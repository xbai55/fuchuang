import asyncio
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import Any


SENDER = "2036689220@qq.com"
PASSWORD = "xtdqjalxubxgdihc"
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SUBJECT = "【天枢明御】诈骗预警通知"


def _is_high_risk(result: dict[str, Any]) -> bool:
    level = str(result.get("risk_level") or "").strip().lower()
    return level in {"high", "高", "高危", "高风险"}


def _build_email_content(result: dict[str, Any]) -> str:
    scam_type = str(result.get("scam_type") or "").strip() or "未知诈骗类型"
    detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""尊敬的监护人/紧急联系人：

您好。

天枢明御反诈系统检测到一起高风险诈骗预警事件。为保护当事人的资金与账号安全，请您尽快联系当事人进行确认和提醒。

一、预警摘要
预警时间：{detected_at}
风险等级：高危
疑似类型：{scam_type}

二、建议处置
1. 请立即联系当事人，确认其当前是否正在与陌生人沟通或进行资金、账号相关操作。
2. 请提醒当事人立即停止转账、扫码付款、提供验证码、开启屏幕共享、下载陌生软件等高风险行为。
3. 如已发生资金损失或个人信息泄露，请尽快保留聊天记录、转账凭证等证据，并联系银行、平台客服或拨打 110 / 96110 咨询处理。

三、安全提示
本邮件仅用于风险预警，不包含当事人的具体沟通内容。请以电话或当面方式与当事人核实情况，避免通过可疑链接或陌生联系方式继续沟通。

天枢明御反诈预警系统
"""


def _send_high_risk_email_sync(receiver: str, result: dict[str, Any]) -> dict[str, Any]:
    msg = MIMEText(_build_email_content(result), "plain", "utf-8")
    msg["Subject"] = SUBJECT
    msg["From"] = SENDER
    msg["To"] = receiver

    smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
    try:
        smtp.login(SENDER, PASSWORD)
        smtp.sendmail(SENDER, receiver, msg.as_string())
    finally:
        smtp.quit()

    return {
        "notified": True,
        "channel": "email",
        "provider": "qq_smtp",
        "status": "sent",
        "receiver": receiver,
        "scam_type": str(result.get("scam_type") or "").strip() or "未知诈骗类型",
    }


async def send_high_risk_email_if_needed(
    *,
    receiver: str,
    result: dict[str, Any],
    notify_enabled: bool,
    notify_high_risk: bool,
) -> dict[str, Any]:
    receiver = (receiver or "").strip()

    if not _is_high_risk(result):
        return {"notified": False, "channel": "email", "status": "not_high_risk"}

    if not (notify_enabled and notify_high_risk):
        return {"notified": False, "channel": "email", "status": "disabled"}

    if "@" not in receiver:
        return {
            "notified": False,
            "channel": "email",
            "status": "missing_receiver",
            "failure_reason": "No valid guardian email is configured in contacts.",
        }

    try:
        return await asyncio.to_thread(_send_high_risk_email_sync, receiver, result)
    except Exception as exc:
        return {
            "notified": False,
            "channel": "email",
            "provider": "qq_smtp",
            "status": "failed",
            "receiver": receiver,
            "failure_reason": str(exc),
        }


def attach_email_notification(
    result: dict[str, Any],
    email_notification: dict[str, Any],
) -> None:
    existing = result.get("guardian_notification")
    if isinstance(existing, dict):
        existing["email"] = email_notification
        result["guardian_notification"] = existing
        return

    result["guardian_notification"] = {"email": email_notification}
