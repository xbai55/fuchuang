from pathlib import Path
from time import perf_counter
from typing import Any, Optional
import asyncio
import json
import os
import re
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from auth import decode_token, get_current_active_user
from database import ChatHistory, Contact, SessionLocal, User, get_db
from graph_core.graph_client import graph_client
from graph_core.task_manager import TaskStatus, task_manager
from schemas import FeedbackRequest
from schemas.response import ResponseCode, error_response, paginate_response, success_response
from src.brain.rag.auto_build import get_rag_config_path
from src.brain.rag.config import load_rag_config
from src.brain.rag.detector import RiskDetector
from src.brain.rag.indexer import SimilarityIndex
from src.brain.rag.models import create_search_hit_from_retrieved_case
from src.brain.rag.retriever import FraudCaseRetriever
from src.core.utils.config_loader import load_node_config
from src.core.utils.risk_personalization import build_personalized_thresholds
from src.evolution.monitoring_service import monitoring_service
from src.evolution.runtime import get_evolution_runtime

router = APIRouter()
evolution_runtime = get_evolution_runtime()
_FAST_RAG_BUNDLE: Optional[dict[str, Any]] = None
_FAST_RAG_BUNDLE_LOCK = asyncio.Lock()
_SINGLE_PASS_FRAUD_LLM: Optional[ChatOpenAI] = None
_FAST_IMAGE_AI_ANALYZER: Any = None
_FAST_IMAGE_AI_ANALYZER_LOCK = asyncio.Lock()
_FAST_IMAGE_AI_ANALYZER_ERROR: Optional[str] = None

_SINGLE_PASS_REPORT_SEPARATOR = "\n---REPORT---\n"
_SINGLE_PASS_SYSTEM_PROMPT = """你是一位专业反诈分析助手，请严格遵守输出协议并只输出要求内容。

先输出 5 行元数据（严格使用以下英文键名）：
RISK_SCORE: <0-100整数>
RISK_LEVEL: <low|medium|high>
SCAM_TYPE: <诈骗类型名称>
GUARDIAN_ALERT: <true|false>
WARNING_MESSAGE: <一句话风险提醒>

随后必须单独输出一行分隔符：
---REPORT---

分隔符后输出 Markdown 正文报告，要求：
1. 用中文输出
2. 结构清晰，包含风险结论、关键线索、建议操作
3. 禁止再次输出 RISK_SCORE 等元数据键
4. 如果信息不足，明确标注不确定性并给出保守建议"""


_TEXT_PATTERN_RULES = (
    (re.compile(r"(立即|马上|立刻).{0,8}(转账|汇款|打款)"), 30, "对方要求立即转账"),
    (re.compile(r"(验证码|短信码|动态码).{0,8}(告诉|提供|发给)"), 28, "对方索要验证码"),
    (re.compile(r"(安全账户|资金清查|洗钱|配合调查|案件保密)"), 26, "出现公检法常见施压话术"),
    (re.compile(r"(屏幕共享|远程控制|远程协助|会议软件|共享屏幕)"), 24, "对方引导远程控制"),
    (re.compile(r"(点击链接|下载app|安装软件|扫码|二维码).{0,10}(退款|解冻|核验|领取)"), 22, "出现诱导链接或安装话术"),
)

_TEXT_KEYWORD_WEIGHTS = {
    "公安局": 12,
    "检察院": 12,
    "法院": 10,
    "冻结": 10,
    "解冻": 8,
    "刷流水": 16,
    "跑分": 18,
    "裸聊": 20,
    "征信": 10,
    "兼职刷单": 18,
    "先垫付": 14,
    "高收益": 14,
    "内部消息": 12,
    "verification code": 18,
    "wire transfer": 18,
    "safe account": 16,
    "screen share": 16,
}

_RISK_LEVEL_PRIORITY = {"low": 1, "medium": 2, "high": 3}


def _normalize_level(
    level: str,
    fallback_score: int,
    low_threshold: int = 40,
    high_threshold: int = 75,
) -> str:
    normalized = (level or "").lower().strip()
    if normalized in _RISK_LEVEL_PRIORITY:
        return normalized
    return _risk_level_from_score(fallback_score, low_threshold=low_threshold, high_threshold=high_threshold)


def _max_level(*levels: str) -> str:
    best_level = "low"
    best_rank = 0
    for item in levels:
        normalized = (item or "").lower().strip()
        rank = _RISK_LEVEL_PRIORITY.get(normalized, 0)
        if rank > best_rank:
            best_rank = rank
            best_level = normalized
    return best_level


def _risk_level_from_score(score: int, low_threshold: int = 40, high_threshold: int = 75) -> str:
    if score > high_threshold:
        return "high"
    if score >= low_threshold:
        return "medium"
    return "low"


def _is_single_pass_enabled() -> bool:
    raw = os.getenv("FRAUD_SINGLE_PASS_STREAMING", "true")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _extract_llm_chunk_text(raw_content: Any) -> str:
    if raw_content is None:
        return ""
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, list):
        parts: list[str] = []
        for item in raw_content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    if isinstance(raw_content, dict):
        text = raw_content.get("text") or raw_content.get("content")
        return str(text) if text else ""
    return str(raw_content)


def _clamp_risk_score(value: int) -> int:
    return max(0, min(100, int(value)))


def _parse_bool(raw_value: str, default: bool = False) -> bool:
    normalized = (raw_value or "").strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_user_memory_context(db: Session, current_user: User, message: str) -> dict[str, Any]:
    user_id = str(current_user.id)
    recent_detections = evolution_runtime.get_recent_detections(user_id=user_id, limit=5)
    short_term_memory_summary = evolution_runtime.build_short_term_memory(
        user_id=user_id,
        current_text=(message or "").strip(),
        recent_detections=recent_detections,
    )

    history_rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(60)
        .all()
    )

    scores = [_safe_int(getattr(item, "risk_score", 0), 0) for item in history_rows]
    total_count = len(scores)
    avg_score = (sum(scores) / total_count) if total_count else 0.0
    high_count = sum(1 for score in scores if score > 75)
    medium_count = sum(1 for score in scores if 40 <= score <= 75)

    recent_window = scores[:5]
    baseline_window = scores[5:15]
    recent_avg = (sum(recent_window) / len(recent_window)) if recent_window else avg_score
    baseline_avg = (sum(baseline_window) / len(baseline_window)) if baseline_window else avg_score
    rising_risk = (
        (recent_avg - baseline_avg >= 12)
        if baseline_window else (bool(recent_window) and recent_avg >= 62)
    )

    history_profile = {
        "total_count": total_count,
        "avg_score": round(avg_score, 2),
        "high_ratio": round(high_count / total_count, 4) if total_count else 0.0,
        "medium_ratio": round(medium_count / total_count, 4) if total_count else 0.0,
        "recent_avg_score": round(recent_avg, 2),
        "baseline_avg_score": round(baseline_avg, 2),
        "rising_risk": rising_risk,
    }

    if total_count > 0:
        long_term_memory_summary = (
            f"历史检测 {total_count} 次，平均风险 {avg_score:.1f}/100，"
            f"高风险占比 {history_profile['high_ratio']:.0%}，"
            f"中风险占比 {history_profile['medium_ratio']:.0%}，"
            f"趋势 {'上升' if rising_risk else '平稳'}"
        )
    else:
        long_term_memory_summary = "暂无长期历史行为记录"

    dynamic_thresholds = build_personalized_thresholds(
        user_role=str(current_user.user_role or "general"),
        short_term_events=recent_detections,
        history_profile=history_profile,
    )

    return {
        "short_term_memory_summary": short_term_memory_summary,
        "long_term_memory_summary": long_term_memory_summary,
        "recent_detections": recent_detections,
        "history_profile": history_profile,
        "dynamic_thresholds": dynamic_thresholds,
    }


def _extract_action_items_from_report(report: str, max_items: int = 4) -> list[str]:
    if not report:
        return []

    action_items: list[str] = []
    for line in report.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") or stripped.startswith("•"):
            action_items.append(stripped.lstrip("-• ").strip())
            continue
        if re.match(r"^\d+[\.)、]\s+", stripped):
            action_items.append(re.sub(r"^\d+[\.)、]\s+", "", stripped))

        if len(action_items) >= max_items:
            break

    return [item for item in action_items if item]


def _build_single_pass_user_prompt(
    message: str,
    user_role: str,
    early_warning: Optional[dict],
    has_media: bool,
    memory_context: Optional[dict[str, Any]] = None,
    dynamic_thresholds: Optional[dict[str, Any]] = None,
) -> str:
    memory_context = memory_context or {}
    dynamic_thresholds = dynamic_thresholds or {}

    warning_score = int((early_warning or {}).get("risk_score", 0))
    warning_level = str((early_warning or {}).get("risk_level", "low")).lower()
    warning_text = str((early_warning or {}).get("warning_message", "")).strip()
    warning_clues = list((early_warning or {}).get("risk_clues") or [])
    warning_clues_text = "\n".join(f"- {item}" for item in warning_clues[:6]) if warning_clues else "- 无"

    short_term_summary = str(memory_context.get("short_term_memory_summary") or "暂无短期风险记忆")
    long_term_summary = str(memory_context.get("long_term_memory_summary") or "暂无长期历史行为记录")
    low_threshold = _safe_int(dynamic_thresholds.get("low_threshold"), 40)
    high_threshold = _safe_int(dynamic_thresholds.get("high_threshold"), 75)
    threshold_reasons = list(dynamic_thresholds.get("adjustment_reasons") or [])
    threshold_reason_text = "；".join(str(item) for item in threshold_reasons) if threshold_reasons else "无"

    media_hint = "用户包含媒体文件上传；请在报告中说明当前结论以文本与预警为基础。" if has_media else "本次输入为文本场景。"

    return (
        "请基于以下信息输出反诈分析：\n"
        f"用户角色: {user_role or 'general'}\n"
        f"{media_hint}\n"
        f"快速预警分数: {warning_score}\n"
        f"快速预警等级: {warning_level}\n"
        f"快速预警提示: {warning_text or '无'}\n"
        f"快速预警线索:\n{warning_clues_text}\n\n"
        "短期记忆（最近检测）:\n"
        f"{short_term_summary}\n\n"
        "长期行为画像:\n"
        f"{long_term_summary}\n\n"
        "个性化风险分段阈值:\n"
        f"- low_threshold: {low_threshold}\n"
        f"- high_threshold: {high_threshold}\n"
        f"- 调整依据: {threshold_reason_text}\n\n"
        "用户原始输入:\n"
        f"{(message or '').strip()}\n\n"
        "请务必按照系统协议输出，并确保 RISK_LEVEL 与上述个性化阈值分段一致。"
    )


def _parse_single_pass_response(
    raw_output: str,
    early_warning: Optional[dict],
    dynamic_thresholds: Optional[dict[str, Any]] = None,
    memory_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    dynamic_thresholds = dynamic_thresholds or {}
    memory_context = memory_context or {}

    normalized = (raw_output or "").replace("\r\n", "\n")

    if _SINGLE_PASS_REPORT_SEPARATOR in normalized:
        header_text, report_text = normalized.split(_SINGLE_PASS_REPORT_SEPARATOR, 1)
    else:
        header_text, report_text = "", normalized

    score_match = re.search(r"RISK_SCORE\s*:\s*(\d{1,3})", header_text, re.IGNORECASE)
    level_match = re.search(r"RISK_LEVEL\s*:\s*(low|medium|high)", header_text, re.IGNORECASE)
    scam_type_match = re.search(r"SCAM_TYPE\s*:\s*(.+)", header_text, re.IGNORECASE)
    guardian_alert_match = re.search(r"GUARDIAN_ALERT\s*:\s*(.+)", header_text, re.IGNORECASE)
    warning_message_match = re.search(r"WARNING_MESSAGE\s*:\s*(.+)", header_text, re.IGNORECASE)

    fallback_score = int((early_warning or {}).get("risk_score", 0))
    parsed_score = int(score_match.group(1)) if score_match else fallback_score
    risk_score = _clamp_risk_score(parsed_score)

    low_threshold = _safe_int(dynamic_thresholds.get("low_threshold"), 40)
    high_threshold = _safe_int(dynamic_thresholds.get("high_threshold"), 75)
    score_based_level = _risk_level_from_score(
        risk_score,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
    )

    parsed_level = (level_match.group(1).lower() if level_match else "")
    fallback_level = _normalize_level(
        str((early_warning or {}).get("risk_level", "")),
        risk_score,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
    )
    risk_level = _max_level(parsed_level, score_based_level, fallback_level)

    scam_type = (scam_type_match.group(1).strip() if scam_type_match else "") or "未识别"
    guardian_alert = _parse_bool(
        guardian_alert_match.group(1).strip() if guardian_alert_match else "",
        default=risk_level == "high",
    )

    warning_message = (
        warning_message_match.group(1).strip() if warning_message_match else ""
    ) or str((early_warning or {}).get("warning_message", "")).strip()

    final_report = report_text.strip() or warning_message or "系统已完成分析，请保持警惕并避免敏感操作。"
    risk_clues = list((early_warning or {}).get("risk_clues") or [])
    action_items = _extract_action_items_from_report(final_report)

    if not action_items:
        if risk_level == "high":
            action_items = [
                "立即停止转账和共享屏幕",
                "保留证据并拨打 110 或 96110",
                "尽快联系银行进行风险止付",
            ]
        elif risk_level == "medium":
            action_items = [
                "暂停当前操作并通过官方渠道核验",
                "不要提供验证码或银行卡信息",
                "将可疑信息发给可信联系人复核",
            ]
        else:
            action_items = [
                "继续保持警惕并核验来源",
                "避免点击陌生链接",
                "如被催促转账请立即中断",
            ]

    return {
        "detection_id": f"det_{uuid.uuid4().hex[:12]}",
        "intent": "single_pass_analysis",
        "short_term_memory_summary": str(memory_context.get("short_term_memory_summary") or ""),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "scam_type": scam_type,
        "risk_clues": risk_clues,
        "warning_message": warning_message,
        "guardian_alert": guardian_alert,
        "alert_reason": "single_pass_llm",
        "action_items": action_items,
        "escalation_actions": [],
        "guardian_notification": None,
        "final_report": final_report,
        "similar_cases": [],
        "personalized_thresholds": {
            "low_threshold": low_threshold,
            "high_threshold": high_threshold,
            "adjustment_reasons": list(dynamic_thresholds.get("adjustment_reasons") or []),
        },
    }


def _get_single_pass_fraud_llm() -> Optional[ChatOpenAI]:
    global _SINGLE_PASS_FRAUD_LLM

    if _SINGLE_PASS_FRAUD_LLM is not None:
        return _SINGLE_PASS_FRAUD_LLM

    api_key = os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    config = load_node_config("report_generation")
    model_name = config.get("model") or os.getenv("LLM_MODEL", "moonshot-v1-8k")
    base_url = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")

    _SINGLE_PASS_FRAUD_LLM = ChatOpenAI(
        model=model_name,
        temperature=float(config.get("temperature", 0.2)),
        max_tokens=int(config.get("max_tokens", 1800)),
        timeout=int(config.get("timeout", 60)),
        api_key=api_key,
        base_url=base_url,
    )
    return _SINGLE_PASS_FRAUD_LLM


async def _run_single_pass_detection_stream(
    task_id: str,
    message: str,
    user_role: str,
    early_warning: Optional[dict],
    has_media: bool,
    memory_context: Optional[dict[str, Any]] = None,
    dynamic_thresholds: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], int]:
    llm = _get_single_pass_fraud_llm()
    if llm is None:
        raise RuntimeError("LLM API key 未配置，无法启用单次流式分析")

    user_prompt = _build_single_pass_user_prompt(
        message=message,
        user_role=user_role,
        early_warning=early_warning,
        has_media=has_media,
        memory_context=memory_context,
        dynamic_thresholds=dynamic_thresholds,
    )
    messages = [
        SystemMessage(content=_SINGLE_PASS_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    task_manager.publish_task_event(task_id, {"event": "report_stream_started", "stream_mode": "token"})

    raw_parts: list[str] = []
    buffered_prefix = ""
    marker_seen = False
    chunk_count = 0

    async for chunk in llm.astream(messages):
        chunk_text = _extract_llm_chunk_text(getattr(chunk, "content", ""))
        if not chunk_text:
            continue

        raw_parts.append(chunk_text)

        if marker_seen:
            chunk_count += 1
            task_manager.publish_task_event(
                task_id,
                {
                    "event": "report_chunk",
                    "chunk": chunk_text,
                    "chunk_index": chunk_count,
                },
            )
            task_manager.update_task_progress(task_id, min(94, 40 + int(chunk_count * 1.5)))
            continue

        buffered_prefix += chunk_text
        marker_index = buffered_prefix.find(_SINGLE_PASS_REPORT_SEPARATOR)
        if marker_index >= 0:
            marker_seen = True
            report_text_after_marker = buffered_prefix[marker_index + len(_SINGLE_PASS_REPORT_SEPARATOR):]
            buffered_prefix = ""
            if report_text_after_marker:
                chunk_count += 1
                task_manager.publish_task_event(
                    task_id,
                    {
                        "event": "report_chunk",
                        "chunk": report_text_after_marker,
                        "chunk_index": chunk_count,
                    },
                )
                task_manager.update_task_progress(task_id, min(94, 40 + int(chunk_count * 1.5)))
            continue

        # Fail-safe: if model didn't follow protocol, still stream what we already got.
        if len(buffered_prefix) > 900:
            marker_seen = True
            chunk_count += 1
            task_manager.publish_task_event(
                task_id,
                {
                    "event": "report_chunk",
                    "chunk": buffered_prefix,
                    "chunk_index": chunk_count,
                },
            )
            buffered_prefix = ""
            task_manager.update_task_progress(task_id, min(94, 40 + int(chunk_count * 1.5)))

    raw_output = "".join(raw_parts)
    parsed_result = _parse_single_pass_response(
        raw_output,
        early_warning=early_warning,
        dynamic_thresholds=dynamic_thresholds,
        memory_context=memory_context,
    )

    return parsed_result, chunk_count


def _load_fast_rag_bundle_sync() -> Optional[dict[str, Any]]:
    """
    Load a lightweight RAG bundle for early warning.

    For latency stability, early warning only uses local TF-IDF index
    and does not trigger vector embedding calls.
    """
    try:
        config_path = get_rag_config_path()
        if not config_path.exists():
            return None

        config = load_rag_config(config_path)
        if not config.paths.index_dir.exists():
            return None

        tfidf_index = SimilarityIndex.load(config.paths.index_dir)
        if tfidf_index.backend == "sentence-transformer":
            # Dense query encoding cold-start is too expensive for early warning.
            return None

        top_k = max(3, min(6, int(config.index.top_k)))
        retriever = FraudCaseRetriever(
            tfidf_index=tfidf_index,
            default_k=top_k,
            use_hybrid=False,
        )
        detector = RiskDetector(
            high_threshold=config.warning.high_threshold,
            medium_threshold=config.warning.medium_threshold,
        )

        return {
            "retriever": retriever,
            "detector": detector,
            "top_k": top_k,
        }
    except Exception as exc:
        print(f"[预警] 快速RAG初始化失败: {exc}")
        return None


async def _get_fast_rag_bundle() -> Optional[dict[str, Any]]:
    global _FAST_RAG_BUNDLE

    if _FAST_RAG_BUNDLE is not None:
        return _FAST_RAG_BUNDLE

    async with _FAST_RAG_BUNDLE_LOCK:
        if _FAST_RAG_BUNDLE is not None:
            return _FAST_RAG_BUNDLE
        _FAST_RAG_BUNDLE = await asyncio.to_thread(_load_fast_rag_bundle_sync)
        return _FAST_RAG_BUNDLE


async def _build_fast_rag_warning(message: str) -> Optional[dict]:
    text = (message or "").strip()
    if len(text) < 6:
        return None

    rag_bundle = await _get_fast_rag_bundle()
    if not rag_bundle:
        return None

    retriever: FraudCaseRetriever = rag_bundle["retriever"]
    detector: RiskDetector = rag_bundle["detector"]
    top_k = int(rag_bundle.get("top_k", 4))

    # Cap query length for predictable latency.
    query = text[:900]
    try:
        retrieved_cases = await retriever.retrieve(query=query, k=top_k)
    except Exception as exc:
        print(f"[预警] 快速RAG检索失败: {exc}")
        return None

    if not retrieved_cases:
        return None

    search_hits = [create_search_hit_from_retrieved_case(case) for case in retrieved_cases]
    rag_result = detector.assess(query, search_hits)

    rag_score = int(float(rag_result.confidence) * 100)
    rag_level = _normalize_level(rag_result.risk_level, rag_score)

    if rag_level == "low" and rag_score < 12:
        return None

    clues: list[str] = []
    if rag_result.matched_subtypes:
        clues.append(f"RAG命中子类型: {rag_result.matched_subtypes[0]}")
    for tag in (rag_result.matched_tags or [])[:3]:
        clues.append(f"RAG标签: {tag}")
    clues.append(f"RAG命中知识片段: {len(rag_result.hits)}条")

    if rag_level == "high":
        warning_message = "RAG检索高度匹配诈骗知识，请立即暂停资金与账号操作。"
    elif rag_level == "medium":
        warning_message = "RAG检索到可疑诈骗特征，请先核验后再执行敏感操作。"
    else:
        warning_message = "RAG检索有少量可疑命中，建议保持谨慎并等待完整分析。"

    return {
        "risk_score": min(rag_score, 99),
        "risk_level": rag_level,
        "risk_clues": clues[:6],
        "warning_message": warning_message,
        "source": "fast_rag_probe",
        "is_preliminary": True,
    }


def _merge_fast_warnings(
    rule_warning: Optional[dict],
    rag_warning: Optional[dict],
    has_media: bool,
    image_ai_warning: Optional[dict] = None,
) -> Optional[dict]:
    warning: Optional[dict] = None

    if rule_warning and rag_warning:
        rule_score = int(rule_warning.get("risk_score", 0))
        rag_score = int(rag_warning.get("risk_score", 0))
        merged_score = min(99, int(rule_score * 0.55 + rag_score * 0.45))

        merged_level = _max_level(
            str(rule_warning.get("risk_level", "low")),
            str(rag_warning.get("risk_level", "low")),
        )
        if merged_level == "high":
            merged_score = max(merged_score, 78)
            warning_message = "规则与RAG双重信号均提示高风险，请立即停止转账并核验身份。"
        elif merged_level == "medium":
            merged_score = max(merged_score, 45)
            warning_message = "规则与RAG信号提示存在诈骗风险，请暂停敏感操作并核验。"
        else:
            warning_message = "规则与RAG未发现明显高危特征，建议保持谨慎并等待完整分析。"

        merged_clues = list(
            dict.fromkeys(
                list(rule_warning.get("risk_clues", []))
                + list(rag_warning.get("risk_clues", []))
            )
        )[:8]

        if has_media:
            warning_message += " 已同步启动音频/图片/视频AI率检测。"

        warning = {
            "risk_score": merged_score,
            "risk_level": merged_level,
            "risk_clues": merged_clues,
            "warning_message": warning_message,
            "source": "rules_rag_fusion",
            "is_preliminary": True,
        }

    elif rag_warning or rule_warning:
        warning = dict(rag_warning or rule_warning or {})

    if image_ai_warning:
        if warning is None:
            warning = dict(image_ai_warning)
        else:
            base_score = int(warning.get("risk_score", 0))
            ai_score = int(image_ai_warning.get("risk_score", 0))
            merged_level = _max_level(
                str(warning.get("risk_level", "low")),
                str(image_ai_warning.get("risk_level", "low")),
            )
            merged_score = min(99, max(base_score, int(base_score * 0.30 + ai_score * 0.70)))

            if merged_level == "high":
                merged_score = max(merged_score, 82)
            elif merged_level == "medium":
                merged_score = max(merged_score, 52)

            merged_clues = list(
                dict.fromkeys(
                    list(image_ai_warning.get("risk_clues", []))
                    + list(warning.get("risk_clues", []))
                )
            )[:8]

            ai_message = str(image_ai_warning.get("warning_message", "")).strip()
            base_message = str(warning.get("warning_message", "")).strip()
            if ai_message and base_message and ai_message not in base_message:
                warning_message = f"{ai_message} {base_message}".strip()
            else:
                warning_message = ai_message or base_message

            warning.update(
                {
                    "risk_score": merged_score,
                    "risk_level": merged_level,
                    "risk_clues": merged_clues,
                    "warning_message": warning_message,
                    "source": "rules_rag_image_ai_fusion",
                    "is_preliminary": True,
                }
            )

        warning["image_ai_probability"] = image_ai_warning.get("image_ai_probability")
        warning["prefer_ai_rate_early_warning"] = bool(
            image_ai_warning.get("prefer_ai_rate_early_warning", False)
        )
        warning["image_ai_ocr_skip_threshold"] = image_ai_warning.get("image_ai_ocr_skip_threshold", 0.74)

    if warning is None:
        return None

    if has_media and warning.get("warning_message"):
        if "AI率检测" not in str(warning["warning_message"]):
            warning["warning_message"] = f"{warning['warning_message']} 已同步启动音频/图片/视频AI率检测。"
    return warning


def _load_fast_image_ai_analyzer_sync() -> Any:
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    multimodal_path = project_root / "multimodal_input"
    if str(multimodal_path) not in sys.path:
        sys.path.insert(0, str(multimodal_path))

    from video_module.video_inference import get_shared_video_fake_analyzer

    model_path = os.getenv("VIDEO_MODEL_PATH")
    if not model_path:
        model_path = str(multimodal_path / "video_module" / "weights" / "final_model.pth")

    snap_timestamp = 1.0
    try:
        snap_timestamp = float(os.getenv("VIDEO_SNAP_TIMESTAMP", "1.0"))
    except (TypeError, ValueError):
        snap_timestamp = 1.0

    return get_shared_video_fake_analyzer(
        weight_path=model_path,
        snap_timestamp_sec=snap_timestamp,
    )


async def _get_fast_image_ai_analyzer() -> Any:
    global _FAST_IMAGE_AI_ANALYZER
    global _FAST_IMAGE_AI_ANALYZER_ERROR

    if _FAST_IMAGE_AI_ANALYZER is not None:
        return _FAST_IMAGE_AI_ANALYZER
    if _FAST_IMAGE_AI_ANALYZER_ERROR:
        return None

    async with _FAST_IMAGE_AI_ANALYZER_LOCK:
        if _FAST_IMAGE_AI_ANALYZER is not None:
            return _FAST_IMAGE_AI_ANALYZER
        if _FAST_IMAGE_AI_ANALYZER_ERROR:
            return None

        try:
            _FAST_IMAGE_AI_ANALYZER = await asyncio.to_thread(_load_fast_image_ai_analyzer_sync)
        except Exception as exc:
            _FAST_IMAGE_AI_ANALYZER_ERROR = str(exc)
            print(f"[预警] 图片AI率模型初始化失败: {exc}")
            return None

    return _FAST_IMAGE_AI_ANALYZER


async def _build_fast_image_ai_warning(image_path: Optional[str]) -> Optional[dict]:
    if not image_path or not os.path.exists(image_path):
        return None

    analyzer = await _get_fast_image_ai_analyzer()
    if analyzer is None:
        return None

    try:
        fake_prob = await asyncio.to_thread(analyzer.predict_image_path, image_path)
    except Exception as exc:
        print(f"[预警] 图片AI率快速检测失败: {exc}")
        return None

    fake_prob = max(0.0, min(1.0, float(fake_prob)))
    score = _clamp_risk_score(int(round(fake_prob * 100)))

    if fake_prob >= 0.82:
        level = "high"
        score = max(score, 82)
        warning_message = f"图片AI率检测为 {fake_prob:.0%}，疑似深度伪造，请立即暂停转账并核验来源。"
    elif fake_prob >= 0.60:
        level = "medium"
        score = max(score, 52)
        warning_message = f"图片AI率检测为 {fake_prob:.0%}，存在伪造风险，建议先核验再执行敏感操作。"
    elif fake_prob >= 0.25:
        level = "low"
        warning_message = f"图片AI率检测为 {fake_prob:.0%}，暂未到高危阈值，仍建议保持谨慎。"
    else:
        return None

    return {
        "risk_score": score,
        "risk_level": level,
        "risk_clues": [
            f"图片AI率: {fake_prob:.0%}",
            "图片早期预警优先参考AI率检测",
        ],
        "warning_message": warning_message,
        "source": "fast_image_ai_probe",
        "is_preliminary": True,
        "image_ai_probability": fake_prob,
        "prefer_ai_rate_early_warning": fake_prob >= 0.60,
        "image_ai_ocr_skip_threshold": 0.74,
    }


async def _build_fast_early_warning(
    message: str,
    has_media: bool,
    image_ai_warning: Optional[dict] = None,
) -> Optional[dict]:
    rule_warning = _build_fast_text_warning(message, has_media=has_media)
    rag_warning = None

    text = (message or "").strip()
    if text:
        try:
            rag_warning = await asyncio.wait_for(
                _build_fast_rag_warning(text),
                timeout=1.8,
            )
        except asyncio.TimeoutError:
            print("[预警] 快速RAG超时，回退规则预警")
        except Exception as exc:
            print(f"[预警] 快速RAG失败，回退规则预警: {exc}")

    merged_warning = _merge_fast_warnings(
        rule_warning,
        rag_warning,
        has_media,
        image_ai_warning=image_ai_warning,
    )
    if merged_warning is not None:
        return merged_warning

    text = (message or "").strip()
    if has_media:
        fallback_message = "已完成快速预检，媒体文件处理中，稍后将返回完整风险报告。"
        fallback_clues = ["媒体文件已上传，等待多模态分析结果"]
    elif text:
        fallback_message = "已完成快速预检，暂未发现显著高危线索，正在生成完整分析报告。"
        fallback_clues = ["快速规则和RAG未命中高危特征"]
    else:
        fallback_message = "已启动快速预警，正在生成完整分析报告。"
        fallback_clues = ["等待用户输入内容"]

    return {
        "risk_score": 6 if text else 0,
        "risk_level": "low",
        "risk_clues": fallback_clues,
        "warning_message": fallback_message,
        "source": "fast_fallback",
        "is_preliminary": True,
    }


def _build_fast_text_warning(message: str, has_media: bool) -> Optional[dict]:
    text = (message or "").strip()

    if not text:
        if not has_media:
            return None
        return {
            "risk_score": 0,
            "risk_level": "low",
            "risk_clues": ["媒体文件已上传，等待AI率结果"],
            "warning_message": "已收到媒体文件，正在进行AI伪造率快速检测。",
            "source": "media_ai_pending",
            "is_preliminary": True,
        }

    score = 0
    clues = []
    lower_text = text.lower()

    for pattern, weight, clue in _TEXT_PATTERN_RULES:
        if pattern.search(text):
            score += weight
            clues.append(clue)

    for keyword, weight in _TEXT_KEYWORD_WEIGHTS.items():
        if keyword in text or keyword in lower_text:
            score += weight
            clues.append(f"命中关键词: {keyword}")

    urgent_punctuation = text.count("!") + text.count("！")
    if urgent_punctuation >= 2:
        score += 6
        clues.append("话术存在明显催促语气")

    score = min(score, 95)
    if score < 20 and not has_media:
        return None

    level = _risk_level_from_score(score)
    if level == "high":
        warning_message = "检测到高危诈骗话术，请立即停止转账并核验对方身份。"
    elif level == "medium":
        warning_message = "检测到可疑话术，请暂停敏感操作并通过官方渠道核验。"
    else:
        warning_message = "当前未发现明显高危话术，建议保持谨慎并等待完整分析。"

    if has_media:
        warning_message += " 已同步启动音频/图片/视频AI率检测。"

    return {
        "risk_score": score,
        "risk_level": level,
        "risk_clues": list(dict.fromkeys(clues))[:6],
        "warning_message": warning_message,
        "source": "fast_text_rules",
        "is_preliminary": True,
    }


def _chunk_report_text(report: str, chunk_size: int = 220) -> list[str]:
    normalized = (report or "").replace("\r\n", "\n")
    if not normalized.strip():
        return []

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_len = 0

    for line in normalized.split("\n"):
        segment = f"{line}\n"
        segment_len = len(segment)
        if buffer and buffer_len + segment_len > chunk_size:
            chunks.append("".join(buffer))
            buffer = [segment]
            buffer_len = segment_len
            continue

        buffer.append(segment)
        buffer_len += segment_len

    if buffer:
        chunks.append("".join(buffer))

    return chunks


def _save_temp_file(upload_file: UploadFile) -> str:
    temp_dir = tempfile.gettempdir()
    suffix = Path(upload_file.filename).suffix if upload_file.filename else ""
    temp_filename = f"{uuid.uuid4().hex}{suffix}"
    temp_path = os.path.join(temp_dir, temp_filename)
    with open(temp_path, "wb") as file_obj:
        file_obj.write(upload_file.file.read())
    upload_file.file.seek(0)
    return temp_path


def _serialize_contacts(contacts) -> list[dict]:
    return [
        {
            "name": contact.name,
            "phone": contact.phone,
            "relationship": getattr(contact, "relationship", ""),
            "is_guardian": bool(contact.is_guardian),
        }
        for contact in contacts
    ]


def _build_detection_payload(result: dict) -> dict:
    return {
        "detection_id": result.get("detection_id"),
        "intent": result.get("intent"),
        "short_term_memory_summary": result.get("short_term_memory_summary", ""),
        "risk_score": result.get("risk_score", 0),
        "risk_level": result.get("risk_level", "low"),
        "scam_type": result.get("scam_type", ""),
        "risk_clues": result.get("risk_clues", []),
        "warning_message": result.get("warning_message", ""),
        "guardian_alert": result.get("guardian_alert", False),
        "alert_reason": result.get("alert_reason", ""),
        "action_items": result.get("action_items", []),
        "escalation_actions": result.get("escalation_actions", []),
        "guardian_notification": result.get("guardian_notification"),
        "final_report": result.get("final_report", ""),
        "similar_cases": result.get("similar_cases", []),
        "personalized_thresholds": result.get("personalized_thresholds"),
    }


def _build_history_bot_response(result: dict) -> str:
    """Build a history-safe text payload with summary + detailed report."""
    warning_message = str(result.get("warning_message") or "").strip()
    final_report = str(result.get("final_report") or "").strip()

    if not final_report:
        return warning_message

    detail_marker_exists = bool(re.search(r"(^|\n)#{1,6}\s*(详细分析|Detailed Analysis)\s*($|\n)", warning_message, re.IGNORECASE))
    if detail_marker_exists:
        return warning_message

    if warning_message:
        return f"{warning_message}\n\n## 详细分析\n{final_report}"

    return f"## 详细分析\n{final_report}"


def _get_ws_user(token: Optional[str]) -> Optional[User]:
    if not token:
        return None

    token_data = decode_token(token, token_type="access")
    if token_data is None or token_data.user_id is None:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == token_data.user_id).first()
        if not user or not user.is_active:
            return None
        return user
    finally:
        db.close()


@router.post("/detect")
async def detect_fraud(
    message: str = Form(...),
    audio_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    temp_files = []
    started_at = perf_counter()
    request_success = False
    error_message = None
    has_media = bool(audio_file or image_file or video_file)
    use_single_pass = _is_single_pass_enabled() and not has_media
    monitor_model_name = "fraud_detection_single_pass" if use_single_pass else "fraud_detection_graph"

    try:
        audio_path = _save_temp_file(audio_file) if audio_file else None
        image_path = _save_temp_file(image_file) if image_file else None
        video_path = _save_temp_file(video_file) if video_file else None
        temp_files = [path for path in [audio_path, image_path, video_path] if path]

        contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
        guardian_contact = next((contact for contact in contacts if contact.is_guardian), None)
        memory_context = _build_user_memory_context(db, current_user, message)

        if use_single_pass:
            fallback_warning = _build_fast_text_warning(message, has_media=False)
            result, _ = await _run_single_pass_detection_stream(
                task_id=f"sync_{uuid.uuid4().hex[:12]}",
                message=message,
                user_role=current_user.user_role,
                early_warning=fallback_warning,
                has_media=False,
                memory_context=memory_context,
                dynamic_thresholds=memory_context.get("dynamic_thresholds"),
            )
        else:
            workflow_options = {
                "prefer_ai_rate_early_warning": bool(image_path),
                "image_ai_ocr_skip_threshold": 0.74,
            }
            result = await graph_client.detect_fraud(
                text=message,
                audio_path=audio_path,
                image_path=image_path,
                video_path=video_path,
                user_role=current_user.user_role,
                guardian_name=(guardian_contact.name if guardian_contact else current_user.guardian_name),
                guardian_phone=(guardian_contact.phone if guardian_contact else None),
                emergency_contacts=_serialize_contacts(contacts),
                notify_enabled=current_user.notify_enabled,
                notify_guardian_alert=current_user.notify_guardian_alert,
                user_id=str(current_user.id),
                history_profile=memory_context.get("history_profile"),
                workflow_options=workflow_options,
            )

        db.add(
            ChatHistory(
                user_id=current_user.id,
                user_message=message,
                bot_response=_build_history_bot_response(result),
                risk_score=result.get("risk_score", 0),
                risk_level=result.get("risk_level", "low"),
                scam_type=result.get("scam_type", ""),
                guardian_alert=result.get("guardian_alert", False),
            )
        )
        db.commit()
        request_success = True
        return success_response(data=_build_detection_payload(result), message="检测完成")

    except Exception as exc:
        error_message = str(exc)
        raise HTTPException(status_code=500, detail=f"检测失败: {exc}")

    finally:
        latency_ms = (perf_counter() - started_at) * 1000
        try:
            await monitoring_service.record_request(
                model_name=monitor_model_name,
                latency_ms=latency_ms,
                success=request_success,
                error=error_message,
                context={"endpoint": "/api/fraud/detect", "mode": "sync"},
            )
        except Exception as monitor_error:
            print(f"[monitoring] detect record failed: {monitor_error}")

        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as cleanup_error:
                print(f"[cleanup] failed to remove temp file: {cleanup_error}")


@router.post("/detect-async")
async def detect_fraud_async(
    message: str = Form(...),
    audio_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    temp_files = []
    task = None
    has_media = bool(audio_file or image_file or video_file)
    use_single_pass = _is_single_pass_enabled() and not has_media

    try:
        input_summary = message[:50] if message else "fraud-detection"
        if audio_file:
            input_summary += f" [audio:{audio_file.filename}]"
        if image_file:
            input_summary += f" [image:{image_file.filename}]"
        if video_file:
            input_summary += f" [video:{video_file.filename}]"

        task = task_manager.create_task(user_id=current_user.id, input_summary=input_summary)
        task_manager.update_task_progress(task.task_id, 5)
        user_id = current_user.id
        user_role = current_user.user_role
        fallback_guardian_name = current_user.guardian_name
        notify_enabled = current_user.notify_enabled
        notify_guardian_alert = current_user.notify_guardian_alert
        memory_context = _build_user_memory_context(db, current_user, message)

        audio_path = _save_temp_file(audio_file) if audio_file else None
        image_path = _save_temp_file(image_file) if image_file else None
        video_path = _save_temp_file(video_file) if video_file else None
        temp_files = [path for path in [audio_path, image_path, video_path] if path]
        task_manager.update_task_progress(task.task_id, 15)

        image_ai_warning = None
        if image_path:
            try:
                image_ai_warning = await asyncio.wait_for(
                    _build_fast_image_ai_warning(image_path),
                    timeout=1.2,
                )
            except asyncio.TimeoutError:
                print("[预警] 图片AI率快速检测超时，继续执行规则/RAG预警")
            except Exception as exc:
                print(f"[预警] 图片AI率快速检测失败: {exc}")

        early_warning = await _build_fast_early_warning(
            message,
            has_media=has_media,
            image_ai_warning=image_ai_warning,
        )

        workflow_options = {
            "prefer_ai_rate_early_warning": bool(
                (image_ai_warning or {}).get("prefer_ai_rate_early_warning", bool(image_path))
            ),
            "image_ai_probability": (image_ai_warning or {}).get("image_ai_probability"),
            "image_ai_risk_level": (image_ai_warning or {}).get("risk_level"),
            "image_ai_ocr_skip_threshold": (image_ai_warning or {}).get("image_ai_ocr_skip_threshold", 0.74),
        }

        contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
        guardian_contact = next((contact for contact in contacts if contact.is_guardian), None)
        serialized_contacts = _serialize_contacts(contacts)

        async def process_and_cleanup():
            db_session = SessionLocal()
            started_at = perf_counter()
            request_success = False
            error_message = None
            monitor_model_name = "fraud_detection_single_pass" if use_single_pass else "fraud_detection_graph"
            try:
                task_manager.update_task_progress(task.task_id, 35)
                if use_single_pass:
                    result, total_chunks = await _run_single_pass_detection_stream(
                        task_id=task.task_id,
                        message=message,
                        user_role=user_role,
                        early_warning=early_warning,
                        has_media=False,
                        memory_context=memory_context,
                        dynamic_thresholds=memory_context.get("dynamic_thresholds"),
                    )
                    detection_payload = _build_detection_payload(result)
                    stream_mode = "token"
                    if total_chunks <= 0:
                        fallback_chunks = _chunk_report_text(detection_payload.get("final_report", ""))
                        for chunk_index, chunk in enumerate(fallback_chunks, start=1):
                            task_manager.publish_task_event(
                                task.task_id,
                                {
                                    "event": "report_chunk",
                                    "chunk": chunk,
                                    "chunk_index": chunk_index,
                                },
                            )
                        total_chunks = len(fallback_chunks)
                        stream_mode = "fallback_chunk"

                    task_manager.publish_task_event(
                        task.task_id,
                        {
                            "event": "report_stream_finished",
                            "total_chunks": total_chunks,
                            "stream_mode": stream_mode,
                        },
                    )
                else:
                    result = await graph_client.detect_fraud(
                        text=message,
                        audio_path=audio_path,
                        image_path=image_path,
                        video_path=video_path,
                        user_role=user_role,
                        guardian_name=(guardian_contact.name if guardian_contact else fallback_guardian_name),
                        guardian_phone=(guardian_contact.phone if guardian_contact else None),
                        emergency_contacts=serialized_contacts,
                        notify_enabled=notify_enabled,
                        notify_guardian_alert=notify_guardian_alert,
                        user_id=str(user_id),
                        history_profile=memory_context.get("history_profile"),
                        workflow_options=workflow_options,
                    )
                    task_manager.update_task_progress(task.task_id, 78)

                    detection_payload = _build_detection_payload(result)
                    report_chunks = _chunk_report_text(detection_payload.get("final_report", ""))
                    total_chunks = len(report_chunks)

                    if total_chunks > 0:
                        task_manager.publish_task_event(
                            task.task_id,
                            {
                                "event": "report_stream_started",
                                "total_chunks": total_chunks,
                            },
                        )

                        for chunk_index, chunk in enumerate(report_chunks, start=1):
                            task_manager.publish_task_event(
                                task.task_id,
                                {
                                    "event": "report_chunk",
                                    "chunk": chunk,
                                    "chunk_index": chunk_index,
                                    "total_chunks": total_chunks,
                                    "done": chunk_index == total_chunks,
                                },
                            )

                            stream_progress = min(94, 78 + int((chunk_index / total_chunks) * 16))
                            task_manager.update_task_progress(task.task_id, stream_progress)

                            if chunk_index < total_chunks:
                                await asyncio.sleep(0.03)

                        task_manager.publish_task_event(
                            task.task_id,
                            {
                                "event": "report_stream_finished",
                                "total_chunks": total_chunks,
                            },
                        )

                task_manager.update_task_progress(task.task_id, 96)
                task_manager.complete_task(task.task_id, detection_payload)

                db_session.add(
                    ChatHistory(
                        user_id=user_id,
                        user_message=message,
                        bot_response=_build_history_bot_response(result),
                        risk_score=result.get("risk_score", 0),
                        risk_level=result.get("risk_level", "low"),
                        scam_type=result.get("scam_type", ""),
                        guardian_alert=result.get("guardian_alert", False),
                    )
                )
                db_session.commit()
                request_success = True

            except Exception as exc:
                error_message = str(exc)
                db_session.rollback()
                task_manager.fail_task(task.task_id, str(exc))

            finally:
                latency_ms = (perf_counter() - started_at) * 1000
                try:
                    await monitoring_service.record_request(
                        model_name=monitor_model_name,
                        latency_ms=latency_ms,
                        success=request_success,
                        error=error_message,
                        context={"endpoint": "/api/fraud/detect-async", "mode": "async"},
                    )
                except Exception as monitor_error:
                    print(f"[monitoring] async detect record failed: {monitor_error}")

                db_session.close()
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception as cleanup_error:
                        print(f"[cleanup] failed to remove temp file: {cleanup_error}")

        asyncio.create_task(process_and_cleanup())
        return success_response(
            data={
                "task_id": task.task_id,
                "status": task.status.value,
                "estimated_time": 5 if not video_file else 15,
                "poll_url": f"/api/fraud/tasks/{task.task_id}",
                "ws_url": f"/api/fraud/ws/tasks/{task.task_id}",
                "early_warning": early_warning,
            },
            message="异步检测已开始",
        )

    except Exception as exc:
        if task is not None:
            task_manager.fail_task(task.task_id, str(exc))
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
        return error_response(ResponseCode.INTERNAL_ERROR, f"异步检测启动失败: {exc}")


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_active_user),
):
    try:
        result = await evolution_runtime.collect_feedback(
            user_id=str(current_user.id),
            detection_id=request.detection_id,
            feedback_type=request.feedback_type,
            comment=request.comment,
        )
        return success_response(data=result, message="反馈已记录")
    except Exception as exc:
        return error_response(ResponseCode.BAD_REQUEST, f"反馈提交失败: {exc}")


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
):
    task = task_manager.get_task(task_id)
    if not task:
        return error_response(ResponseCode.TASK_NOT_FOUND, "任务不存在")
    if task.user_id != current_user.id:
        return error_response(ResponseCode.FORBIDDEN, "无权查看该任务")
    return success_response(data=task.to_dict())


@router.get("/tasks")
async def get_user_tasks(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    return success_response(data=task_manager.get_user_tasks(current_user.id, limit))


@router.websocket("/ws/tasks/{task_id}")
async def task_updates_ws(websocket: WebSocket, task_id: str):
    token = websocket.query_params.get("token")
    user = _get_ws_user(token)
    if user is None:
        await websocket.close(code=1008, reason="invalid token")
        return

    await websocket.accept()
    task = task_manager.get_task(task_id)
    if task is None:
        await websocket.send_json({"event": "error", "task_id": task_id, "message": "任务不存在"})
        await websocket.close(code=1008)
        return
    if task.user_id != user.id:
        await websocket.send_json({"event": "error", "task_id": task_id, "message": "无权查看该任务"})
        await websocket.close(code=1008)
        return

    terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT}
    last_snapshot = ""
    last_event_seq = 0
    try:
        await websocket.send_json({"event": "connected", "task_id": task_id, "task": task.to_dict()})
        while True:
            current_task = task_manager.get_task(task_id)
            if current_task is None:
                await websocket.send_json({"event": "error", "task_id": task_id, "message": "任务已失效"})
                await websocket.close(code=1000)
                break

            snapshot = current_task.to_dict()
            snapshot_key = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
            if snapshot_key != last_snapshot:
                await websocket.send_json({"event": "task_update", "task_id": task_id, "task": snapshot})
                last_snapshot = snapshot_key

            pending_events = task_manager.get_task_events(task_id, after_seq=last_event_seq)
            for item in pending_events:
                last_event_seq = max(last_event_seq, int(item.get("seq", 0)))
                event_name = item.get("event", "task_event")
                event_payload = {k: v for k, v in item.items() if k != "event"}
                await websocket.send_json({"event": event_name, "task_id": task_id, **event_payload})

            if current_task.status in terminal_statuses:
                event = "task_completed" if current_task.status == TaskStatus.COMPLETED else "task_failed"
                await websocket.send_json(
                    {
                        "event": event,
                        "task_id": task_id,
                        "task": snapshot,
                        "result": current_task.result,
                        "error": current_task.error,
                    }
                )
                await websocket.close(code=1000)
                break
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return


@router.options("/history")
async def options_history():
    return {"ok": True}


@router.get("/history")
async def get_chat_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    test: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if test:
        return success_response(data={"ok": True, "cors_test": "success"}, message="CORS test ok")

    offset = (page - 1) * size
    total = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id).count()
    history = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    items = [
        {
            "id": item.id,
            "user_message": item.user_message,
            "bot_response": item.bot_response,
            "risk_score": item.risk_score,
            "risk_level": item.risk_level,
            "scam_type": item.scam_type,
            "chat_mode": "agent" if item.scam_type == "agent_chat" else "fraud",
            "guardian_alert": item.guardian_alert,
            "created_at": item.created_at.isoformat(),
        }
        for item in history
    ]
    return paginate_response(items, total, page, size)


@router.delete("/history/{history_id}")
async def delete_chat_history_item(
    history_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    history_item = (
        db.query(ChatHistory)
        .filter(ChatHistory.id == history_id, ChatHistory.user_id == current_user.id)
        .first()
    )

    if history_item is None:
        return error_response(ResponseCode.NOT_FOUND, "历史记录不存在")

    db.delete(history_item)
    db.commit()
    return success_response(data={"id": history_id}, message="删除成功")


@router.delete("/history")
async def clear_chat_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    deleted = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return success_response(data={"deleted": deleted}, message="历史记录已清空")
