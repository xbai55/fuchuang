from typing import Any, Optional


def normalize_output_language(language: Optional[str]) -> str:
    value = (language or "").strip().lower()
    if value.startswith("en"):
        return "en-US"
    return "zh-CN"


def is_english_output(language: Optional[str]) -> bool:
    return normalize_output_language(language) == "en-US"


SINGLE_PASS_SYSTEM_PROMPT_EN = """You are a professional anti-fraud analysis engine.

Return exactly two parts.

Part 1: metadata, exactly 5 lines:
RISK_SCORE: <0-100 integer>
RISK_LEVEL: <low|medium|high>
SCAM_TYPE: <short fraud type or not_identified>
GUARDIAN_ALERT: <true|false>
WARNING_MESSAGE: <one concise user-facing warning>

Then output the separator exactly:
---REPORT---

Part 2: a complete Markdown report.

IMPORTANT OUTPUT LANGUAGE RULE:
- Write WARNING_MESSAGE and the entire Markdown report in English only.
- Keep metadata keys exactly as specified above.
- Keep RISK_LEVEL values as low, medium, or high.
- Do not include Chinese user-facing text in the output.

Report requirements:
1. Summarize the analyzed content and media evidence.
2. Explain the specific fraud indicators and uncertainty.
3. Justify the RISK_SCORE and risk level.
4. Provide concrete next actions for the user.
5. If risk is high, recommend stopping payment, preserving evidence, and contacting guardians or official hotlines.
"""

CRITICAL_FRAUD_GUARDRAIL_ZH = """

硬性高风险规则：
- 命中以下任一红线组合时，RISK_SCORE 必须不低于 85，RISK_LEVEL 必须为 high；如果伴随“马上/立即/否则/报警/冻结/逮捕/通缉/配合调查”等催促或威胁，RISK_SCORE 必须不低于 90。
- 红线组合包括：冒充公检法/警察要求转账或转入指定账户；冒充客服退款/理赔/改签并索要验证码、银行卡、链接下载或屏幕共享；刷单返利/做任务要求垫付、充值或保证金；贷款放款前收保证金、解冻费、手续费或刷流水；投资老师/内幕消息/稳赚高收益诱导充值、USDT、虚拟币或转账；网恋交友诱导投资；裸聊或私密视频敲诈勒索；冒充领导要求紧急转账；冒充亲属出事、被抓、急救并要求汇款；征信修复/注销校园贷要求缴费、转账或验证码；远程协助/屏幕共享查看银行卡、账户、余额或验证码。
- 对于“二维码/扫码/长按识别/短链接/点击链接”等引导，只要伴随领取补贴、领取奖励、返利、红包、退款、进群、下载、安装、登录或填写信息等动作，不得判为白样本，至少给中风险；若同时出现验证码、银行卡、转账或客服退款话术，RISK_SCORE 必须不低于 85。
- 若文本明显是国家反诈中心、公安机关或 96110 发布的官方反诈提醒、科普短信或安全公告，例如出现“凡是……都是诈骗”“如有疑问请拨打96110咨询”等表述，且消息本身未提供待点击外链、二维码、收款账户或转账指令，应按官方反诈提醒处理，不应判为诈骗样本。
- 不得因为用户用第一人称咨询、转述或求助而降低上述红线风险。
"""

CRITICAL_FRAUD_GUARDRAIL_EN = """

Mandatory high-risk rule:
- If the original content matches any common fraud red-flag combination, RISK_SCORE must be at least 85 and RISK_LEVEL must be high. If urgency or threats are also present, RISK_SCORE must be at least 90.
- Red-flag combinations include law-enforcement impersonation plus transfer/designated account; fake customer-service refund/claim/ticket-change plus verification code, bank card, download link, or screen sharing; task rebate or fake part-time job plus advance payment/recharge/deposit; loan approval plus upfront fees, unfreezing fees, processing fees, or fake transaction flow; investment mentor, insider information, guaranteed high return, crypto/USDT recharge, or transfer; romance plus investment; nude-chat or private-video extortion; boss/leader emergency transfer; family emergency/arrest/medical treatment plus remittance; credit repair or campus-loan cancellation plus payment, transfer, or verification code; remote assistance or screen sharing plus bank card, account, balance, or verification code.
- Do not downgrade this red-flag scenario merely because the user is asking, quoting, or reporting it in first person.
"""


def build_single_pass_system_prompt(base_prompt: str, language: Optional[str]) -> str:
    if is_english_output(language):
        return SINGLE_PASS_SYSTEM_PROMPT_EN + CRITICAL_FRAUD_GUARDRAIL_EN
    return str(base_prompt or "") + CRITICAL_FRAUD_GUARDRAIL_ZH


def english_fast_warning_message(risk_level: str, source: str = "", has_media: bool = False) -> str:
    normalized_level = (risk_level or "low").strip().lower()
    source_text = (source or "").strip().lower()
    if normalized_level == "high":
        return (
            "Stop immediately. This interaction shows high-risk fraud indicators. "
            "Do not transfer money, share verification codes, install remote-control tools, "
            "or continue private communication. Preserve evidence and contact a guardian or official hotline."
        )
    if normalized_level == "medium":
        return (
            "Proceed with caution. Suspicious fraud indicators were detected. "
            "Verify the identity through an official channel before taking any action."
        )
    if "media" in source_text or has_media:
        return (
            "Initial media screening is in progress. Do not act on payment, account, "
            "or identity requests until the full analysis is complete."
        )
    return (
        "Initial screening did not find clear high-risk indicators, but stay cautious. "
        "Avoid transfers or sharing sensitive information before verification."
    )


def english_fast_warning_clues(risk_level: str, source: str = "", has_media: bool = False) -> list[str]:
    normalized_level = (risk_level or "low").strip().lower()
    source_text = (source or "").strip().lower()
    if normalized_level == "high":
        return [
            "High-risk fraud pattern detected",
            "Potential request for money, credentials, verification codes, or remote access",
            "Immediate interruption and independent verification are recommended",
        ]
    if normalized_level == "medium":
        return [
            "Suspicious content or context detected",
            "Identity and intent should be verified through an official channel",
        ]
    if "media" in source_text or has_media:
        return ["Media content requires full OCR, speech, or video analysis before action"]
    return ["No clear high-risk indicator was found in the fast screening stage"]


def localize_early_warning(
    warning: Optional[dict[str, Any]],
    language: Optional[str],
    has_media: bool = False,
) -> Optional[dict[str, Any]]:
    if not warning or not is_english_output(language):
        return warning

    localized = dict(warning)
    risk_level = str(localized.get("risk_level") or "low")
    source = str(localized.get("source") or "")
    localized["warning_message"] = english_fast_warning_message(risk_level, source, has_media)
    localized["risk_clues"] = english_fast_warning_clues(risk_level, source, has_media)
    localized["language"] = "en-US"
    return localized
