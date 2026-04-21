from pathlib import Path
from time import perf_counter, time
from typing import Any, Optional
import asyncio
from functools import lru_cache
import json
import os
import re
import tempfile
import unicodedata
import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from auth import decode_token, get_current_active_user
from database import ChatHistory, Contact, SessionLocal, User, get_db
from email_notifier import attach_email_notification, send_high_risk_email_if_needed
from graph_core.graph_client import graph_client
from graph_core.task_manager import TaskStatus, task_manager
try:
    from language_prompts import (
        build_single_pass_system_prompt,
        localize_early_warning,
        normalize_output_language,
    )
except ImportError:
    from backend.language_prompts import (
        build_single_pass_system_prompt,
        localize_early_warning,
        normalize_output_language,
    )
try:
    from risk_guardrails import (
        apply_critical_warning_floor,
        build_critical_text_guardrail_warning,
        is_authoritative_anti_fraud_notice,
    )
except ImportError:
    from backend.risk_guardrails import (
        apply_critical_warning_floor,
        build_critical_text_guardrail_warning,
        is_authoritative_anti_fraud_notice,
    )
from notification_recipients import resolve_guardian_email_receiver
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
    build_role_prompt_guidance,
    build_personalized_thresholds,
    format_combined_profile_text,
    normalize_user_role,
)
from src.core.utils.multimodal_payloads import (
    build_text_and_video_user_content,
    flatten_multimodal_text_content,
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
    (re.compile(r"(刷单|返利|做任务).{0,10}(垫付|先付|充值|返现|佣金)"), 24, "出现刷单返利诱导垫付话术"),
    (re.compile(r"(客服|平台|商家).{0,12}(退款|退费|理赔|改签).{0,12}(验证码|链接|下载|屏幕共享|远程)"), 24, "出现冒充客服退款链路"),
    (re.compile(r"(注销|清空|修复).{0,12}(征信|校园贷|学生账户|贷款记录)"), 22, "出现征信修复/注销类恐吓话术"),
    (re.compile(r"(贷款|放款|征信).{0,14}(保证金|解冻费|工本费|刷流水|手续费)"), 22, "出现贷款前置收费或刷流水话术"),
    (re.compile(r"(带单|老师|分析师|内幕消息).{0,12}(稳赚|保本|高收益|翻倍|拉群)"), 20, "出现投资带单高收益诱导"),
    (re.compile(r"(裸聊|私密视频).{0,14}(敲诈|转账|删(除)?视频|封口费)"), 28, "出现裸聊敲诈勒索话术"),
    (re.compile(r"(领导|老板|总监).{0,10}(转账|打款|汇款).{0,8}(紧急|马上|立刻)"), 22, "出现冒充领导紧急转账指令"),
    (re.compile(r"(游戏交易|游戏账号|装备|皮肤).{0,12}(私下交易|先付款|保证金)"), 18, "出现游戏交易私下付款诱导"),
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
    "刷单返利": 20,
    "垫付资金": 16,
    "保证金": 14,
    "解冻费": 14,
    "工本费": 10,
    "包装流水": 16,
    "注销校园贷": 16,
    "征信修复": 14,
    "冒充客服": 14,
    "退款理赔": 12,
    "机票改签": 12,
    "会员退费": 12,
    "高收益": 14,
    "内部消息": 12,
    "带单老师": 14,
    "杀猪盘": 20,
    "网恋投资": 16,
    "裸聊敲诈": 24,
    "冒充领导": 14,
    "领导转账": 16,
    "游戏交易": 12,
    "私下交易": 12,
    "verification code": 18,
    "wire transfer": 18,
    "safe account": 16,
    "screen share": 16,
}

_TEXT_CONSULTATIVE_CONTEXT_KEYWORDS = (
    "反诈",
    "防诈",
    "防骗",
    "科普",
    "普法",
    "宣传",
    "案例分析",
    "新闻",
    "报道",
    "课程",
    "作业",
    "论文",
    "讲座",
    "提醒",
    "这是诈骗吗",
    "是不是诈骗",
    "是否诈骗",
    "帮我判断",
)

_TEXT_TRANSACTION_KEYWORDS = (
    "转账",
    "汇款",
    "打款",
    "付款",
    "先付款",
    "先交钱",
    "充值",
    "垫付",
    "保证金",
    "解冻费",
    "工本费",
    "手续费",
    "刷流水",
    "验证码",
    "动态码",
    "安全账户",
    "屏幕共享",
    "远程控制",
    "远程协助",
    "点击链接",
    "下载app",
    "下载APP",
    "私下交易",
    "扫码",
)

_TEXT_HARD_SIGNAL_KEYWORDS = (
    "验证码",
    "安全账户",
    "屏幕共享",
    "远程控制",
    "立即转账",
    "公检法",
    "解冻费",
    "刷流水",
    "裸聊敲诈",
)

_TEXT_COMBINATION_RULES = (
    ("转账", "验证码", 24, "出现转账+验证码组合"),
    ("安全账户", "转账", 22, "出现安全账户+转账组合"),
    ("远程", "转账", 16, "出现远程控制+转账组合"),
    ("刷单", "垫付", 18, "出现刷单+垫付组合"),
    ("贷款", "保证金", 18, "出现贷款+保证金组合"),
    ("贷款", "解冻", 18, "出现贷款+解冻组合"),
    ("征信", "注销", 16, "出现征信+注销组合"),
    ("客服", "屏幕共享", 16, "出现客服+屏幕共享组合"),
    ("退款", "链接", 14, "出现退款+链接组合"),
    ("高收益", "内部消息", 14, "出现高收益+内部消息组合"),
    ("投资", "带单", 14, "出现投资+带单组合"),
    ("网恋", "投资", 16, "出现网恋+投资组合"),
    ("裸聊", "转账", 20, "出现裸聊+转账组合"),
    ("领导", "转账", 16, "出现领导+转账组合"),
    ("游戏", "私下交易", 14, "出现游戏+私下交易组合"),
    ("跑分", "银行卡", 20, "出现跑分+银行卡组合"),
    ("退款", "验证码", 14, "出现退款+验证码组合"),
)

_FAST_RAG_MIN_SIMILARITY = 0.16
_FAST_RAG_LOW_CONF_SIMILARITY = 0.24
_FAST_RAG_LOW_SCORE_CUTOFF = 18
_TEXT_MATCH_SEPARATOR_RE = re.compile(r"[\s\-_.,，。!！?？:：;；/\\|`~·•…'\"“”‘’()\[\]{}<>《》【】]+")

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


def _get_single_pass_system_prompt(mode: str, language: str = "zh-CN") -> str:
    if mode == "pro":
        base_prompt = _SINGLE_PASS_SYSTEM_PROMPT_PRO
    else:
        base_prompt = _SINGLE_PASS_SYSTEM_PROMPT_FLASH
    return build_single_pass_system_prompt(base_prompt, language)


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_rule_severity(value: Any, default: str = "soft") -> str:
    severity = str(value or default).strip().lower()
    return "hard" if severity == "hard" else "soft"


def _build_rule_meta(
    item: dict[str, Any],
    *,
    default_id: str,
    default_severity: str,
    default_floor_score: int = 0,
) -> dict[str, Any]:
    return {
        "rule_id": str(item.get("rule_id") or default_id).strip() or default_id,
        "severity": _normalize_rule_severity(item.get("severity"), default=default_severity),
        "floor_score": max(0, min(100, _safe_int(item.get("floor_score"), default_floor_score))),
        "source_priority": list(item.get("source_priority") or ["fast_text_rules", "local_rag", "llm_review"]),
    }


def _parse_warning_pattern_rules(
    raw_items: Any,
    max_weight: int = 40,
) -> tuple[tuple[re.Pattern[str], int, str, dict[str, Any]], ...]:
    pattern_rules: list[tuple[re.Pattern[str], int, str, dict[str, Any]]] = []
    for item in list(raw_items or []):
        if not isinstance(item, dict):
            continue
        raw_pattern = str(item.get("pattern") or "").strip()
        clue = str(item.get("clue") or "").strip()
        weight = _safe_int(item.get("weight"), 0)
        if not raw_pattern or not clue or weight <= 0:
            continue
        try:
            compiled = re.compile(raw_pattern, re.IGNORECASE)
        except re.error:
            continue
        normalized_weight = min(weight, max_weight)
        meta = _build_rule_meta(
            item,
            default_id=f"pattern:{len(pattern_rules) + 1}",
            default_severity="hard" if normalized_weight >= 30 else "soft",
        )
        pattern_rules.append((compiled, normalized_weight, clue, meta))
    return tuple(pattern_rules)


def _parse_warning_keyword_weights(raw_keywords: Any, max_weight: int = 30) -> dict[str, int]:
    keyword_weights: dict[str, int] = {}
    if not isinstance(raw_keywords, dict):
        return keyword_weights

    for raw_keyword, raw_weight in raw_keywords.items():
        keyword = str(raw_keyword or "").strip()
        weight = _safe_int(raw_weight, 0)
        if keyword and weight > 0:
            keyword_weights[keyword] = min(weight, max_weight)
    return keyword_weights


def _parse_structured_warning_rules(data: Any) -> dict[str, Any]:
    parsed = {
        "pattern_rules": [],
        "keyword_rules": [],
        "combination_rules": [],
    }
    for index, raw_rule in enumerate(list(data or []), start=1):
        if not isinstance(raw_rule, dict):
            continue
        rule_type = str(raw_rule.get("type") or "").strip().lower()
        clue = str(raw_rule.get("clue") or "").strip()
        meta = _build_rule_meta(raw_rule, default_id=f"structured:{index}", default_severity="soft")
        if rule_type == "pattern":
            raw_pattern = str(raw_rule.get("pattern") or "").strip()
            weight = _safe_int(raw_rule.get("weight"), 0)
            if not raw_pattern or not clue or weight <= 0:
                continue
            try:
                compiled = re.compile(raw_pattern, re.IGNORECASE)
            except re.error:
                continue
            parsed["pattern_rules"].append((compiled, min(weight, 40), clue, meta))
        elif rule_type == "keyword":
            keyword = str(raw_rule.get("keyword") or "").strip()
            weight = _safe_int(raw_rule.get("weight"), 0)
            if not keyword or weight <= 0:
                continue
            parsed["keyword_rules"].append((keyword, min(weight, 30), clue or f"命中关键词: {keyword}", meta))
        elif rule_type == "combination":
            left_token = str(raw_rule.get("left") or "").strip()
            right_token = str(raw_rule.get("right") or "").strip()
            bonus = _safe_int(raw_rule.get("bonus"), 0)
            if not left_token or not right_token or not clue or bonus <= 0:
                continue
            parsed["combination_rules"].append((left_token, right_token, min(bonus, 30), clue, meta))
    return parsed


def _parse_warning_combination_rules(
    raw_items: Any,
    max_bonus: int = 30,
) -> tuple[tuple[str, str, int, str, dict[str, Any]], ...]:
    combination_rules: list[tuple[str, str, int, str, dict[str, Any]]] = []
    for item in list(raw_items or []):
        if not isinstance(item, dict):
            continue
        left_token = str(item.get("left") or "").strip()
        right_token = str(item.get("right") or "").strip()
        clue = str(item.get("clue") or "").strip()
        bonus = _safe_int(item.get("bonus"), 0)
        if not left_token or not right_token or not clue or bonus <= 0:
            continue
        normalized_bonus = min(bonus, max_bonus)
        meta = _build_rule_meta(
            item,
            default_id=f"combo:{len(combination_rules) + 1}",
            default_severity="hard" if normalized_bonus >= 20 else "soft",
        )
        combination_rules.append((left_token, right_token, normalized_bonus, clue, meta))
    return tuple(combination_rules)


@lru_cache(maxsize=1)
def _get_fast_warning_rule_overrides() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parent.parent.parent
    default_path = project_root / "config" / "fast_warning_rules.json"
    config_path = Path(os.getenv("FAST_WARNING_RULES_PATH", str(default_path))).expanduser()

    overrides: dict[str, Any] = {
        "pattern_rules": tuple(),
        "keyword_rules": tuple(),
        "keyword_weights": {},
        "combination_rules": tuple(),
        "score_policy": {},
        "role_profiles": {},
    }
    if not config_path.exists():
        return overrides

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[预警] 读取规则配置失败: {config_path} ({exc})")
        return overrides

    pattern_rules = _parse_warning_pattern_rules(data.get("pattern_rules"), max_weight=40)
    structured_rules = _parse_structured_warning_rules(data.get("structured_rules"))
    keyword_weights = _parse_warning_keyword_weights(data.get("keyword_weights"), max_weight=30)
    combination_rules = _parse_warning_combination_rules(data.get("combination_rules"), max_bonus=30)

    raw_score_policy = data.get("score_policy")
    score_policy = raw_score_policy if isinstance(raw_score_policy, dict) else {}

    role_profiles: dict[str, dict[str, Any]] = {}
    raw_role_profiles = data.get("role_profiles")
    if isinstance(raw_role_profiles, dict):
        for raw_role_key, raw_profile in raw_role_profiles.items():
            if not isinstance(raw_profile, dict):
                continue

            role_key = normalize_user_role(str(raw_role_key or "general"))
            profile_pattern_rules = _parse_warning_pattern_rules(raw_profile.get("pattern_rules"), max_weight=40)
            profile_structured_rules = _parse_structured_warning_rules(raw_profile.get("structured_rules"))
            profile_keyword_weights = _parse_warning_keyword_weights(raw_profile.get("keyword_weights"), max_weight=30)
            profile_combination_rules = _parse_warning_combination_rules(raw_profile.get("combination_rules"), max_bonus=30)
            profile_raw_score_policy = raw_profile.get("score_policy")
            profile_score_policy = profile_raw_score_policy if isinstance(profile_raw_score_policy, dict) else {}

            if role_key in role_profiles:
                existing = role_profiles[role_key]
                existing["pattern_rules"] = (
                    tuple(existing.get("pattern_rules") or ())
                    + profile_pattern_rules
                    + tuple(profile_structured_rules.get("pattern_rules") or ())
                )
                existing["keyword_rules"] = (
                    tuple(existing.get("keyword_rules") or ())
                    + tuple(profile_structured_rules.get("keyword_rules") or ())
                )
                existing["keyword_weights"] = {
                    **dict(existing.get("keyword_weights") or {}),
                    **profile_keyword_weights,
                }
                existing["combination_rules"] = (
                    tuple(existing.get("combination_rules") or ())
                    + profile_combination_rules
                    + tuple(profile_structured_rules.get("combination_rules") or ())
                )
                existing["score_policy"] = {
                    **dict(existing.get("score_policy") or {}),
                    **profile_score_policy,
                }
                continue

            role_profiles[role_key] = {
                "pattern_rules": profile_pattern_rules + tuple(profile_structured_rules.get("pattern_rules") or ()),
                "keyword_rules": tuple(profile_structured_rules.get("keyword_rules") or ()),
                "keyword_weights": profile_keyword_weights,
                "combination_rules": profile_combination_rules + tuple(profile_structured_rules.get("combination_rules") or ()),
                "score_policy": profile_score_policy,
            }

    return {
        "pattern_rules": pattern_rules + tuple(structured_rules.get("pattern_rules") or ()),
        "keyword_rules": tuple(structured_rules.get("keyword_rules") or ()),
        "keyword_weights": keyword_weights,
        "combination_rules": combination_rules + tuple(structured_rules.get("combination_rules") or ()),
        "score_policy": score_policy,
        "role_profiles": role_profiles,
    }


def _get_role_warning_profile(rule_overrides: dict[str, Any], user_role: str) -> dict[str, Any]:
    role_profiles = rule_overrides.get("role_profiles")
    if not isinstance(role_profiles, dict):
        return {
            "pattern_rules": tuple(),
            "keyword_rules": tuple(),
            "keyword_weights": {},
            "combination_rules": tuple(),
            "score_policy": {},
        }

    normalized_role = normalize_user_role(user_role or "general")
    profile = role_profiles.get(normalized_role)
    if not isinstance(profile, dict):
        return {
            "pattern_rules": tuple(),
            "keyword_rules": tuple(),
            "keyword_weights": {},
            "combination_rules": tuple(),
            "score_policy": {},
        }

    return {
        "pattern_rules": tuple(profile.get("pattern_rules") or ()),
        "keyword_rules": tuple(profile.get("keyword_rules") or ()),
        "keyword_weights": dict(profile.get("keyword_weights") or {}),
        "combination_rules": tuple(profile.get("combination_rules") or ()),
        "score_policy": dict(profile.get("score_policy") or {}),
    }


def _get_shared_role_warning_rules(rule_overrides: dict[str, Any]) -> dict[str, Any]:
    role_profiles = rule_overrides.get("role_profiles")
    if not isinstance(role_profiles, dict):
        return {
            "pattern_rules": tuple(),
            "keyword_rules": tuple(),
            "keyword_weights": {},
            "combination_rules": tuple(),
        }

    merged_pattern_items: list[tuple[re.Pattern[str], int, str, dict[str, Any]]] = []
    merged_keyword_rules: list[tuple[str, int, str, dict[str, Any]]] = []
    merged_keyword_weights: dict[str, int] = {}
    merged_combination_items: list[tuple[str, str, int, str, dict[str, Any]]] = []

    for raw_profile in role_profiles.values():
        if not isinstance(raw_profile, dict):
            continue

        merged_pattern_items.extend(tuple(raw_profile.get("pattern_rules") or ()))
        merged_keyword_rules.extend(tuple(raw_profile.get("keyword_rules") or ()))
        merged_keyword_weights.update(dict(raw_profile.get("keyword_weights") or {}))
        merged_combination_items.extend(tuple(raw_profile.get("combination_rules") or ()))

    deduped_patterns: list[tuple[re.Pattern[str], int, str, dict[str, Any]]] = []
    seen_patterns: set[tuple[str, int, str, str]] = set()
    for pattern, weight, clue, meta in merged_pattern_items:
        dedupe_key = (getattr(pattern, "pattern", str(pattern)), int(weight), str(clue), str(meta.get("rule_id")))
        if dedupe_key in seen_patterns:
            continue
        seen_patterns.add(dedupe_key)
        deduped_patterns.append((pattern, weight, clue, meta))

    deduped_keyword_rules: list[tuple[str, int, str, dict[str, Any]]] = []
    seen_keyword_rules: set[tuple[str, int, str, str]] = set()
    for keyword, weight, clue, meta in merged_keyword_rules:
        dedupe_key = (str(keyword), int(weight), str(clue), str(meta.get("rule_id")))
        if dedupe_key in seen_keyword_rules:
            continue
        seen_keyword_rules.add(dedupe_key)
        deduped_keyword_rules.append((keyword, weight, clue, meta))

    deduped_combinations: list[tuple[str, str, int, str, dict[str, Any]]] = []
    seen_combinations: set[tuple[str, str, int, str, str]] = set()
    for left_token, right_token, bonus, clue, meta in merged_combination_items:
        dedupe_key = (str(left_token), str(right_token), int(bonus), str(clue), str(meta.get("rule_id")))
        if dedupe_key in seen_combinations:
            continue
        seen_combinations.add(dedupe_key)
        deduped_combinations.append((left_token, right_token, bonus, clue, meta))

    return {
        "pattern_rules": tuple(deduped_patterns),
        "keyword_rules": tuple(deduped_keyword_rules),
        "keyword_weights": merged_keyword_weights,
        "combination_rules": tuple(deduped_combinations),
    }


def _build_text_match_variants(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    compact = _TEXT_MATCH_SEPARATOR_RE.sub("", normalized)
    if compact and compact != normalized:
        return normalized, compact
    return (normalized,)


def _match_token_in_variants(text_variants: tuple[str, ...], token: str) -> bool:
    for token_variant in _build_text_match_variants(token):
        if not token_variant:
            continue
        for text_variant in text_variants:
            if token_variant in text_variant:
                return True
    return False


def _find_token_spans(text: str, token: str) -> list[dict[str, Any]]:
    if not text or not token:
        return []
    normalized_text = unicodedata.normalize("NFKC", str(text or ""))
    normalized_token = unicodedata.normalize("NFKC", str(token or ""))
    lowered_text = normalized_text.lower()
    lowered_token = normalized_token.lower()
    spans: list[dict[str, Any]] = []
    start = 0
    while lowered_token:
        index = lowered_text.find(lowered_token, start)
        if index < 0:
            break
        end = index + len(lowered_token)
        spans.append({"text": normalized_text[index:end], "start": index, "end": end})
        start = end
    return spans


def _dedupe_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for span in spans:
        key = (int(span.get("start", -1)), int(span.get("end", -1)), str(span.get("text") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(span)
    return deduped


def _count_keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    text_variants = _build_text_match_variants(text)
    return sum(1 for keyword in keywords if keyword and _match_token_in_variants(text_variants, keyword))


def _collect_role_profile_hits(
    text: str,
    text_variants: tuple[str, ...],
    compact_text: str,
    role_profile: dict[str, Any],
) -> tuple[int, list[str]]:
    hit_count = 0
    matched_markers: list[str] = []

    for pattern, _weight, clue, _meta in tuple(role_profile.get("pattern_rules") or ()):
        if pattern.search(text) or (compact_text != text_variants[0] and pattern.search(compact_text)):
            hit_count += 1
            matched_markers.append(str(clue))

    for keyword, _weight, clue, _meta in tuple(role_profile.get("keyword_rules") or ()):
        if _match_token_in_variants(text_variants, keyword):
            hit_count += 1
            matched_markers.append(str(clue))

    for keyword in dict(role_profile.get("keyword_weights") or {}).keys():
        if _match_token_in_variants(text_variants, keyword):
            hit_count += 1
            matched_markers.append(f"关键词:{keyword}")

    for left_token, right_token, _bonus, clue, _meta in tuple(role_profile.get("combination_rules") or ()):
        if _match_token_in_variants(text_variants, left_token) and _match_token_in_variants(text_variants, right_token):
            hit_count += 1
            matched_markers.append(str(clue))

    return hit_count, matched_markers


def _has_consultative_context(text: str) -> bool:
    text_variants = _build_text_match_variants(text)
    return any(_match_token_in_variants(text_variants, keyword) for keyword in _TEXT_CONSULTATIVE_CONTEXT_KEYWORDS)


def _calibrate_fast_rag_score(
    raw_rag_score: int,
    top_similarity: float,
    avg_similarity: float,
    hit_count: int,
) -> int:
    similarity_score = int(round((top_similarity * 0.7 + avg_similarity * 0.3) * 100))
    calibrated = int(round(raw_rag_score * 0.62 + similarity_score * 0.38))

    if top_similarity < 0.20:
        calibrated = int(calibrated * 0.62)
    elif top_similarity < _FAST_RAG_LOW_CONF_SIMILARITY:
        calibrated = int(calibrated * 0.80)

    if hit_count >= 3 and avg_similarity >= _FAST_RAG_LOW_CONF_SIMILARITY:
        calibrated += 4

    return _clamp_risk_score(calibrated)


def _warning_evidence_weight(warning: Optional[dict]) -> float:
    if not warning:
        return 0.0

    score = _safe_int(warning.get("risk_score"), 0)
    source = str(warning.get("source", "") or "")
    weight = 0.58 + min(0.42, score / 220.0)

    if source == "fast_text_rules":
        hard_signal_count = _safe_int(warning.get("hard_signal_count"), 0)
        weight += min(0.24, hard_signal_count * 0.08)
        if bool(warning.get("consultative_context")) and hard_signal_count <= 1:
            weight -= 0.20
    elif source == "fast_rag_probe":
        top_similarity = _safe_float(warning.get("rag_top_similarity"), 0.0)
        weight += min(0.26, top_similarity * 0.7)
        if top_similarity < _FAST_RAG_LOW_CONF_SIMILARITY:
            weight -= 0.16

    return max(0.35, min(1.45, weight))


def _build_fallback_low_risk_score(text: str, has_media: bool) -> int:
    normalized = (text or "").strip()
    if not normalized:
        return 0

    score = 2
    text_len = len(normalized)
    if text_len >= 24:
        score += 1
    if text_len >= 80:
        score += 2
    if "?" in normalized or "？" in normalized:
        score += 1
    if has_media:
        score = max(score, 4)

    return min(score, 12)


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
    language: str = "zh-CN",
) -> str:
    memory_context = memory_context or {}
    dynamic_thresholds = dynamic_thresholds or {}
    combined_profile_text = str(memory_context.get("combined_profile_text") or "none")
    normalized_language = normalize_output_language(language)
    role_prompt_guidance = build_role_prompt_guidance(user_role or "general", normalized_language)

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
    language_instruction = ""
    role_guidance_label = "角色提示"
    rag_context_label = "RAG相似案例与知识片段"
    short_term_label = "短期记忆（最近检测）"
    long_term_label = "长期行为画像"
    threshold_label = "个性化风险分段阈值"
    user_input_label = "用户原始输入"
    score_instruction = (
        "评分说明：请以你对原始输入、OCR文本、RAG片段和用户上下文的语义判断为主进行评分；"
        "快速预警只是参考证据，不是分数基线，也不能直接决定最终分数。\n"
        "若无明显风险，请在 0-15 内按文本实际内容给分，而不是固定输出 6。\n"
    )
    if normalized_language == "en-US":
        language_instruction = (
            "Output language: English only. Write WARNING_MESSAGE, risk explanation, "
            "action suggestions, and the full Markdown report in English. Keep metadata keys unchanged.\n\n"
        )
        role_guidance_label = "Role-specific guidance"
        rag_context_label = "RAG similar cases / knowledge snippets"
        short_term_label = "Short-term memory (recent detections)"
        long_term_label = "Long-term behavior profile"
        threshold_label = "Personalized risk thresholds"
        user_input_label = "Original user input"
        score_instruction = (
            "Score instruction: decide RISK_SCORE primarily by your own semantic assessment of the original input, OCR text, "
            "RAG snippets, and user context. Fast warning is only supporting evidence, not a score baseline.\n"
            "For clearly low-risk/general inquiry content with no warning evidence, choose a score in 0-15 based on the actual content; "
            "do not always output 6.\n"
        )

    media_hint = "用户包含媒体文件上传；请在报告中说明当前结论以文本与预警为基础。" if has_media else "本次输入为文本场景。"

    return language_instruction + (
        "请基于以下信息输出反诈分析：\n"
        f"用户角色: {user_role or 'general'}\n"
        f"{role_guidance_label}:\n{role_prompt_guidance}\n"
        f"组合画像:\n{combined_profile_text}\n"
        f"{media_hint}\n"
        f"快速预警分数: {warning_score}\n"
        f"快速预警等级: {warning_level}\n"
        f"快速预警提示: {warning_text or '无'}\n"
        f"快速预警线索:\n{warning_clues_text}\n\n"
        f"{rag_context_label}:\n"
        f"{rag_context_text}\n\n"
        f"{short_term_label}:\n"
        f"{short_term_summary}\n\n"
        f"{long_term_label}:\n"
        f"{long_term_summary}\n\n"
        f"{threshold_label}:\n"
        f"- low_threshold: {low_threshold}\n"
        f"- high_threshold: {high_threshold}\n"
        f"- 调整依据: {threshold_reason_text}\n\n"
        f"{user_input_label}:\n"
        f"{(message or '').strip()}\n\n"
        f"{score_instruction}"
        "请务必按照系统协议输出，并确保 RISK_LEVEL 与上述个性化阈值分段一致。"
    )


def _parse_single_pass_response(
    raw_output: str,
    early_warning: Optional[dict],
    dynamic_thresholds: Optional[dict[str, Any]] = None,
    memory_context: Optional[dict[str, Any]] = None,
    language: str = "zh-CN",
) -> dict[str, Any]:
    dynamic_thresholds = dynamic_thresholds or {}
    memory_context = memory_context or {}
    english_output = normalize_output_language(language) == "en-US"

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

    scam_type = (scam_type_match.group(1).strip() if scam_type_match else "") or (
        "not_identified" if english_output else "未识别"
    )
    guardian_alert = _parse_bool(
        guardian_alert_match.group(1).strip() if guardian_alert_match else "",
        default=risk_level == "high",
    )

    warning_message = (
        warning_message_match.group(1).strip() if warning_message_match else ""
    ) or str((early_warning or {}).get("warning_message", "")).strip()

    fallback_report = (
        "The system has completed the analysis. Stay cautious and avoid sensitive actions until verification is complete."
        if english_output
        else "系统已完成分析，请保持警惕并避免敏感操作。"
    )
    final_report = report_text.strip() or warning_message or fallback_report
    risk_clues = list((early_warning or {}).get("risk_clues") or [])
    action_items = _extract_action_items_from_report(final_report)

    if not action_items:
        if english_output and risk_level == "high":
            action_items = [
                "Stop transfers, downloads, screen sharing, and code sharing immediately",
                "Call 110 or 96110 if money or account access is involved",
                "Notify a guardian or trusted emergency contact",
            ]
        elif english_output and risk_level == "medium":
            action_items = [
                "Pause payment or account operations",
                "Verify the identity through an official channel",
                "Preserve screenshots, audio, video, and chat records",
            ]
        elif english_output:
            action_items = [
                "Keep the conversation in official channels",
                "Do not click suspicious links or install unknown apps",
                "Avoid sharing sensitive information before verification",
            ]
        elif risk_level == "high":
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

    result = {
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
        "matched_rule_ids": list((early_warning or {}).get("matched_rule_ids") or []),
        "hard_rule_ids": list((early_warning or {}).get("hard_rule_ids") or []),
        "soft_rule_ids": list((early_warning or {}).get("soft_rule_ids") or []),
        "matched_spans": list((early_warning or {}).get("matched_spans") or []),
        "source_priority": list((early_warning or {}).get("source_priority") or ["single_pass_llm", "llm_review"]),
        "popup_severity": (early_warning or {}).get("popup_severity")
        or ("blocking" if risk_level == "high" else "soft" if risk_level == "medium" else "none"),
        "critical_guardrail_triggered": bool((early_warning or {}).get("critical_guardrail_triggered", False)),
        "voice_warning_required": bool(
            (early_warning or {}).get("voice_warning_required", risk_level == "high")
        ),
        "guardian_intervention_required": bool(
            (early_warning or {}).get("guardian_intervention_required", risk_level == "high" and guardian_alert)
        ),
        "score_breakdown": (early_warning or {}).get("score_breakdown"),
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
    return apply_critical_warning_floor(result, early_warning)


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
                {
                    "role": "user",
                    "content": flatten_multimodal_text_content(getattr(messages[1], "content", "")),
                },
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
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(f"Ollama chat failed {response.status_code}: {detail[:500]}")
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
    language: str = "zh-CN",
    memory_context: Optional[dict[str, Any]] = None,
    dynamic_thresholds: Optional[dict[str, Any]] = None,
    video_path: Optional[str] = None,
) -> tuple[dict[str, Any], int]:
    total_started_at = perf_counter()
    model_config = _get_single_pass_model_config()
    if not _is_ollama_native_streaming_enabled(str(model_config.get("base_url") or "")):
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
        language=language,
    )
    system_prompt = _get_single_pass_system_prompt(model_mode, language)
    user_content: Any = user_prompt
    if video_path:
        try:
            user_content = build_text_and_video_user_content(user_prompt, video_path)
        except Exception as exc:
            print(f"[single_pass_llm] multimodal video payload disabled: {exc}")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    task_manager.publish_task_event(task_id, {"event": "report_stream_started", "stream_mode": "token"})

    raw_parts: list[str] = []
    buffered_prefix = ""
    marker_seen = False
    chunk_count = 0
    llm_started_at = perf_counter()
    first_report_chunk_ms: Optional[float] = None
    llm_metadata: dict[str, Any] = {}
    published_metadata: dict[str, Any] = {}
    llm_error: Optional[str] = None

    def publish_metadata_if_changed(force: bool = False) -> None:
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

    try:
        async for chunk_text, _backend_name in _stream_single_pass_chunks(messages, model_config, system_prompt):
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
    except (httpx.HTTPError, RuntimeError) as exc:
        llm_error = str(exc)
        print(f"[single_pass_llm] streaming failed, fallback to early warning: {llm_error}")

    raw_output = "".join(raw_parts)
    parsed_result = _parse_single_pass_response(
        raw_output,
        early_warning=early_warning,
        dynamic_thresholds=dynamic_thresholds,
        memory_context=memory_context,
        language=language,
    )
    parsed_result["performance_timing"] = {
        "report_llm_api_roundtrip_ms": _elapsed_ms(llm_started_at),
        "report_llm_total_ms": _elapsed_ms(total_started_at),
        "report_first_chunk_ms": first_report_chunk_ms,
    }
    if llm_error:
        parsed_result["performance_timing"]["report_llm_error"] = llm_error
        parsed_result["performance_timing"]["report_llm_fallback"] = "early_warning"

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

    similarity_values = [
        _safe_float(getattr(case, "similarity", 0.0), 0.0)
        for case in retrieved_cases
    ]
    top_similarity = max(similarity_values) if similarity_values else 0.0
    avg_similarity = (sum(similarity_values) / len(similarity_values)) if similarity_values else 0.0

    if top_similarity < _FAST_RAG_MIN_SIMILARITY:
        return None

    search_hits = [create_search_hit_from_retrieved_case(case) for case in retrieved_cases]
    rag_result = detector.assess(query, search_hits)

    raw_rag_score = int(float(rag_result.confidence) * 100)
    rag_score = _calibrate_fast_rag_score(
        raw_rag_score=raw_rag_score,
        top_similarity=top_similarity,
        avg_similarity=avg_similarity,
        hit_count=len(retrieved_cases),
    )
    detector_level = _normalize_level(rag_result.risk_level, raw_rag_score)
    score_level = _risk_level_from_score(rag_score)
    if top_similarity < _FAST_RAG_LOW_CONF_SIMILARITY:
        rag_level = score_level
    else:
        rag_level = _max_level(detector_level, score_level)

    if rag_level == "low" and rag_score < _FAST_RAG_LOW_SCORE_CUTOFF:
        return None

    clues: list[str] = []
    if rag_result.matched_subtypes:
        clues.append(f"RAG命中子类型: {rag_result.matched_subtypes[0]}")
    for tag in (rag_result.matched_tags or [])[:3]:
        clues.append(f"RAG标签: {tag}")
    clues.append(f"RAG命中知识片段: {len(rag_result.hits)}条")
    clues.append(f"RAG最高相似度: {top_similarity:.2f}")

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
        "popup_severity": "soft" if rag_level in {"medium", "high"} else "none",
        "source_priority": ["local_rag", "fast_text_rules", "llm_review"],
        "rag_raw_score": _clamp_risk_score(raw_rag_score),
        "rag_top_similarity": round(top_similarity, 4),
        "rag_avg_similarity": round(avg_similarity, 4),
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

    if rule_warning and rule_warning.get("source") == "critical_text_guardrail":
        warning = dict(rule_warning)
        if rag_warning:
            warning["risk_clues"] = list(
                dict.fromkeys(
                    list(warning.get("risk_clues") or [])
                    + list(rag_warning.get("risk_clues") or [])
                )
            )[:8]
            warning["rag_context"] = list(rag_warning.get("rag_context") or [])
            warning["similar_cases"] = list(rag_warning.get("similar_cases") or rag_warning.get("rag_context") or [])
            warning["source_priority"] = list(
                dict.fromkeys(
                    list(warning.get("source_priority") or ["critical_text_guardrail", "fast_text_rules", "local_rag"])
                    + list(rag_warning.get("source_priority") or ["local_rag"])
                )
            )

    elif rule_warning and rag_warning:
        rule_score = int(rule_warning.get("risk_score", 0))
        rag_score = int(rag_warning.get("risk_score", 0))
        rule_weight = _warning_evidence_weight(rule_warning)
        rag_weight = _warning_evidence_weight(rag_warning)
        merged_score = min(
            99,
            int(round((rule_score * rule_weight + rag_score * rag_weight) / max(rule_weight + rag_weight, 0.01))),
        )

        rule_level = _normalize_level(str(rule_warning.get("risk_level", "low")), rule_score)
        rag_level = _normalize_level(str(rag_warning.get("risk_level", "low")), rag_score)
        max_source_level = _max_level(rule_level, rag_level)
        merged_level = _risk_level_from_score(merged_score)

        has_dual_medium_signal = rule_score >= 45 and rag_score >= 45
        has_single_strong_signal = max(rule_score, rag_score) >= 86

        if max_source_level == "high" and (has_dual_medium_signal or has_single_strong_signal):
            merged_level = "high"
        elif max_source_level == "medium" and merged_level == "low":
            merged_level = "medium"

        if merged_level == "high":
            merged_score = max(merged_score, 78 if has_dual_medium_signal else 74)
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
            "signal_severity": "hard" if rule_warning.get("signal_severity") == "hard" else "soft",
            "matched_rule_ids": list(dict.fromkeys(list(rule_warning.get("matched_rule_ids") or []))),
            "hard_rule_ids": list(dict.fromkeys(list(rule_warning.get("hard_rule_ids") or []))),
            "soft_rule_ids": list(dict.fromkeys(list(rule_warning.get("soft_rule_ids") or []))),
            "matched_spans": list(rule_warning.get("matched_spans") or []),
            "source_priority": list(
                dict.fromkeys(
                    list(rule_warning.get("source_priority") or ["fast_text_rules", "local_rag", "llm_review"])
                    + list(rag_warning.get("source_priority") or ["local_rag", "llm_review"])
                )
            ),
            "popup_severity": "blocking" if merged_level == "high" else "soft" if merged_level == "medium" else "none",
            "voice_warning_required": merged_level == "high",
            "guardian_intervention_required": merged_level == "high"
            and bool(rule_warning.get("hard_rule_ids") or rule_warning.get("critical_guardrail_triggered")),
            "score_breakdown": {
                "source": "rules_rag_fusion",
                "rule": rule_warning.get("score_breakdown"),
                "rag": {
                    "raw_score": rag_warning.get("rag_raw_score"),
                    "top_similarity": rag_warning.get("rag_top_similarity"),
                    "avg_similarity": rag_warning.get("rag_avg_similarity"),
                },
            },
            "fusion_weights": {
                "rule": round(rule_weight, 3),
                "rag": round(rag_weight, 3),
            },
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
    user_role: str = "general",
) -> Optional[dict]:
    normalized_role = normalize_user_role(user_role or "general")
    rule_warning = _build_fast_text_warning(message, has_media=has_media, user_role=normalized_role)
    rag_warning = None
    rag_timeout_sec = max(0.4, min(2.5, _safe_float(os.getenv("FAST_EARLY_WARNING_RAG_TIMEOUT_SEC"), 1.4)))

    text = (message or "").strip()
    if text:
        try:
            rag_warning = await asyncio.wait_for(
                _build_fast_rag_warning(text),
                timeout=rag_timeout_sec,
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
        "risk_score": _build_fallback_low_risk_score(text, has_media=has_media),
        "risk_level": "low",
        "risk_clues": fallback_clues,
        "warning_message": fallback_message,
        "source": "fast_fallback",
        "is_preliminary": True,
        "user_role": normalized_role,
        "popup_severity": "none",
        "source_priority": ["fast_fallback", "llm_review"],
    }


def _build_fast_text_warning(message: str, has_media: bool, user_role: str = "general") -> Optional[dict]:
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
            "popup_severity": "none",
            "source_priority": ["media_ai_pending", "fast_text_rules", "local_rag", "llm_review"],
        }

    if is_authoritative_anti_fraud_notice(text):
        warning_message = "检测到官方反诈提醒/科普内容，当前更像安全公告而非诈骗样本。"
        if has_media:
            warning_message += " 同时存在媒体内容，后续仍会继续进行图像/语音/视频核验。"
        return {
            "risk_score": 8,
            "risk_level": "low",
            "risk_clues": ["识别为官方反诈提醒语境", "包含国家反诈中心/公安提醒/96110 等安全提示信息"],
            "warning_message": warning_message,
            "source": "official_anti_fraud_notice",
            "is_preliminary": True,
            "user_role": normalize_user_role(user_role or "general"),
            "consultative_context": True,
            "transaction_signal_count": 0,
            "hard_signal_count": 0,
            "signal_severity": "soft",
            "matched_rule_ids": ["info:official_anti_fraud_notice"],
            "hard_rule_ids": [],
            "soft_rule_ids": ["info:official_anti_fraud_notice"],
            "matched_spans": [],
            "source_priority": ["official_anti_fraud_notice", "llm_review"],
            "popup_severity": "none",
            "voice_warning_required": False,
            "guardian_intervention_required": False,
            "score_breakdown": {
                "source": "official_anti_fraud_notice",
                "components": [{"id": "info:official_anti_fraud_notice", "type": "context", "severity": "soft", "score": 8}],
                "hard_rule_count": 0,
                "soft_rule_count": 1,
                "transaction_signal_count": 0,
                "hard_signal_count": 0,
            },
        }

    critical_warning = build_critical_text_guardrail_warning(text)
    if critical_warning is not None:
        warning = dict(critical_warning)
        warning["user_role"] = normalize_user_role(user_role or "general")
        if has_media:
            warning["warning_message"] = (
                f"{warning['warning_message']} 同时存在媒体内容，后续会继续进行图像/语音/视频核验。"
            )
        return warning

    score = 0
    clues = []
    matched_rule_ids: list[str] = []
    hard_rule_ids: list[str] = []
    soft_rule_ids: list[str] = []
    score_components: list[dict[str, Any]] = []
    matched_spans: list[dict[str, Any]] = []
    source_priority = ["fast_text_rules", "local_rag", "llm_review"]
    text_variants = _build_text_match_variants(text)
    compact_text = text_variants[-1]
    normalized_role = normalize_user_role(user_role or "general")
    consultative_context = _has_consultative_context(text)

    rule_overrides = _get_fast_warning_rule_overrides()
    shared_role_rules = _get_shared_role_warning_rules(rule_overrides)
    role_profile = _get_role_warning_profile(rule_overrides, normalized_role)
    pattern_rules = (
        _TEXT_PATTERN_RULES
        + tuple(rule_overrides.get("pattern_rules") or ())
        + tuple(shared_role_rules.get("pattern_rules") or ())
    )
    keyword_rules = (
        tuple(rule_overrides.get("keyword_rules") or ())
        + tuple(shared_role_rules.get("keyword_rules") or ())
    )
    keyword_weights = {
        **_TEXT_KEYWORD_WEIGHTS,
        **dict(rule_overrides.get("keyword_weights") or {}),
        **dict(shared_role_rules.get("keyword_weights") or {}),
    }
    combination_rules = (
        _TEXT_COMBINATION_RULES
        + tuple(rule_overrides.get("combination_rules") or ())
        + tuple(shared_role_rules.get("combination_rules") or ())
    )
    score_policy = dict(rule_overrides.get("score_policy") or {})
    role_score_policy = dict(role_profile.get("score_policy") or {})
    role_specific_hit_count, role_specific_markers = _collect_role_profile_hits(
        text=text,
        text_variants=text_variants,
        compact_text=compact_text,
        role_profile=role_profile,
    )

    for index, pattern_rule in enumerate(pattern_rules, start=1):
        if len(pattern_rule) == 4:
            pattern, weight, clue, meta = pattern_rule
            rule_id = str(meta.get("rule_id") or f"pattern:{index}")
            severity = _normalize_rule_severity(meta.get("severity"), default="hard" if weight >= 30 else "soft")
            floor_score = max(0, _safe_int(meta.get("floor_score"), 0))
            source_priority = list(meta.get("source_priority") or source_priority)
        else:
            pattern, weight, clue = pattern_rule
            rule_id = f"pattern:{index}"
            severity = "hard" if weight >= 30 else "soft"
            floor_score = 0
        match = pattern.search(text) or (compact_text != text_variants[0] and pattern.search(compact_text))
        if match:
            score += weight
            if floor_score > 0:
                score = max(score, floor_score)
            clues.append(clue)
            matched_rule_ids.append(rule_id)
            (hard_rule_ids if severity == "hard" else soft_rule_ids).append(rule_id)
            matched_spans.extend(
                [{"rule_id": rule_id, **span} for span in _find_token_spans(text, str(match.group(0) or ""))]
            )
            score_components.append(
                {
                    "id": rule_id,
                    "type": "pattern",
                    "severity": severity,
                    "score": weight,
                    "floor_score": floor_score,
                    "floor_applied": floor_score > 0,
                    "clue": clue,
                }
            )

    for keyword, weight, clue, meta in keyword_rules:
        if _match_token_in_variants(text_variants, keyword):
            rule_id = str(meta.get("rule_id") or f"keyword:{keyword}")
            severity = _normalize_rule_severity(meta.get("severity"), default="soft")
            floor_score = max(0, _safe_int(meta.get("floor_score"), 0))
            source_priority = list(meta.get("source_priority") or source_priority)
            score += weight
            if floor_score > 0:
                score = max(score, floor_score)
            matched_rule_ids.append(rule_id)
            (hard_rule_ids if severity == "hard" else soft_rule_ids).append(rule_id)
            matched_spans.extend([{"rule_id": rule_id, **span} for span in _find_token_spans(text, keyword)])
            score_components.append(
                {
                    "id": rule_id,
                    "type": "keyword",
                    "severity": severity,
                    "score": weight,
                    "floor_score": floor_score,
                    "floor_applied": floor_score > 0,
                    "keyword": keyword,
                    "clue": clue,
                }
            )
            clues.append(clue)

    for keyword, weight in keyword_weights.items():
        if _match_token_in_variants(text_variants, keyword):
            score += weight
            rule_id = f"keyword:{keyword}"
            severity = "hard" if keyword in _TEXT_HARD_SIGNAL_KEYWORDS or weight >= 24 else "soft"
            matched_rule_ids.append(rule_id)
            (hard_rule_ids if severity == "hard" else soft_rule_ids).append(rule_id)
            matched_spans.extend([{"rule_id": rule_id, **span} for span in _find_token_spans(text, keyword)])
            score_components.append(
                {"id": rule_id, "type": "keyword", "severity": severity, "score": weight, "keyword": keyword}
            )
            clues.append(f"命中关键词: {keyword}")

    for index, combo_rule in enumerate(combination_rules, start=1):
        if len(combo_rule) == 5:
            left_token, right_token, bonus, combo_clue, meta = combo_rule
            rule_id = str(meta.get("rule_id") or f"combo:{index}")
            severity = _normalize_rule_severity(meta.get("severity"), default="hard" if bonus >= 20 else "soft")
            floor_score = max(0, _safe_int(meta.get("floor_score"), 0))
            source_priority = list(meta.get("source_priority") or source_priority)
        else:
            left_token, right_token, bonus, combo_clue = combo_rule
            rule_id = f"combo:{index}"
            severity = "hard" if bonus >= 20 else "soft"
            floor_score = 0
        if _match_token_in_variants(text_variants, left_token) and _match_token_in_variants(text_variants, right_token):
            score += bonus
            if floor_score > 0:
                score = max(score, floor_score)
            clues.append(combo_clue)
            matched_rule_ids.append(rule_id)
            (hard_rule_ids if severity == "hard" else soft_rule_ids).append(rule_id)
            matched_spans.extend([{"rule_id": rule_id, **span} for span in _find_token_spans(text, left_token)])
            matched_spans.extend([{"rule_id": rule_id, **span} for span in _find_token_spans(text, right_token)])
            score_components.append(
                {
                    "id": rule_id,
                    "type": "combination",
                    "severity": severity,
                    "score": bonus,
                    "floor_score": floor_score,
                    "floor_applied": floor_score > 0,
                    "left": left_token,
                    "right": right_token,
                    "clue": combo_clue,
                }
            )

    urgent_punctuation = text.count("!") + text.count("！")
    if urgent_punctuation >= 2:
        score += 6
        clues.append("话术存在明显催促语气")

    transaction_signal_count = _count_keyword_hits(text, _TEXT_TRANSACTION_KEYWORDS)
    hard_signal_count = _count_keyword_hits(text, _TEXT_HARD_SIGNAL_KEYWORDS)

    if len(set(clues)) >= 4:
        score += 8
        clues.append("多个独立风险信号叠加")

    education_fee_signal = any("教育缴费" in clue or "冒充学校" in clue for clue in clues)
    hard_high_risk_signal = any(
        marker in clue
        for clue in clues
        for marker in ["立即转账", "验证码", "公检法", "公安局", "检察院", "法院", "远程控制", "安全账户"]
    ) or hard_signal_count >= 2

    if consultative_context and not hard_high_risk_signal:
        if transaction_signal_count == 0:
            score = min(int(score * 0.22), 18)
            clues.append("检测到咨询/科普语境且无交易动作，已显著降权")
        elif transaction_signal_count == 1:
            score = int(score * 0.36)
            clues.append("检测到咨询/科普语境，已降低误报权重")
        else:
            score = int(score * 0.65)
            clues.append("检测到咨询语境，已进行保守降权")

    if education_fee_signal and not hard_high_risk_signal:
        score = min(max(score, 68), 76)

    hard_signal_medium_min_hits = max(2, _safe_int(score_policy.get("hard_signal_medium_min_hits"), 2))
    hard_signal_high_min_hits = max(hard_signal_medium_min_hits + 1, _safe_int(score_policy.get("hard_signal_high_min_hits"), 3))
    hard_signal_medium_floor = max(45, _safe_int(score_policy.get("hard_signal_medium_floor"), 52))
    hard_signal_high_floor = max(hard_signal_medium_floor + 8, _safe_int(score_policy.get("hard_signal_high_floor"), 82))

    if hard_signal_count >= hard_signal_medium_min_hits:
        score = max(score, hard_signal_medium_floor)
        matched_rule_ids.append("floor:hard_signal_medium")
        hard_rule_ids.append("floor:hard_signal_medium")
        clues.append("命中多个强风险信号，触发保底预警")
    if hard_signal_count >= hard_signal_high_min_hits and transaction_signal_count >= 1:
        score = max(score, hard_signal_high_floor)
        matched_rule_ids.append("floor:hard_signal_high_transaction")
        hard_rule_ids.append("floor:hard_signal_high_transaction")
        clues.append("强风险信号叠加交易动作，提升至高危保底分")

    global_role_signal_score_threshold = max(0, min(95, _safe_int(score_policy.get("role_signal_score_threshold"), 24)))
    global_role_signal_min_hits = max(1, min(8, _safe_int(score_policy.get("role_signal_min_hits"), 1)))
    global_role_signal_boost_per_hit = max(0, min(8, _safe_int(score_policy.get("role_signal_boost_per_hit"), 2)))
    global_role_signal_max_boost = max(0, min(24, _safe_int(score_policy.get("role_signal_max_boost"), 6)))
    global_role_signal_requires_transaction = bool(score_policy.get("role_signal_requires_transaction", False))

    role_signal_score_threshold = max(
        0,
        min(
            95,
            _safe_int(
                role_score_policy.get("role_signal_score_threshold"),
                global_role_signal_score_threshold,
            ),
        ),
    )
    role_signal_min_hits = max(
        1,
        min(8, _safe_int(role_score_policy.get("role_signal_min_hits"), global_role_signal_min_hits)),
    )
    role_signal_boost_per_hit = max(
        0,
        min(8, _safe_int(role_score_policy.get("role_signal_boost_per_hit"), global_role_signal_boost_per_hit)),
    )
    role_signal_max_boost = max(
        0,
        min(24, _safe_int(role_score_policy.get("role_signal_max_boost"), global_role_signal_max_boost)),
    )
    role_signal_fixed_boost = max(0, min(24, _safe_int(role_score_policy.get("role_signal_boost"), 0)))
    role_signal_requires_transaction = bool(
        role_score_policy.get("role_signal_requires_transaction", global_role_signal_requires_transaction)
    )
    role_signal_skip_consultative = bool(role_score_policy.get("role_signal_skip_consultative", True))

    if (
        role_specific_hit_count >= role_signal_min_hits
        and score >= role_signal_score_threshold
        and (not role_signal_requires_transaction or transaction_signal_count >= 1)
        and not (role_signal_skip_consultative and consultative_context and transaction_signal_count == 0)
    ):
        if role_signal_fixed_boost > 0:
            role_signal_boost = role_signal_fixed_boost
        else:
            role_signal_boost = min(role_signal_max_boost, role_specific_hit_count * role_signal_boost_per_hit)

        if role_signal_boost > 0:
            score += role_signal_boost
            if role_specific_markers:
                clues.append(f"角色专项类型: {role_specific_markers[0]}")
            clues.append(f"角色专项命中加分: {normalized_role}(+{role_signal_boost})")

    if len(text) <= 12 and score < 35 and not hard_high_risk_signal and not has_media and not matched_rule_ids:
        return None

    score = min(score, 95)
    if score < 20 and not has_media and not matched_rule_ids:
        return None

    global_medium_threshold = max(20, min(70, _safe_int(score_policy.get("medium_threshold"), 40)))
    global_high_threshold = max(global_medium_threshold + 5, min(96, _safe_int(score_policy.get("high_threshold"), 75)))
    level = _risk_level_from_score(
        score,
        low_threshold=global_medium_threshold,
        high_threshold=global_high_threshold,
    )
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
        "user_role": normalized_role,
        "consultative_context": consultative_context,
        "transaction_signal_count": transaction_signal_count,
        "hard_signal_count": hard_signal_count,
        "signal_severity": "hard" if hard_rule_ids and (level == "high" or hard_signal_count >= 2) else "soft",
        "matched_rule_ids": list(dict.fromkeys(matched_rule_ids)),
        "hard_rule_ids": list(dict.fromkeys(hard_rule_ids)),
        "soft_rule_ids": list(dict.fromkeys(soft_rule_ids)),
        "matched_spans": _dedupe_spans(matched_spans)[:12],
        "source_priority": source_priority,
        "popup_severity": "blocking" if level == "high" else "soft" if level == "medium" else "none",
        "voice_warning_required": level == "high",
        "guardian_intervention_required": level == "high" and bool(hard_rule_ids),
        "score_breakdown": {
            "source": "fast_text_rules",
            "components": score_components[:12],
            "hard_rule_count": len(set(hard_rule_ids)),
            "soft_rule_count": len(set(soft_rule_ids)),
            "transaction_signal_count": transaction_signal_count,
            "hard_signal_count": hard_signal_count,
            "medium_threshold": global_medium_threshold,
            "high_threshold": global_high_threshold,
            "floor_score": score,
        },
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
        audio_path = _save_temp_file(audio_file)

    image_path = None
    if image_file:
        image_path = _save_temp_file(image_file, preprocess_image=True)

    video_path = None
    if video_file:
        video_path = _save_temp_file(video_file)

    return audio_path, image_path, video_path, timing


def _merge_image_ocr_timing(performance_timing: dict[str, Any], metadata: dict[str, Any]) -> None:
    if "ocr_total_ms" in metadata:
        performance_timing["ocr_image_to_text_ms"] = metadata.get("ocr_total_ms")


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

    fake_probability = None
    if result.fake_analysis is not None:
        fake_probability = float(result.fake_analysis.fake_probability)

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

    fake_probability = None
    if result.fake_analysis is not None:
        fake_probability = float(result.fake_analysis.fake_probability)

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
            "email": contact.email or "",
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
        "matched_rule_ids": result.get("matched_rule_ids", []),
        "hard_rule_ids": result.get("hard_rule_ids", []),
        "soft_rule_ids": result.get("soft_rule_ids", []),
        "matched_spans": result.get("matched_spans", []),
        "source_priority": result.get("source_priority", []),
        "popup_severity": result.get("popup_severity"),
        "critical_guardrail_triggered": bool(result.get("critical_guardrail_triggered", False)),
        "voice_warning_required": bool(result.get("voice_warning_required", False)),
        "guardian_intervention_required": bool(result.get("guardian_intervention_required", False)),
        "score_breakdown": result.get("score_breakdown"),
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
    language: Optional[str] = Form(None),
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
    performance_timing: dict[str, Any] = {}
    requested_language = normalize_output_language(language or getattr(current_user, "language", "zh-CN"))

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
        guardian_email_receiver = resolve_guardian_email_receiver(contacts)
        memory_context = _build_user_memory_context(db, current_user, message)

        image_ai_warning = None
        if image_path:
            try:
                image_ai_started_at = perf_counter()
                image_ai_warning = await asyncio.wait_for(
                    _build_fast_image_ai_warning(image_path),
                    timeout=1.2,
                )
            except (asyncio.TimeoutError, Exception):
                pass

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
                user_role=normalize_user_role(current_user.user_role),
            )
            fallback_warning = _merge_warning_with_media_warnings(fallback_warning, media_warnings)
            fallback_warning = localize_early_warning(fallback_warning, requested_language, has_media=has_media)
            result, _ = await _run_single_pass_detection_stream(
                task_id=f"sync_{uuid.uuid4().hex[:12]}",
                message=single_pass_message,
                user_role=normalize_user_role(current_user.user_role),
                early_warning=fallback_warning,
                has_media=has_media,
                model_mode=model_mode,
                language=requested_language,
                memory_context=memory_context,
                dynamic_thresholds=memory_context.get("dynamic_thresholds"),
                video_path=video_path,
            )
            result["performance_timing"] = {
                **performance_timing,
                **dict(result.get("performance_timing") or {}),
            }
        else:
            workflow_options = {
                "prefer_ai_rate_early_warning": bool(image_path),
                "image_ai_ocr_skip_threshold": 0.74,
                "language": requested_language,
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

        email_notification = await send_high_risk_email_if_needed(
            receiver=guardian_email_receiver,
            result=result,
            notify_enabled=current_user.notify_enabled,
            notify_high_risk=current_user.notify_high_risk,
        )
        attach_email_notification(result, email_notification)

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
    language: Optional[str] = Form(None),
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
    performance_timing: dict[str, Any] = {}
    requested_language = normalize_output_language(language or getattr(current_user, "language", "zh-CN"))

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
        receiver_email = ""
        notify_enabled = current_user.notify_enabled
        notify_high_risk = current_user.notify_high_risk
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
            except asyncio.TimeoutError:
                print("[预警] 图片AI率快速检测超时，继续执行规则/RAG预警")
            except Exception as exc:
                print(f"[预警] 图片AI率快速检测失败: {exc}")

        early_warning_started_at = perf_counter()
        early_warning = await _build_fast_early_warning(
            message,
            has_media=has_media,
            image_ai_warning=image_ai_warning,
            user_role=user_role,
        )
        early_warning = localize_early_warning(early_warning, requested_language, has_media=has_media)
        performance_timing["early_warning_total_ms"] = _elapsed_ms(early_warning_started_at)

        workflow_options = {
            "prefer_ai_rate_early_warning": bool(
                (image_ai_warning or {}).get("prefer_ai_rate_early_warning", bool(image_path))
            ),
            "image_ai_probability": (image_ai_warning or {}).get("image_ai_probability"),
            "image_ai_risk_level": (image_ai_warning or {}).get("risk_level"),
            "image_ai_ocr_skip_threshold": (image_ai_warning or {}).get("image_ai_ocr_skip_threshold", 0.74),
            "language": requested_language,
            "age_group": str(getattr(current_user, "age_group", "unknown") or "unknown"),
            "gender": str(getattr(current_user, "gender", "unknown") or "unknown"),
            "occupation": str(getattr(current_user, "occupation", "other") or "other"),
            "combined_profile_text": str(memory_context.get("combined_profile_text") or ""),
            "performance_timing": performance_timing,
        }

        contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
        guardian_contact = next((contact for contact in contacts if contact.is_guardian), None)
        receiver_email = resolve_guardian_email_receiver(contacts)
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
                        user_role=user_role,
                    )
                    llm_early_warning = _merge_warning_with_media_warnings(llm_early_warning, media_warnings)
                    llm_early_warning = localize_early_warning(
                        llm_early_warning,
                        requested_language,
                        has_media=has_media,
                    )
                    result, total_chunks = await _run_single_pass_detection_stream(
                        task_id=task.task_id,
                        message=single_pass_message,
                        user_role=user_role,
                        early_warning=llm_early_warning,
                        has_media=has_media,
                        model_mode=model_mode,
                        language=requested_language,
                        memory_context=memory_context,
                        dynamic_thresholds=memory_context.get("dynamic_thresholds"),
                        video_path=video_path,
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
                email_notification = await send_high_risk_email_if_needed(
                    receiver=receiver_email,
                    result=result,
                    notify_enabled=notify_enabled,
                    notify_high_risk=notify_high_risk,
                )
                attach_email_notification(result, email_notification)
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
                import traceback
                error_message = str(exc)
                print(f"[fraud_detection_error] task={task.task_id} exc={exc!r}")
                traceback.print_exc()
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
