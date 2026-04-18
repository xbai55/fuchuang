from pathlib import Path
from time import perf_counter, time
from typing import Any, Optional
import asyncio
import json
import os
import re
import tempfile
import uuid

import httpx
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
from src.core.utils.risk_personalization import (
    build_personalized_thresholds,
    format_combined_profile_text,
    normalize_user_role,
)
from src.core.models import MediaFile, MediaType
from src.evolution.monitoring_service import monitoring_service
from src.evolution.runtime import get_evolution_runtime
from src.perception import ProcessingContext, get_perception_manager

router = APIRouter()
evolution_runtime = get_evolution_runtime()
_FAST_RAG_BUNDLE: Optional[dict[str, Any]] = None
_FAST_RAG_BUNDLE_LOCK = asyncio.Lock()
_SINGLE_PASS_FRAUD_LLM: Optional[ChatOpenAI] = None
_FAST_IMAGE_AI_ANALYZER: Any = None
_FAST_IMAGE_AI_ANALYZER_LOCK = asyncio.Lock()
_FAST_IMAGE_AI_ANALYZER_ERROR: Optional[str] = None

_SINGLE_PASS_REPORT_SEPARATOR = "\n---REPORT---\n"
_SINGLE_PASS_SYSTEM_PROMPT = """你是一位专业反诈分析助手。必须低延迟输出，禁止寒暄、推理过程、解释协议。

第一批输出必须立刻给出 5 行元数据（严格使用以下英文键名，每个键单独一行）：
RISK_SCORE: <0-100整数>
RISK_LEVEL: <low|medium|high>
SCAM_TYPE: <诈骗类型名称>
GUARDIAN_ALERT: <true|false>
WARNING_MESSAGE: <一句话风险提醒>

然后单独输出一行分隔符：
---REPORT---

分隔符后直接输出 Markdown 正文报告，要求：
1. 用中文输出
2. 短报告优先，包含风险结论、关键线索、建议操作
3. 禁止再次输出 RISK_SCORE 等元数据键
4. 如果信息不足，明确标注不确定性并给出保守建议
5. 不要输出“正在分析”等过渡文本，报告正文从结论开始"""


_SINGLE_PASS_SYSTEM_PROMPT_PRO = """你是一位专业反诈分析助手。输出要准确、结构化、可执行，禁止寒暄和思维过程暴露。
第一段必须先输出 5 行元数据（每行一个键）：
RISK_SCORE: <0-100整数>
RISK_LEVEL: <low|medium|high>
SCAM_TYPE: <诈骗类型名称>
GUARDIAN_ALERT: <true|false>
WARNING_MESSAGE: <一句话风险提醒>

然后单独输出一行分隔符：
---REPORT---

分隔符后输出中文 Markdown 报告，要求：
1. 先给风险结论，再给关键依据，再给操作建议
2. 给出保守且可执行的行动项（优先防止资金损失）
3. 不要重复输出元数据键
4. 信息不足时必须明确不确定性
5. 不要输出“正在分析”等过渡语
"""

_SINGLE_PASS_SYSTEM_PROMPT_FLASH = """你是低延迟反诈分析助手，目标是尽快给出可执行结论。禁止寒暄、解释协议或推理过程。
先输出 5 行元数据（每行一个键）：
RISK_SCORE: <0-100整数>
RISK_LEVEL: <low|medium|high>
SCAM_TYPE: <诈骗类型名称>
GUARDIAN_ALERT: <true|false>
WARNING_MESSAGE: <一句话风险提醒>

然后输出分隔符：
---REPORT---

分隔符后直接输出中文 Markdown 短报告，优先：
1. 风险结论（先结论）
2. 关键线索（最多3点）
3. 立即操作（最多3条，简洁）
不要重复元数据字段，不要过渡语。
"""


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
_MODEL_MODES = {"pro", "flash"}


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


def _get_model_mode() -> str:
    raw = os.getenv("MODEL_MODE", "flash")
    normalized = raw.strip().lower()
    if normalized in _MODEL_MODES:
        return normalized
    if normalized == "unified":
        return "pro"
    return "flash"


def _can_use_single_pass_for_input(has_media: bool, has_audio: bool, has_video: bool, has_image: bool) -> bool:
    # flash mode now supports all input combinations, including audio/video.
    return True


def _should_use_single_pass(mode: str, has_media: bool, has_audio: bool, has_video: bool, has_image: bool) -> bool:
    if mode != "flash":
        return False
    return _can_use_single_pass_for_input(
        has_media=has_media,
        has_audio=has_audio,
        has_video=has_video,
        has_image=has_image,
    )


def _get_single_pass_system_prompt(mode: str) -> str:
    if mode == "pro":
        return _SINGLE_PASS_SYSTEM_PROMPT_PRO
    return _SINGLE_PASS_SYSTEM_PROMPT_FLASH


def _is_ollama_native_streaming_enabled(base_url: str) -> bool:
    raw = os.getenv("FRAUD_OLLAMA_NATIVE_STREAMING")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    normalized = (base_url or "").lower()
    return "11434" in normalized or "ollama" in normalized


def _ollama_api_chat_url(base_url: str) -> str:
    normalized = (base_url or "http://127.0.0.1:11434").rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    return f"{normalized}/api/chat"


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


def _trim_prompt_text(value: Any, max_chars: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _format_rag_context_for_prompt(early_warning: Optional[dict], max_items: int = 4) -> str:
    rag_items = list((early_warning or {}).get("rag_context") or [])
    if not rag_items:
        return "- none"

    lines: list[str] = []
    for index, item in enumerate(rag_items[:max_items], start=1):
        title = _trim_prompt_text(item.get("title") or "untitled", 120)
        content = _trim_prompt_text(item.get("content") or item.get("text") or "", 420)
        source = _trim_prompt_text(item.get("source") or "", 120)
        similarity = item.get("similarity", item.get("score", ""))
        subtype = _trim_prompt_text(item.get("subtype") or "", 80)
        tags = item.get("tags") or []
        if isinstance(tags, list):
            tags_text = ", ".join(str(tag) for tag in tags[:5])
        else:
            tags_text = str(tags)

        meta_parts = []
        if similarity != "":
            try:
                meta_parts.append(f"similarity={float(similarity):.3f}")
            except (TypeError, ValueError):
                meta_parts.append(f"similarity={similarity}")
        if subtype:
            meta_parts.append(f"subtype={subtype}")
        if tags_text:
            meta_parts.append(f"tags={tags_text}")
        if source:
            meta_parts.append(f"source={source}")

        meta = f" ({'; '.join(meta_parts)})" if meta_parts else ""
        lines.append(f"{index}. {title}{meta}\n   excerpt: {content or 'none'}")

    return "\n".join(lines)


def _epoch_ms() -> int:
    return int(time() * 1000)


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


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
        user_role=normalize_user_role(str(current_user.user_role or "general")),
        short_term_events=recent_detections,
        history_profile=history_profile,
        age_group=str(getattr(current_user, "age_group", "unknown") or "unknown"),
        gender=str(getattr(current_user, "gender", "unknown") or "unknown"),
        occupation=str(getattr(current_user, "occupation", "other") or "other"),
    )

    return {
        "short_term_memory_summary": short_term_memory_summary,
        "long_term_memory_summary": long_term_memory_summary,
        "combined_profile_text": format_combined_profile_text(
            str(getattr(current_user, "age_group", "unknown") or "unknown"),
            str(getattr(current_user, "gender", "unknown") or "unknown"),
            str(getattr(current_user, "occupation", "other") or "other"),
            fallback_role=str(current_user.user_role or "general"),
        ),
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
    combined_profile_text = str(memory_context.get("combined_profile_text") or "none")

    warning_source = str((early_warning or {}).get("source", "")).strip()
    warning_score = int((early_warning or {}).get("risk_score", 0))
    if warning_source in {"fast_fallback", "media_ai_pending"}:
        warning_score_text = "未命中高危规则；该快速预警分数只是兜底占位，不作为LLM评分依据"
    else:
        warning_score_text = str(warning_score)
    warning_score = warning_score_text
    warning_level = str((early_warning or {}).get("risk_level", "low")).lower()
    warning_text = str((early_warning or {}).get("warning_message", "")).strip()
    warning_clues = list((early_warning or {}).get("risk_clues") or [])
    rag_context_text = _format_rag_context_for_prompt(early_warning)
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
        f"组合画像:\n{combined_profile_text}\n"
        f"{media_hint}\n"
        f"快速预警分数: {warning_score}\n"
        f"快速预警等级: {warning_level}\n"
        f"快速预警提示: {warning_text or '无'}\n"
        f"快速预警线索:\n{warning_clues_text}\n\n"
        "RAG similar cases / knowledge snippets:\n"
        f"{rag_context_text}\n\n"
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
        "Score instruction: decide RISK_SCORE primarily by your own semantic assessment of the original input, OCR text, "
        "RAG snippets, and user context. Fast warning is only supporting evidence, not a score baseline.\n"
        "For clearly low-risk/general inquiry content with no warning evidence, choose a score in 0-15 based on the actual content; "
        "do not always output 6.\n"
        "请以你对原始输入、OCR文本、RAG片段和用户上下文的语义判断为主进行评分；快速预警只是参考证据，"
        "不是分数基线，也不能直接决定最终分数。\n"
        "若无明显风险，请在 0-15 内按文本实际内容给分，而不是固定输出 6。\n"
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
        maybe_metadata = _parse_single_pass_metadata(normalized)
        if maybe_metadata:
            header_text = normalized
            report_lines = []
            for line in normalized.splitlines():
                if re.match(
                    r"^\s*(RISK_SCORE|RISK_LEVEL|SCAM_TYPE|GUARDIAN_ALERT|WARNING_MESSAGE)\s*:",
                    line,
                    re.IGNORECASE,
                ):
                    continue
                if line.strip() == "---REPORT---":
                    continue
                report_lines.append(line)
            report_text = "\n".join(report_lines)
        else:
            header_text, report_text = "", normalized

    score_match = re.search(r"RISK_SCORE\s*:\s*(\d{1,3})", header_text, re.IGNORECASE)
    level_match = re.search(r"RISK_LEVEL\s*:\s*(low|medium|high)", header_text, re.IGNORECASE)
    scam_type_match = re.search(r"SCAM_TYPE\s*:\s*(.+)", header_text, re.IGNORECASE)
    guardian_alert_match = re.search(r"GUARDIAN_ALERT\s*:\s*(.+)", header_text, re.IGNORECASE)
    warning_message_match = re.search(r"WARNING_MESSAGE\s*:\s*(.+)", header_text, re.IGNORECASE)

    has_llm_risk_score = score_match is not None
    fallback_score = int((early_warning or {}).get("risk_score", 0))
    parsed_score = int(score_match.group(1)) if has_llm_risk_score else fallback_score
    risk_score = _clamp_risk_score(parsed_score)
    raw_llm_risk_score = risk_score if has_llm_risk_score else None

    low_threshold = _safe_int(dynamic_thresholds.get("low_threshold"), 40)
    high_threshold = _safe_int(dynamic_thresholds.get("high_threshold"), 75)
    score_based_level = _risk_level_from_score(
        risk_score,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
    )

    fallback_level = _normalize_level(
        str((early_warning or {}).get("risk_level", "")),
        risk_score,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
    )
    parsed_level = (level_match.group(1).lower() if level_match else "")
    if has_llm_risk_score:
        risk_level = score_based_level
    else:
        risk_level = _max_level(parsed_level, fallback_level)

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
        "llm_risk_score": raw_llm_risk_score,
        "llm_risk_score_available": has_llm_risk_score,
        "score_source": "single_pass_llm" if has_llm_risk_score else "early_warning_fallback",
        "early_warning_score": fallback_score,
        "early_warning_level": fallback_level,
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
        "similar_cases": list(
            (early_warning or {}).get("similar_cases")
            or (early_warning or {}).get("rag_context")
            or []
        ),
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

    model_config = _get_single_pass_model_config()
    model_name = model_config["model"]
    base_url = model_config["base_url"]

    _SINGLE_PASS_FRAUD_LLM = ChatOpenAI(
        model=model_name,
        temperature=float(model_config.get("temperature", 0.0)),
        max_tokens=int(model_config.get("max_tokens", 1800)),
        timeout=int(model_config.get("timeout", 60)),
        api_key=api_key,
        base_url=base_url,
    )
    return _SINGLE_PASS_FRAUD_LLM


def _get_single_pass_model_config() -> dict[str, Any]:
    config = load_node_config("report_generation")
    nested_config = config.get("config") if isinstance(config.get("config"), dict) else {}
    model_name = (
        os.getenv("FRAUD_REPORT_MODEL")
        or config.get("model")
        or nested_config.get("model")
        or os.getenv("LLM_MODEL", "moonshot-v1-8k")
    )
    base_url = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
    max_tokens = (
        config.get("max_tokens")
        or nested_config.get("max_tokens")
        or nested_config.get("max_completion_tokens")
        or 1800
    )
    temperature = float(os.getenv("FRAUD_SINGLE_PASS_TEMPERATURE", "0.0"))
    return {
        "model": model_name,
        "base_url": base_url,
        "temperature": temperature,
        "max_tokens": int(max_tokens),
        "timeout": int(config.get("timeout", nested_config.get("timeout", 60))),
    }


async def _stream_single_pass_chunks(
    messages: list[Any],
    model_config: dict[str, Any],
    system_prompt: str,
):
    base_url = str(model_config.get("base_url") or "")
    model_name = str(model_config.get("model") or "")
    use_ollama_native = _is_ollama_native_streaming_enabled(base_url)

    if use_ollama_native:
        options: dict[str, Any] = {
            "temperature": float(model_config.get("temperature", 0.0)),
            "num_predict": int(model_config.get("max_tokens", 1800)),
        }
        for env_name, option_name in [
            ("OLLAMA_NUM_CTX", "num_ctx"),
            ("OLLAMA_NUM_THREAD", "num_thread"),
            ("OLLAMA_NUM_GPU", "num_gpu"),
        ]:
            raw_value = os.getenv(env_name)
            if raw_value:
                try:
                    options[option_name] = int(raw_value)
                except ValueError:
                    pass

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(getattr(messages[1], "content", ""))},
            ],
            "stream": True,
            "options": options,
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
        }
        if os.getenv("OLLAMA_THINK", "false").strip().lower() in {"0", "false", "no", "off"}:
            payload["think"] = False
        timeout = httpx.Timeout(
            connect=5.0,
            read=float(model_config.get("timeout", 60)) + 30.0,
            write=10.0,
            pool=5.0,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", _ollama_api_chat_url(base_url), json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if item.get("done"):
                        break
                    content = ((item.get("message") or {}).get("content") or item.get("response") or "")
                    if content:
                        yield str(content), "ollama_native"
        return

    llm = _get_single_pass_fraud_llm()
    if llm is None:
        raise RuntimeError("LLM API key 未配置，无法启用单次流式分析")

    async for chunk in llm.astream(messages):
        chunk_text = _extract_llm_chunk_text(getattr(chunk, "content", ""))
        if chunk_text:
            yield chunk_text, "langchain_openai"


def _parse_single_pass_metadata(header_text: str) -> dict[str, Any]:
    score_match = re.search(r"RISK_SCORE\s*:\s*(\d{1,3})", header_text, re.IGNORECASE)
    level_match = re.search(r"RISK_LEVEL\s*:\s*(low|medium|high)", header_text, re.IGNORECASE)
    scam_type_match = re.search(r"SCAM_TYPE\s*:\s*([^\n\r]+)", header_text, re.IGNORECASE)
    guardian_alert_match = re.search(r"GUARDIAN_ALERT\s*:\s*([^\n\r]+)", header_text, re.IGNORECASE)
    warning_message_match = re.search(r"WARNING_MESSAGE\s*:\s*([^\n\r]+)", header_text, re.IGNORECASE)

    metadata: dict[str, Any] = {}
    if score_match:
        metadata["risk_score"] = _clamp_risk_score(int(score_match.group(1)))
    if level_match:
        metadata["risk_level"] = level_match.group(1).lower()
    if scam_type_match:
        metadata["scam_type"] = scam_type_match.group(1).strip()
    if guardian_alert_match:
        metadata["guardian_alert"] = _parse_bool(guardian_alert_match.group(1).strip())
    if warning_message_match:
        metadata["warning_message"] = warning_message_match.group(1).strip()
    return metadata


async def _run_single_pass_detection_stream(
    task_id: str,
    message: str,
    user_role: str,
    early_warning: Optional[dict],
    has_media: bool,
    model_mode: str,
    memory_context: Optional[dict[str, Any]] = None,
    dynamic_thresholds: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], int]:
    total_started_at = perf_counter()
    model_config = _get_single_pass_model_config()
    if not _is_ollama_native_streaming_enabled(str(model_config.get("base_url") or "")):
        llm = _get_single_pass_fraud_llm()
        if llm is None:
            raise RuntimeError("LLM API key 未配置，无法启用单次流式分析")

    prompt_started_at = perf_counter()
    user_prompt = _build_single_pass_user_prompt(
        message=message,
        user_role=user_role,
        early_warning=early_warning,
        has_media=has_media,
        memory_context=memory_context,
        dynamic_thresholds=dynamic_thresholds,
    )
    system_prompt = _get_single_pass_system_prompt(model_mode)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    prompt_prepare_ms = _elapsed_ms(prompt_started_at)

    task_manager.publish_task_event(task_id, {"event": "report_stream_started", "stream_mode": "token"})

    raw_parts: list[str] = []
    buffered_prefix = ""
    marker_seen = False
    chunk_count = 0
    llm_started_at = perf_counter()
    first_raw_chunk_ms = None
    first_report_chunk_ms = None
    first_llm_score_ms = None
    llm_metadata: dict[str, Any] = {}
    published_metadata: dict[str, Any] = {}
    stream_backend = "unknown"

    def publish_metadata_if_changed(force: bool = False) -> None:
        nonlocal first_llm_score_ms
        if "risk_score" in llm_metadata and first_llm_score_ms is None:
            first_llm_score_ms = _elapsed_ms(llm_started_at)

        changed = force or any(published_metadata.get(key) != value for key, value in llm_metadata.items())
        if not changed or "risk_score" not in llm_metadata:
            return

        published_metadata.update(llm_metadata)
        task_manager.publish_task_event(
            task_id,
            {
                "event": "llm_risk_update",
                **llm_metadata,
                "is_preliminary": True,
            },
        )

    async for chunk_text, backend_name in _stream_single_pass_chunks(messages, model_config, system_prompt):
        stream_backend = backend_name
        if not chunk_text:
            continue

        if first_raw_chunk_ms is None:
            first_raw_chunk_ms = _elapsed_ms(llm_started_at)

        raw_parts.append(chunk_text)

        if marker_seen:
            chunk_count += 1
            if first_report_chunk_ms is None:
                first_report_chunk_ms = _elapsed_ms(llm_started_at)
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
        llm_metadata.update(_parse_single_pass_metadata(buffered_prefix))
        publish_metadata_if_changed()

        marker_index = buffered_prefix.find(_SINGLE_PASS_REPORT_SEPARATOR)
        if marker_index >= 0:
            marker_seen = True
            llm_metadata.update(_parse_single_pass_metadata(buffered_prefix[:marker_index]))
            publish_metadata_if_changed(force=True)
            report_text_after_marker = buffered_prefix[marker_index + len(_SINGLE_PASS_REPORT_SEPARATOR):]
            buffered_prefix = ""
            if report_text_after_marker:
                chunk_count += 1
                if first_report_chunk_ms is None:
                    first_report_chunk_ms = _elapsed_ms(llm_started_at)
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

        metadata_complete = all(
            key in llm_metadata
            for key in ["risk_score", "risk_level", "scam_type", "guardian_alert", "warning_message"]
        )
        if metadata_complete:
            lines = buffered_prefix.splitlines(keepends=True)
            metadata_line_count = 0
            for line in lines:
                if re.match(
                    r"^\s*(RISK_SCORE|RISK_LEVEL|SCAM_TYPE|GUARDIAN_ALERT|WARNING_MESSAGE)\s*:",
                    line,
                    re.IGNORECASE,
                ):
                    metadata_line_count += 1
                    continue
                if not line.strip() or line.strip() == "---REPORT---":
                    metadata_line_count += 1
                    continue
                break

            report_candidate = "".join(lines[metadata_line_count:]).lstrip()
            if report_candidate:
                marker_seen = True
                buffered_prefix = ""
                chunk_count += 1
                if first_report_chunk_ms is None:
                    first_report_chunk_ms = _elapsed_ms(llm_started_at)
                task_manager.publish_task_event(
                    task_id,
                    {
                        "event": "report_chunk",
                        "chunk": report_candidate,
                        "chunk_index": chunk_count,
                    },
                )
                task_manager.update_task_progress(task_id, min(94, 40 + int(chunk_count * 1.5)))
                continue

        # Fail-safe: if the model does not follow the separator protocol, expose output after a small buffer.
        if len(buffered_prefix) > 360 and ("risk_score" not in llm_metadata or len(buffered_prefix) > 900):
            marker_seen = True
            chunk_count += 1
            if first_report_chunk_ms is None:
                first_report_chunk_ms = _elapsed_ms(llm_started_at)
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
    parsed_result["performance_timing"] = {
        "report_prompt_prepare_ms": prompt_prepare_ms,
        "report_llm_prompt_chars": len(system_prompt) + len(user_prompt),
        "report_llm_first_raw_chunk_ms": first_raw_chunk_ms,
        "report_llm_first_score_ms": first_llm_score_ms,
        "report_llm_first_report_chunk_ms": first_report_chunk_ms,
        "report_llm_api_roundtrip_ms": _elapsed_ms(llm_started_at),
        "report_llm_total_ms": _elapsed_ms(total_started_at),
        "report_llm_model": str(model_config.get("model") or ""),
        "report_llm_stream_backend": stream_backend,
        "report_llm_output_chars": len(raw_output),
        "single_pass_stream_mode": True,
        "single_pass_prompt_mode": model_mode,
    }

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

    rag_context = []
    for case in retrieved_cases[:top_k]:
        rag_context.append(
            {
                "case_id": str(getattr(case, "case_id", "")),
                "title": str(getattr(case, "title", "")),
                "content": str(getattr(case, "content", "")),
                "similarity": float(getattr(case, "similarity", 0.0) or 0.0),
                "source": str(getattr(case, "source", "")),
                "subtype": str(getattr(case, "subtype", "") or ""),
                "tags": list(getattr(case, "tags", []) or []),
            }
        )

    return {
        "risk_score": min(rag_score, 99),
        "risk_level": rag_level,
        "risk_clues": clues[:6],
        "warning_message": warning_message,
        "source": "fast_rag_probe",
        "is_preliminary": True,
        "rag_context": rag_context,
        "similar_cases": rag_context,
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
            "rag_context": list(rag_warning.get("rag_context") or []),
            "similar_cases": list(rag_warning.get("similar_cases") or rag_warning.get("rag_context") or []),
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

    education_fee_signal = any("教育缴费" in clue or "冒充学校" in clue for clue in clues)
    hard_high_risk_signal = any(
        marker in clue
        for clue in clues
        for marker in ["立即转账", "验证码", "公检法", "远程控制", "安全账户"]
    )
    if education_fee_signal and not hard_high_risk_signal:
        score = min(max(score, 68), 76)

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


def _compress_temp_image(image_path: str) -> str:
    try:
        from PIL import Image, ImageOps
    except Exception as exc:
        print(f"[image] Pillow unavailable, skip compression: {exc}")
        return image_path

    try:
        max_edge = int(os.getenv("FRAUD_IMAGE_MAX_EDGE", "1600"))
        jpeg_quality = int(os.getenv("FRAUD_IMAGE_JPEG_QUALITY", "78"))
    except (TypeError, ValueError):
        max_edge = 1600
        jpeg_quality = 78

    try:
        original_size = os.path.getsize(image_path)
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

            if image.mode not in ("RGB", "L"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
            elif image.mode != "RGB":
                image = image.convert("RGB")

            compressed_path = f"{Path(image_path).with_suffix('')}_compressed.jpg"
            image.save(
                compressed_path,
                format="JPEG",
                quality=max(40, min(95, jpeg_quality)),
                optimize=True,
                progressive=True,
            )

        compressed_size = os.path.getsize(compressed_path)
        if compressed_size < original_size * 0.95:
            try:
                os.remove(image_path)
            except OSError:
                pass
            return compressed_path

        try:
            os.remove(compressed_path)
        except OSError:
            pass
        return image_path
    except Exception as exc:
        print(f"[image] compression failed, use original: {exc}")
        return image_path


def _save_temp_file(upload_file: UploadFile, preprocess_image: bool = False) -> str:
    temp_dir = tempfile.gettempdir()
    suffix = Path(upload_file.filename).suffix if upload_file.filename else ""
    temp_filename = f"{uuid.uuid4().hex}{suffix}"
    temp_path = os.path.join(temp_dir, temp_filename)
    with open(temp_path, "wb") as file_obj:
        file_obj.write(upload_file.file.read())
    upload_file.file.seek(0)
    if preprocess_image:
        return _compress_temp_image(temp_path)
    return temp_path


def _save_uploads_with_timing(
    audio_file: Optional[UploadFile],
    image_file: Optional[UploadFile],
    video_file: Optional[UploadFile],
) -> tuple[Optional[str], Optional[str], Optional[str], dict[str, Any]]:
    timing: dict[str, Any] = {}

    audio_path = None
    if audio_file:
        started_at = perf_counter()
        audio_path = _save_temp_file(audio_file)
        timing["audio_upload_save_ms"] = _elapsed_ms(started_at)

    image_path = None
    if image_file:
        started_at = perf_counter()
        image_path = _save_temp_file(image_file, preprocess_image=True)
        timing["image_upload_save_preprocess_ms"] = _elapsed_ms(started_at)
        try:
            timing["image_temp_size_bytes"] = os.path.getsize(image_path)
        except OSError:
            pass

    video_path = None
    if video_file:
        started_at = perf_counter()
        video_path = _save_temp_file(video_file)
        timing["video_upload_save_ms"] = _elapsed_ms(started_at)

    return audio_path, image_path, video_path, timing


def _merge_image_ocr_timing(performance_timing: dict[str, Any], metadata: dict[str, Any]) -> None:
    if "ocr_total_ms" in metadata:
        performance_timing["ocr_image_to_text_ms"] = metadata.get("ocr_total_ms")
    if "ocr_engine_ms" in metadata:
        performance_timing["ocr_engine_ms"] = metadata.get("ocr_engine_ms")
    if "image_fake_analysis_ms" in metadata:
        performance_timing["image_fake_analysis_ms"] = metadata.get("image_fake_analysis_ms")
    performance_timing["ocr_text_length"] = metadata.get("ocr_text_length", 0)
    performance_timing["ocr_skipped_due_to_high_ai_rate"] = bool(
        metadata.get("ocr_skipped_due_to_high_ai_rate", False)
    )


def _build_media_fake_warning(modality: str, fake_probability: Optional[float]) -> Optional[dict[str, Any]]:
    if fake_probability is None:
        return None

    probability = max(0.0, min(1.0, float(fake_probability)))
    if probability < 0.30:
        return None

    score = _clamp_risk_score(int(round(probability * 100)))
    if probability >= 0.82:
        level = "high"
        score = max(score, 82)
        warning_message = f"{modality}疑似AI伪造概率为 {probability:.0%}，请立即暂停转账并进行人工核验。"
    elif probability >= 0.60:
        level = "medium"
        score = max(score, 52)
        warning_message = f"{modality}存在AI伪造风险（{probability:.0%}），建议先核验来源再执行敏感操作。"
    else:
        level = "low"
        warning_message = f"{modality}检测到一定伪造风险（{probability:.0%}），请保持谨慎。"

    return {
        "risk_score": score,
        "risk_level": level,
        "risk_clues": [f"{modality}AI伪造概率: {probability:.0%}"],
        "warning_message": warning_message,
        "source": f"fast_{modality}_ai_probe",
        "is_preliminary": True,
        "ai_fake_probability": probability,
    }


def _merge_warning_with_media_warnings(
    base_warning: Optional[dict[str, Any]],
    media_warnings: list[Optional[dict[str, Any]]],
) -> Optional[dict[str, Any]]:
    merged_media_warnings = [item for item in media_warnings if item]
    if not merged_media_warnings:
        return base_warning

    if base_warning is None:
        base_warning = {
            "risk_score": 0,
            "risk_level": "low",
            "risk_clues": [],
            "warning_message": "",
            "source": "media_fusion",
            "is_preliminary": True,
        }

    merged = dict(base_warning)
    merged_score = int(merged.get("risk_score", 0) or 0)
    merged_level = str(merged.get("risk_level", "low") or "low")
    merged_clues = list(merged.get("risk_clues") or [])
    merged_message = str(merged.get("warning_message", "") or "").strip()

    for media_warning in merged_media_warnings:
        merged_score = max(merged_score, int(media_warning.get("risk_score", 0) or 0))
        merged_level = _max_level(merged_level, str(media_warning.get("risk_level", "low") or "low"))
        merged_clues.extend(list(media_warning.get("risk_clues") or []))
        media_message = str(media_warning.get("warning_message", "") or "").strip()
        if media_message and media_message not in merged_message:
            merged_message = f"{media_message} {merged_message}".strip()

    if merged_level == "high":
        merged_score = max(merged_score, 82)
    elif merged_level == "medium":
        merged_score = max(merged_score, 52)

    merged.update(
        {
            "risk_score": _clamp_risk_score(merged_score),
            "risk_level": merged_level,
            "risk_clues": list(dict.fromkeys(merged_clues))[:10],
            "warning_message": merged_message,
            "source": f"{str(merged.get('source', 'warning') or 'warning')}_media_fusion",
            "is_preliminary": True,
        }
    )
    return merged


async def _extract_image_text_for_single_pass(
    image_path: str,
    performance_timing: dict[str, Any],
    image_ai_warning: Optional[dict] = None,
    task_id: Optional[str] = None,
) -> str:
    """Run the same perception OCR path, then feed only text into single-pass LLM."""
    perception_started_at = perf_counter()
    manager = get_perception_manager()
    context = ProcessingContext(
        task_id=task_id,
        metadata={
            "prefer_ai_rate_early_warning": False,
            "image_ai_probability": (image_ai_warning or {}).get("image_ai_probability"),
            "image_ai_risk_level": (image_ai_warning or {}).get("risk_level"),
            "image_ai_ocr_skip_threshold": (image_ai_warning or {}).get("image_ai_ocr_skip_threshold", 0.74),
        },
    )
    result = await manager.process_single(
        MediaFile(type=MediaType.IMAGE, url=image_path),
        context=context,
    )
    metadata = dict(result.metadata or {})
    performance_timing["perception_total_ms"] = _elapsed_ms(perception_started_at)
    _merge_image_ocr_timing(performance_timing, metadata)
    print(
        "[OCR] image received-to-text "
        f"{performance_timing.get('ocr_image_to_text_ms', performance_timing['perception_total_ms'])} ms; "
        f"engine {performance_timing.get('ocr_engine_ms', 'n/a')} ms; "
        f"text_len {len(result.text_content or '')}"
    )
    return (result.text_content or "").strip()


async def _extract_audio_text_for_single_pass(
    audio_path: str,
    performance_timing: dict[str, Any],
    task_id: Optional[str] = None,
) -> tuple[str, Optional[dict[str, Any]]]:
    perception_started_at = perf_counter()
    manager = get_perception_manager()
    context = ProcessingContext(task_id=task_id, metadata={})
    result = await manager.process_single(
        MediaFile(type=MediaType.AUDIO, url=audio_path),
        context=context,
    )
    performance_timing["audio_perception_total_ms"] = _elapsed_ms(perception_started_at)
    performance_timing["audio_asr_text_length"] = len(result.text_content or "")
    performance_timing["audio_asr_available"] = bool((result.metadata or {}).get("asr_available", False))

    fake_probability = None
    if result.fake_analysis is not None:
        fake_probability = float(result.fake_analysis.fake_probability)
        performance_timing["audio_fake_probability"] = fake_probability

    warning = _build_media_fake_warning("音频", fake_probability)
    return (result.text_content or "").strip(), warning


async def _extract_video_text_for_single_pass(
    video_path: str,
    performance_timing: dict[str, Any],
    task_id: Optional[str] = None,
) -> tuple[str, Optional[dict[str, Any]]]:
    perception_started_at = perf_counter()
    manager = get_perception_manager()
    context = ProcessingContext(task_id=task_id, metadata={})
    result = await manager.process_single(
        MediaFile(type=MediaType.VIDEO, url=video_path),
        context=context,
    )
    performance_timing["video_perception_total_ms"] = _elapsed_ms(perception_started_at)
    performance_timing["video_ocr_text_length"] = len(result.text_content or "")
    performance_timing["video_keyframe_count"] = int((result.metadata or {}).get("keyframe_count", 0) or 0)

    fake_probability = None
    if result.fake_analysis is not None:
        fake_probability = float(result.fake_analysis.fake_probability)
        performance_timing["video_fake_probability"] = fake_probability

    warning = _build_media_fake_warning("视频", fake_probability)
    return (result.text_content or "").strip(), warning


def _build_single_pass_message_with_multimodal(
    message: str,
    ocr_text: str = "",
    audio_text: str = "",
    video_text: str = "",
) -> str:
    base_text = (message or "").strip()
    sections: list[str] = [base_text] if base_text else []

    normalized_audio = (audio_text or "").strip()
    if normalized_audio:
        sections.append(f"[音频转写文本]\n{normalized_audio}")

    normalized_ocr = (ocr_text or "").strip()
    if normalized_ocr:
        sections.append(f"[图片OCR识别文本]\n{normalized_ocr}")

    normalized_video = (video_text or "").strip()
    if normalized_video:
        sections.append(f"[视频抽帧OCR文本]\n{normalized_video}")

    return "\n\n".join([item for item in sections if item]).strip()


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
        "llm_risk_score": result.get("llm_risk_score"),
        "llm_risk_score_available": bool(result.get("llm_risk_score_available", False)),
        "score_source": result.get("score_source"),
        "early_warning_score": result.get("early_warning_score"),
        "early_warning_level": result.get("early_warning_level"),
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
        "performance_timing": result.get("performance_timing", {}),
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
    client_request_started_at_ms: Optional[float] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    temp_files = []
    started_at = perf_counter()
    server_handler_epoch_ms = _epoch_ms()
    request_success = False
    error_message = None
    has_media = bool(audio_file or image_file or video_file)
    model_mode = _get_model_mode()
    use_single_pass = _should_use_single_pass(
        mode=model_mode,
        has_media=has_media,
        has_audio=bool(audio_file),
        has_video=bool(video_file),
        has_image=bool(image_file),
    )
    monitor_model_name = "fraud_detection_single_pass" if use_single_pass else "fraud_detection_graph"
    performance_timing: dict[str, Any] = {
        "server_handler_started_epoch_ms": server_handler_epoch_ms,
        "model_mode": model_mode,
    }
    if client_request_started_at_ms:
        performance_timing["client_to_backend_handler_ms_clock_based"] = round(
            server_handler_epoch_ms - float(client_request_started_at_ms),
            2,
        )

    try:
        audio_path, image_path, video_path, upload_timing = _save_uploads_with_timing(
            audio_file,
            image_file,
            video_file,
        )
        performance_timing.update(upload_timing)
        temp_files = [path for path in [audio_path, image_path, video_path] if path]

        contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
        guardian_contact = next((contact for contact in contacts if contact.is_guardian), None)
        memory_context = _build_user_memory_context(db, current_user, message)

        image_ai_warning = None
        if image_path:
            try:
                image_ai_started_at = perf_counter()
                image_ai_warning = await asyncio.wait_for(
                    _build_fast_image_ai_warning(image_path),
                    timeout=1.2,
                )
                performance_timing["early_image_ai_warning_ms"] = _elapsed_ms(image_ai_started_at)
            except asyncio.TimeoutError:
                performance_timing["early_image_ai_warning_timeout_ms"] = 1200
            except Exception as exc:
                performance_timing["early_image_ai_warning_error"] = str(exc)

        if use_single_pass:
            single_pass_message = message
            ocr_text = ""
            audio_text = ""
            video_text = ""
            media_warnings: list[Optional[dict[str, Any]]] = []

            extraction_keys: list[str] = []
            extraction_tasks: list[asyncio.Task] = []
            if image_path:
                extraction_keys.append("image")
                extraction_tasks.append(
                    asyncio.create_task(
                        _extract_image_text_for_single_pass(
                            image_path=image_path,
                            performance_timing=performance_timing,
                            image_ai_warning=image_ai_warning,
                        )
                    )
                )
            if audio_path:
                extraction_keys.append("audio")
                extraction_tasks.append(
                    asyncio.create_task(
                        _extract_audio_text_for_single_pass(
                            audio_path=audio_path,
                            performance_timing=performance_timing,
                        )
                    )
                )
            if video_path:
                extraction_keys.append("video")
                extraction_tasks.append(
                    asyncio.create_task(
                        _extract_video_text_for_single_pass(
                            video_path=video_path,
                            performance_timing=performance_timing,
                        )
                    )
                )

            if extraction_tasks:
                extracted_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
                for key, extracted in zip(extraction_keys, extracted_results):
                    if isinstance(extracted, Exception):
                        performance_timing[f"{key}_single_pass_extract_error"] = str(extracted)
                        continue
                    if key == "image":
                        ocr_text = str(extracted or "")
                    elif key == "audio":
                        audio_text, audio_warning = extracted
                        media_warnings.append(audio_warning)
                    elif key == "video":
                        video_text, video_warning = extracted
                        media_warnings.append(video_warning)

            single_pass_message = _build_single_pass_message_with_multimodal(
                message=message,
                ocr_text=ocr_text,
                audio_text=audio_text,
                video_text=video_text,
            )
            fallback_warning = await _build_fast_early_warning(
                single_pass_message,
                has_media=has_media,
                image_ai_warning=image_ai_warning,
            )
            fallback_warning = _merge_warning_with_media_warnings(fallback_warning, media_warnings)
            result, _ = await _run_single_pass_detection_stream(
                task_id=f"sync_{uuid.uuid4().hex[:12]}",
                message=single_pass_message,
                user_role=normalize_user_role(current_user.user_role),
                early_warning=fallback_warning,
                has_media=has_media,
                model_mode=model_mode,
                memory_context=memory_context,
                dynamic_thresholds=memory_context.get("dynamic_thresholds"),
            )
            result["performance_timing"] = {
                **performance_timing,
                **dict(result.get("performance_timing") or {}),
            }
        else:
            workflow_options = {
                "prefer_ai_rate_early_warning": bool(image_path),
                "image_ai_ocr_skip_threshold": 0.74,
                "language": str(getattr(current_user, "language", "zh-CN") or "zh-CN"),
                "age_group": str(getattr(current_user, "age_group", "unknown") or "unknown"),
                "gender": str(getattr(current_user, "gender", "unknown") or "unknown"),
                "occupation": str(getattr(current_user, "occupation", "other") or "other"),
                "combined_profile_text": str(memory_context.get("combined_profile_text") or ""),
                "performance_timing": performance_timing,
            }
            result = await graph_client.detect_fraud(
                text=message,
                audio_path=audio_path,
                image_path=image_path,
                video_path=video_path,
                user_role=normalize_user_role(current_user.user_role),
                guardian_name=(guardian_contact.name if guardian_contact else current_user.guardian_name),
                guardian_phone=(guardian_contact.phone if guardian_contact else None),
                emergency_contacts=_serialize_contacts(contacts),
                notify_enabled=current_user.notify_enabled,
                notify_guardian_alert=current_user.notify_guardian_alert,
                user_id=str(current_user.id),
                history_profile=memory_context.get("history_profile"),
                workflow_options=workflow_options,
            )
            result["performance_timing"] = {
                **performance_timing,
                **dict(result.get("performance_timing") or {}),
            }

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
        result["performance_timing"] = {
            **dict(result.get("performance_timing") or {}),
            "backend_sync_total_ms": _elapsed_ms(started_at),
        }
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
    client_request_started_at_ms: Optional[float] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    temp_files = []
    task = None
    endpoint_started_at = perf_counter()
    server_handler_epoch_ms = _epoch_ms()
    has_media = bool(audio_file or image_file or video_file)
    model_mode = _get_model_mode()
    use_single_pass = _should_use_single_pass(
        mode=model_mode,
        has_media=has_media,
        has_audio=bool(audio_file),
        has_video=bool(video_file),
        has_image=bool(image_file),
    )
    performance_timing: dict[str, Any] = {
        "server_handler_started_epoch_ms": server_handler_epoch_ms,
        "model_mode": model_mode,
    }
    if client_request_started_at_ms:
        performance_timing["client_to_backend_handler_ms_clock_based"] = round(
            server_handler_epoch_ms - float(client_request_started_at_ms),
            2,
        )

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
        user_role = normalize_user_role(current_user.user_role)
        fallback_guardian_name = current_user.guardian_name
        notify_enabled = current_user.notify_enabled
        notify_guardian_alert = current_user.notify_guardian_alert
        memory_context = _build_user_memory_context(db, current_user, message)

        audio_path, image_path, video_path, upload_timing = _save_uploads_with_timing(
            audio_file,
            image_file,
            video_file,
        )
        performance_timing.update(upload_timing)
        temp_files = [path for path in [audio_path, image_path, video_path] if path]
        task_manager.update_task_progress(task.task_id, 15)

        image_ai_warning = None
        if image_path:
            try:
                image_ai_started_at = perf_counter()
                image_ai_warning = await asyncio.wait_for(
                    _build_fast_image_ai_warning(image_path),
                    timeout=1.2,
                )
                performance_timing["early_image_ai_warning_ms"] = _elapsed_ms(image_ai_started_at)
            except asyncio.TimeoutError:
                performance_timing["early_image_ai_warning_timeout_ms"] = 1200
                print("[预警] 图片AI率快速检测超时，继续执行规则/RAG预警")
            except Exception as exc:
                performance_timing["early_image_ai_warning_error"] = str(exc)
                print(f"[预警] 图片AI率快速检测失败: {exc}")

        early_warning_started_at = perf_counter()
        early_warning = await _build_fast_early_warning(
            message,
            has_media=has_media,
            image_ai_warning=image_ai_warning,
        )
        performance_timing["early_warning_total_ms"] = _elapsed_ms(early_warning_started_at)

        workflow_options = {
            "prefer_ai_rate_early_warning": bool(
                (image_ai_warning or {}).get("prefer_ai_rate_early_warning", bool(image_path))
            ),
            "image_ai_probability": (image_ai_warning or {}).get("image_ai_probability"),
            "image_ai_risk_level": (image_ai_warning or {}).get("risk_level"),
            "image_ai_ocr_skip_threshold": (image_ai_warning or {}).get("image_ai_ocr_skip_threshold", 0.74),
            "language": str(getattr(current_user, "language", "zh-CN") or "zh-CN"),
            "age_group": str(getattr(current_user, "age_group", "unknown") or "unknown"),
            "gender": str(getattr(current_user, "gender", "unknown") or "unknown"),
            "occupation": str(getattr(current_user, "occupation", "other") or "other"),
            "combined_profile_text": str(memory_context.get("combined_profile_text") or ""),
            "performance_timing": performance_timing,
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
                    single_pass_message = message
                    llm_early_warning = early_warning
                    ocr_text = ""
                    audio_text = ""
                    video_text = ""
                    media_warnings: list[Optional[dict[str, Any]]] = []

                    extraction_keys: list[str] = []
                    extraction_tasks: list[asyncio.Task] = []
                    if image_path:
                        extraction_keys.append("image")
                        extraction_tasks.append(
                            asyncio.create_task(
                                _extract_image_text_for_single_pass(
                                    image_path=image_path,
                                    performance_timing=performance_timing,
                                    image_ai_warning=image_ai_warning,
                                    task_id=task.task_id,
                                )
                            )
                        )
                    if audio_path:
                        extraction_keys.append("audio")
                        extraction_tasks.append(
                            asyncio.create_task(
                                _extract_audio_text_for_single_pass(
                                    audio_path=audio_path,
                                    performance_timing=performance_timing,
                                    task_id=task.task_id,
                                )
                            )
                        )
                    if video_path:
                        extraction_keys.append("video")
                        extraction_tasks.append(
                            asyncio.create_task(
                                _extract_video_text_for_single_pass(
                                    video_path=video_path,
                                    performance_timing=performance_timing,
                                    task_id=task.task_id,
                                )
                            )
                        )

                    if extraction_tasks:
                        extracted_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
                        for key, extracted in zip(extraction_keys, extracted_results):
                            if isinstance(extracted, Exception):
                                performance_timing[f"{key}_single_pass_extract_error"] = str(extracted)
                                continue
                            if key == "image":
                                ocr_text = str(extracted or "")
                            elif key == "audio":
                                audio_text, audio_warning = extracted
                                media_warnings.append(audio_warning)
                            elif key == "video":
                                video_text, video_warning = extracted
                                media_warnings.append(video_warning)

                    single_pass_message = _build_single_pass_message_with_multimodal(
                        message=message,
                        ocr_text=ocr_text,
                        audio_text=audio_text,
                        video_text=video_text,
                    )
                    llm_early_warning = await _build_fast_early_warning(
                        single_pass_message,
                        has_media=has_media,
                        image_ai_warning=image_ai_warning,
                    )
                    llm_early_warning = _merge_warning_with_media_warnings(llm_early_warning, media_warnings)
                    result, total_chunks = await _run_single_pass_detection_stream(
                        task_id=task.task_id,
                        message=single_pass_message,
                        user_role=user_role,
                        early_warning=llm_early_warning,
                        has_media=has_media,
                        model_mode=model_mode,
                        memory_context=memory_context,
                        dynamic_thresholds=memory_context.get("dynamic_thresholds"),
                    )
                    result["performance_timing"] = {
                        **performance_timing,
                        **dict(result.get("performance_timing") or {}),
                    }
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
                    graph_streamed_chunks = 0

                    task_manager.publish_task_event(
                        task.task_id,
                        {
                            "event": "report_stream_started",
                            "stream_mode": "graph_live",
                        },
                    )

                    async def _publish_graph_stream_chunk(chunk: str) -> None:
                        nonlocal graph_streamed_chunks
                        if not chunk:
                            return
                        graph_streamed_chunks += 1
                        task_manager.publish_task_event(
                            task.task_id,
                            {
                                "event": "report_chunk",
                                "chunk": chunk,
                                "chunk_index": graph_streamed_chunks,
                            },
                        )
                        stream_progress = min(94, 78 + min(graph_streamed_chunks, 16))
                        task_manager.update_task_progress(task.task_id, stream_progress)

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
                        on_stream_chunk=_publish_graph_stream_chunk,
                    )
                    result["performance_timing"] = {
                        **performance_timing,
                        **dict(result.get("performance_timing") or {}),
                    }
                    task_snapshot = task_manager.get_task(task.task_id)
                    current_progress = int(task_snapshot.progress) if task_snapshot else 0
                    task_manager.update_task_progress(task.task_id, max(current_progress, 78))

                    detection_payload = _build_detection_payload(result)
                    total_chunks = graph_streamed_chunks
                    stream_mode = "graph_live"
                    if total_chunks <= 0:
                        report_chunks = _chunk_report_text(detection_payload.get("final_report", ""))
                        for chunk_index, chunk in enumerate(report_chunks, start=1):
                            task_manager.publish_task_event(
                                task.task_id,
                                {
                                    "event": "report_chunk",
                                    "chunk": chunk,
                                    "chunk_index": chunk_index,
                                },
                            )
                        total_chunks = len(report_chunks)
                        stream_mode = "fallback_chunk"

                    task_manager.publish_task_event(
                        task.task_id,
                        {
                            "event": "report_stream_finished",
                            "total_chunks": total_chunks,
                            "stream_mode": stream_mode,
                        },
                    )

                task_manager.update_task_progress(task.task_id, 96)
                result["performance_timing"] = {
                    **dict(result.get("performance_timing") or {}),
                    "backend_async_worker_total_ms": _elapsed_ms(started_at),
                    "backend_async_total_since_handler_ms": _elapsed_ms(endpoint_started_at),
                }
                detection_payload = _build_detection_payload(result)
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
                "performance_timing": {
                    **performance_timing,
                    "backend_async_initial_response_ms": _elapsed_ms(endpoint_started_at),
                },
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
