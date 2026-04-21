import re
import unicodedata
from typing import Any, Optional


_SEPARATOR_RE = re.compile(r"[\s\-_.,，。！？!?、；;:：\"'“”‘’（）()\[\]{}<>《》/\\|`~+]+")
_ACTUAL_URL_RE = re.compile(
    r"(https?://|www\.|[a-z0-9][a-z0-9.-]{1,}\.(com|cn|net|top|xyz|cc|vip|shop|site|live|info|biz|app|link)\b)",
    re.IGNORECASE,
)

_LAW_ENFORCEMENT_TOKENS = (
    "警察",
    "民警",
    "警官",
    "公安",
    "公安机关",
    "派出所",
    "刑警",
    "网警",
    "公检法",
    "检察院",
    "法院",
    "反诈中心",
)

_MONEY_TRANSFER_TOKENS = (
    "转账",
    "汇款",
    "打钱",
    "付款",
    "缴费",
    "保证金",
    "指定账户",
    "安全账户",
    "监管账户",
    "审查账户",
    "资金核验",
    "资金清查",
    "自证清白",
)

_PRESSURE_TOKENS = (
    "马上",
    "立刻",
    "立即",
    "现在",
    "否则",
    "不然",
    "报警",
    "冻结",
    "逮捕",
    "拘留",
    "通缉",
    "传唤",
    "配合调查",
    "涉嫌",
    "涉案",
    "洗钱",
)

_CUSTOMER_SERVICE_TOKENS = ("客服", "平台", "商家", "快递", "航空", "票务", "银行客服")
_REFUND_TOKENS = ("退款", "退费", "理赔", "赔付", "改签", "取消会员", "关闭百万保障")
_SENSITIVE_ACTION_TOKENS = (
    "验证码",
    "动态码",
    "银行卡",
    "身份证",
    "链接",
    "下载",
    "安装",
    "屏幕共享",
    "共享屏幕",
    "远程协助",
    "远程控制",
)
_TASK_REBATE_TOKENS = ("刷单", "做任务", "点赞", "关注", "返利", "佣金", "兼职")
_ADVANCE_PAYMENT_TOKENS = ("垫付", "先付", "充值", "保证金", "手续费", "解冻费", "工本费", "刷流水")
_LOAN_TOKENS = ("贷款", "放款", "额度", "借款", "网贷")
_INVESTMENT_HOOK_TOKENS = ("老师", "分析师", "带单", "内幕消息", "稳赚", "保本", "高收益", "翻倍")
_INVESTMENT_ACTION_TOKENS = ("投资", "理财", "虚拟币", "usdt", "充值", "转账", "入金", "平台")
_ROMANCE_TOKENS = ("网恋", "恋爱", "对象", "男朋友", "女朋友", "交友", "相亲")
_NUDE_EXTORTION_TOKENS = ("裸聊", "私密视频", "不雅视频", "偷拍视频")
_EXTORTION_TOKENS = ("勒索", "敲诈", "封口费", "删视频", "发给家人", "转账")
_LEADER_TOKENS = ("领导", "老板", "总监", "主任", "经理")
_FAMILY_TOKENS = ("儿子", "女儿", "孙子", "孙女", "家属", "亲属", "孩子")
_EMERGENCY_TOKENS = ("出事", "被抓", "车祸", "手术", "急救", "拘留")
_CREDIT_REPAIR_TOKENS = ("注销", "清空", "修复", "消除")
_CREDIT_LOAN_TOKENS = ("征信", "校园贷", "学生贷", "贷款记录")
_REMOTE_CONTROL_TOKENS = ("远程协助", "远程控制", "屏幕共享", "共享屏幕", "会议软件")
_FINANCIAL_ACCOUNT_TOKENS = ("银行卡", "账户", "余额", "转账", "付款", "验证码")
_QR_LINK_TOKENS = ("二维码", "扫码", "扫描二维码", "长按识别", "识别二维码", "点击链接", "点链接", "短链接", "短链", "链接", "网址")
_QR_LINK_REWARD_TOKENS = ("领取补贴", "领补贴", "补贴", "领取奖励", "领奖励", "奖励", "领奖", "返利", "红包", "福利", "提现")
_DATA_COLLECTION_TOKENS = ("填写信息", "填资料", "实名", "实名认证", "登录", "注册", "下载", "安装", "进群", "入群")
_ANTI_FRAUD_SOURCE_TOKENS = (
    "国家反诈中心",
    "反诈中心",
    "公安部刑侦局",
    "警方提醒",
    "公安提醒",
    "反诈提醒",
    "全民反诈",
    "96110",
)
_ANTI_FRAUD_NOTICE_TOKENS = (
    "都是诈骗",
    "谨防诈骗",
    "防范诈骗",
    "反诈提醒",
    "安全提示",
    "如有疑问请拨打96110",
    "请拨打96110咨询",
    "96110咨询",
    "不要点击",
    "不要下载",
    "不要转账",
)

_COMMON_FRAUD_SCENARIOS = (
    {
        "scam_type": "冒充公检法诈骗",
        "id": "law_enforcement_transfer",
        "severity": "hard",
        "score": 90,
        "groups": (
            ("冒充执法机关线索", _LAW_ENFORCEMENT_TOKENS),
            ("资金操作要求", _MONEY_TRANSFER_TOKENS),
        ),
        "boosts": (("催促或威胁施压", _PRESSURE_TOKENS, 4),),
        "warning_message": "对方自称警察或公检法并要求转账到指定账户，这是典型诈骗红线。立即停止转账，挂断电话，并通过 110 或 96110 核实。",
    },
    {
        "scam_type": "冒充客服退款诈骗",
        "score": 88,
        "groups": (
            ("冒充客服或平台", _CUSTOMER_SERVICE_TOKENS),
            ("退款/理赔/改签诱导", _REFUND_TOKENS),
            ("索要敏感信息或远程操作", _SENSITIVE_ACTION_TOKENS),
        ),
        "warning_message": "冒充客服以退款、理赔、改签为由索要验证码、银行卡或要求屏幕共享，属于高风险诈骗。请停止操作并通过官方 App 或客服电话核实。",
    },
    {
        "scam_type": "刷单返利诈骗",
        "score": 88,
        "groups": (
            ("刷单/任务/返利诱导", _TASK_REBATE_TOKENS),
            ("垫付或充值要求", _ADVANCE_PAYMENT_TOKENS),
        ),
        "warning_message": "刷单返利、做任务先垫付或充值是典型诈骗。不要继续付款或提现解冻操作。",
    },
    {
        "scam_type": "虚假贷款诈骗",
        "score": 88,
        "groups": (
            ("贷款/放款诱导", _LOAN_TOKENS),
            ("前置收费要求", _ADVANCE_PAYMENT_TOKENS),
        ),
        "warning_message": "贷款放款前要求缴纳保证金、解冻费、刷流水或手续费是典型虚假贷款诈骗。正规贷款不会先收费。",
    },
    {
        "scam_type": "虚假投资理财诈骗",
        "score": 86,
        "groups": (
            ("投资带单或高收益话术", _INVESTMENT_HOOK_TOKENS),
            ("投资入金或虚拟币操作", _INVESTMENT_ACTION_TOKENS),
        ),
        "warning_message": "所谓内幕消息、老师带单、稳赚高收益并诱导充值或转账，属于高风险投资理财诈骗。",
    },
    {
        "scam_type": "杀猪盘/网恋投资诈骗",
        "score": 86,
        "groups": (
            ("网恋或交友关系诱导", _ROMANCE_TOKENS),
            ("投资理财诱导", _INVESTMENT_ACTION_TOKENS),
        ),
        "warning_message": "网恋或交友对象诱导投资、理财、虚拟币入金，是典型杀猪盘诈骗。请停止转账并保留聊天记录。",
    },
    {
        "scam_type": "裸聊敲诈诈骗",
        "score": 94,
        "groups": (
            ("裸聊或私密视频", _NUDE_EXTORTION_TOKENS),
            ("敲诈勒索要求", _EXTORTION_TOKENS),
        ),
        "warning_message": "裸聊或私密视频被威胁传播并要求转账，是高风险敲诈诈骗。不要转账，保留证据并报警。",
    },
    {
        "scam_type": "冒充领导诈骗",
        "score": 88,
        "groups": (
            ("冒充领导或上级", _LEADER_TOKENS),
            ("资金操作要求", _MONEY_TRANSFER_TOKENS),
        ),
        "boosts": (("紧急施压", _PRESSURE_TOKENS, 2),),
        "warning_message": "领导、老板或上级通过聊天要求紧急转账，应按单位财务制度线下复核，切勿直接付款。",
    },
    {
        "scam_type": "冒充亲属紧急求助诈骗",
        "score": 88,
        "groups": (
            ("亲属身份", _FAMILY_TOKENS),
            ("紧急事故话术", _EMERGENCY_TOKENS),
            ("资金操作要求", _MONEY_TRANSFER_TOKENS),
        ),
        "warning_message": "自称亲属出事、被抓、急救并要求汇款，是高风险冒充亲属诈骗。请通过原有号码或家人核实。",
    },
    {
        "scam_type": "征信修复/注销校园贷诈骗",
        "score": 86,
        "groups": (
            ("征信修复或注销动作", _CREDIT_REPAIR_TOKENS),
            ("征信/校园贷话题", _CREDIT_LOAN_TOKENS),
            ("收费或敏感操作", _ADVANCE_PAYMENT_TOKENS + _SENSITIVE_ACTION_TOKENS),
        ),
        "warning_message": "声称能注销校园贷、修复征信并要求缴费、转账或提供验证码，是典型诈骗。",
    },
    {
        "scam_type": "远程控制诈骗",
        "score": 86,
        "groups": (
            ("远程控制或屏幕共享", _REMOTE_CONTROL_TOKENS),
            ("账户或资金信息", _FINANCIAL_ACCOUNT_TOKENS),
        ),
        "warning_message": "对方要求远程协助、屏幕共享并查看银行卡、账户或验证码，属于高风险诈骗。请立即断开连接。",
    },
    {
        "scam_type": "二维码/链接诱导诈骗",
        "id": "qr_link_reward_lure",
        "score": 88,
        "groups": (
            ("二维码或链接引导", _QR_LINK_TOKENS),
            ("补贴/奖励/返利诱导", _QR_LINK_REWARD_TOKENS),
        ),
        "boosts": (
            ("附带信息提交或安装动作", _DATA_COLLECTION_TOKENS, 2),
            ("附带敏感操作", _SENSITIVE_ACTION_TOKENS, 2),
        ),
        "warning_message": "对方通过二维码或链接诱导领取补贴、奖励、返利或红包，属于高风险诈骗引流。不要扫码、不要点链接、不要继续填写信息或下载应用。",
    },
)


def _text_variants(text: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    compact = _SEPARATOR_RE.sub("", normalized)
    return normalized, compact


def _matched_tokens(text: str, tokens: tuple[str, ...]) -> list[str]:
    variants = _text_variants(text)
    matched: list[str] = []
    for token in tokens:
        token_variants = _text_variants(token)
        if any(token_variant and token_variant in variant for token_variant in token_variants for variant in variants):
            matched.append(token)
    return matched


def _find_token_spans(text: str, token: str) -> list[dict[str, Any]]:
    normalized_text = unicodedata.normalize("NFKC", str(text or ""))
    normalized_token = unicodedata.normalize("NFKC", str(token or ""))
    lowered_text = normalized_text.lower()
    lowered_token = normalized_token.lower()
    spans: list[dict[str, Any]] = []
    if not lowered_token:
        return spans
    start = 0
    while True:
        index = lowered_text.find(lowered_token, start)
        if index < 0:
            break
        end = index + len(lowered_token)
        spans.append({"text": normalized_text[index:end], "start": index, "end": end})
        start = end
    return spans


def _build_scenario_warning(text: str, scenario: dict[str, Any]) -> Optional[dict[str, Any]]:
    score = int(scenario["score"])
    base_score = score
    scenario_id = str(scenario.get("id") or str(scenario["scam_type"])).strip()
    rule_id = f"critical:{scenario_id}"
    severity = str(scenario.get("severity") or "hard").strip().lower()
    clues: list[str] = []
    hard_signal_count = 0
    matched_groups: list[dict[str, str]] = []
    boost_breakdown: list[dict[str, Any]] = []
    matched_spans: list[dict[str, Any]] = []

    for label, tokens in scenario["groups"]:
        matched = _matched_tokens(text, tokens)
        if not matched:
            return None
        hard_signal_count += len(matched)
        clues.append(f"{label}: {matched[0]}")
        matched_groups.append({"label": str(label), "token": str(matched[0])})
        matched_spans.extend([{"rule_id": rule_id, **span} for span in _find_token_spans(text, str(matched[0]))])

    for label, tokens, boost in scenario.get("boosts", ()):
        matched = _matched_tokens(text, tokens)
        if matched:
            score += int(boost)
            hard_signal_count += len(matched)
            clues.append(f"{label}: {matched[0]}")
            boost_breakdown.append({"label": str(label), "token": str(matched[0]), "score": int(boost)})
            matched_spans.extend([{"rule_id": rule_id, **span} for span in _find_token_spans(text, str(matched[0]))])

    return {
        "risk_score": min(score, 98),
        "risk_level": "high",
        "risk_clues": clues,
        "warning_message": str(scenario["warning_message"]),
        "source": "critical_text_guardrail",
        "is_preliminary": True,
        "critical_guardrail_triggered": True,
        "scam_type": str(scenario["scam_type"]),
        "guardian_alert": True,
        "hard_signal_count": hard_signal_count,
        "signal_severity": severity,
        "matched_rule_ids": [rule_id],
        "matched_spans": matched_spans[:12],
        "source_priority": ["critical_text_guardrail", "fast_text_rules", "local_rag", "llm_review"],
        "popup_severity": "blocking",
        "voice_warning_required": True,
        "guardian_intervention_required": True,
        "score_breakdown": {
            "source": "critical_text_guardrail",
            "severity": severity,
            "base_score": base_score,
            "boost_score": max(0, score - base_score),
            "final_score": min(score, 98),
            "floor_score": min(score, 98),
            "hard_signal_count": hard_signal_count,
            "matched_groups": matched_groups,
            "boosts": boost_breakdown,
        },
    }


def is_authoritative_anti_fraud_notice(text: str) -> bool:
    normalized_text = unicodedata.normalize("NFKC", str(text or "")).strip()
    lowered_text = normalized_text.lower()
    if not normalized_text:
        return False
    if _ACTUAL_URL_RE.search(lowered_text):
        return False

    has_source = any(token in normalized_text for token in _ANTI_FRAUD_SOURCE_TOKENS)
    has_notice = any(token in normalized_text for token in _ANTI_FRAUD_NOTICE_TOKENS)
    has_reminder_shape = bool(
        re.search(r"凡是.{0,48}(都是诈骗|谨防诈骗)", normalized_text)
        or re.search(r"提醒您.{0,48}(诈骗|96110)", normalized_text)
    )
    has_hotline = "96110" in normalized_text

    return (has_source and (has_notice or has_reminder_shape)) or (has_hotline and has_reminder_shape)


def build_critical_text_guardrail_warning(text: str) -> Optional[dict[str, Any]]:
    """Detect deterministic high-risk fraud patterns that must not be left to LLM scoring."""
    if is_authoritative_anti_fraud_notice(text):
        return None

    for scenario in _COMMON_FRAUD_SCENARIOS:
        warning = _build_scenario_warning(text, scenario)
        if warning is not None:
            return warning

    return None


def apply_critical_warning_floor(result: dict[str, Any], early_warning: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Prevent low LLM scores from overriding deterministic high-risk early warnings."""
    if not early_warning or not (
        early_warning.get("source") == "critical_text_guardrail"
        or bool(early_warning.get("critical_guardrail_triggered"))
    ):
        return result

    floor_score = int(early_warning.get("risk_score") or 0)
    current_score = int(result.get("risk_score") or 0)
    guarded = dict(result)
    guarded["risk_level"] = "high"
    guarded["guardian_alert"] = True
    guarded["critical_guardrail_triggered"] = True
    guarded["early_warning_score"] = floor_score
    guarded["early_warning_level"] = "high"
    guarded["scam_type"] = guarded.get("scam_type") or early_warning.get("scam_type")
    guarded["warning_message"] = early_warning.get("warning_message") or guarded.get("warning_message")
    guarded["risk_clues"] = list(
        dict.fromkeys(list(early_warning.get("risk_clues") or []) + list(guarded.get("risk_clues") or []))
    )[:8]

    for key in (
        "signal_severity",
        "matched_rule_ids",
        "popup_severity",
        "voice_warning_required",
        "guardian_intervention_required",
        "matched_spans",
        "source_priority",
        "score_breakdown",
    ):
        if key in early_warning:
            guarded[key] = early_warning.get(key)

    if floor_score <= current_score:
        return guarded

    guarded["risk_score"] = floor_score
    guarded["score_source"] = "critical_text_guardrail_floor"
    return guarded
