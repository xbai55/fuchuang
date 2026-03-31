from __future__ import annotations

from collections import defaultdict
from typing import Any

from .config import WarningConfig
from .models import SearchHit


SUBTYPE_ADVICE = {
    "investment_fraud": "不要继续充值、跟单或点击开户链接，先核验平台资质和资金流向。",
    "job_training_fraud": "警惕先交培训费、开通贷款或承诺包就业的招聘流程。",
    "fake_job_training_poster": "警惕先交培训费、开通贷款或承诺包就业的招聘流程。",
    "customer_service_fraud": "不要扫码退款、共享屏幕、下载陌生会议软件或进行所谓资金验证。",
    "ai_voice_family_urgency": "通过原联系方式或线下方式二次确认亲友身份，不要仅凭语音或截图转账。",
    "credit_card_fraud": "不要出借、套现或代办信用卡，注意异常验证码和扣款信息。",
    "card_running_score": "不要出租银行卡、支付账户、电话卡或参与代收代付跑分。",
    "fake_investment_dashboard": "高收益截图和群内统一晒单常是诱导入金的诈骗前置材料。",
    "fake_customer_service_refund": "退款理赔应只走官方 App 或官方客服电话，不要点陌生链接。",
    "suspicious_qr_install": "不要扫描陌生二维码安装应用，也不要为所谓退款或解冻授予远程控制权限。",
    "fake_transfer_receipt": "不要仅凭转账截图发货或继续付款，应以真实到账和官方流水为准。",
}


def assess_risk(query_text: str, hits: list[SearchHit], warning: WarningConfig) -> dict[str, Any]:
    if not hits:
        return {
            "risk_level": "low",
            "confidence": 0.0,
            "matched_subtypes": [],
            "matched_tags": [],
            "recommendations": ["未检索到明显关联知识，建议继续人工核验。"],
            "hits": [],
        }

    best_score = hits[0].score
    category_scores: dict[str, float] = defaultdict(float)
    subtype_scores: dict[str, float] = defaultdict(float)
    tag_scores: dict[str, float] = defaultdict(float)

    for hit in hits:
        category_scores[hit.chunk.category] += hit.score
        if hit.chunk.subtype:
            subtype_scores[hit.chunk.subtype] += hit.score
        for tag in hit.chunk.tags:
            tag_scores[tag] += hit.score

    has_case = category_scores.get("case", 0.0) > 0
    has_law = category_scores.get("law", 0.0) > 0
    has_photo = category_scores.get("photo_type", 0.0) > 0

    evidence_score = best_score + 0.08 * int(has_case) + 0.05 * int(has_law) + 0.05 * int(has_photo)

    if best_score >= warning.high_threshold or (evidence_score >= warning.high_threshold + 0.08 and best_score >= warning.medium_threshold):
        risk_level = "high"
    elif (
        best_score >= warning.medium_threshold
        or evidence_score >= warning.medium_threshold + 0.08
        or (best_score >= warning.medium_threshold * 0.8 and (has_case or has_photo) and has_law)
    ):
        risk_level = "medium"
    else:
        risk_level = "low"

    top_subtypes = [name for name, _ in sorted(subtype_scores.items(), key=lambda item: item[1], reverse=True)[:3]]
    top_tags = [name for name, _ in sorted(tag_scores.items(), key=lambda item: item[1], reverse=True)[:6]]

    recommendations = [
        "暂停转账、扫码、共享屏幕、提供验证码或安装陌生应用。",
        "通过官方客服电话、官方 App 或线下渠道二次核验身份与业务真实性。",
        "保留聊天记录、转账截图、链接、电话号码和图片线索，便于后续处置。",
    ]
    for subtype in top_subtypes:
        advice = SUBTYPE_ADVICE.get(subtype)
        if advice:
            recommendations.append(advice)
    recommendations = _unique(recommendations)

    confidence = min(0.99, round(evidence_score, 4))

    return {
        "risk_level": risk_level,
        "confidence": confidence,
        "matched_subtypes": top_subtypes,
        "matched_tags": top_tags,
        "recommendations": recommendations,
        "hits": [
            {
                "score": round(hit.score, 6),
                "title": hit.chunk.title,
                "category": hit.chunk.category,
                "subtype": hit.chunk.subtype,
                "source_url": hit.chunk.source_url,
                "tags": hit.chunk.tags,
            }
            for hit in hits
        ],
    }


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
