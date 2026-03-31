"""
风险检测模块
从 rag/src/fraud_rag/detector.py 迁移
基于知识检索结果进行精细化风险分级
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.brain.rag.models import SearchHit, RiskAssessmentResult


# 诈骗子类型建议映射
# 键: 子类型标识, 值: 针对性建议
SUBTYPE_ADVICE = {
    # 投资诈骗
    "investment_fraud": "不要继续充值、跟单或点击开户链接，先核验平台资质和资金流向。",
    "fake_investment_dashboard": "高收益截图和群内统一晒单常是诱导入金的诈骗前置材料。",
    "fake_job_training_poster": "警惕先交培训费、开通贷款或承诺包就业的招聘流程。",

    # 客服/退款诈骗
    "customer_service_fraud": "不要扫码退款、共享屏幕、下载陌生会议软件或进行所谓资金验证。",
    "fake_customer_service_refund": "退款理赔应只走官方 App 或官方客服电话，不要点陌生链接。",

    # AI 拟声诈骗
    "ai_voice_family_urgency": "通过原联系方式或线下方式二次确认亲友身份，不要仅凭语音或截图转账。",

    # 信用卡诈骗
    "credit_card_fraud": "不要出借、套现或代办信用卡，注意异常验证码和扣款信息。",

    # 两卡/跑分诈骗
    "card_running_score": "不要出租银行卡、支付账户、电话卡或参与代收代付跑分。",
    "bank_card_running_score": "不要出租银行卡、支付账户、电话卡或参与代收代付跑分。",

    # 公检法诈骗
    "fake_police_notice": "公检法不会通过电话、网络要求转账到安全账户，如有疑问请直接到当地派出所核实。",

    # 伪造转账
    "fake_transfer_receipt": "不要仅凭转账截图发货或继续付款，应以真实到账和官方流水为准。",

    # 二维码/安装诈骗
    "suspicious_qr_install": "不要扫描陌生二维码安装应用，也不要为所谓退款或解冻授予远程控制权限。",

    # 法律案例
    "fraud_law": "参考相关法律条文，了解自身权益和诈骗行为的法律后果。",
    "fraud_case": "参考类似案例，了解诈骗手法和防范要点。",
}


class RiskDetector:
    """
    风险检测器

    基于知识检索结果的多维度风险评估：
    - 相似度分数: 与已知诈骗知识的匹配程度
    - 类别覆盖: 同时命中案例、法律、图片说明的证据强度
    - 子类型匹配: 识别具体诈骗手法

    风险等级判定逻辑:
    - HIGH: 最佳分数 >= 高阈值，或证据综合分数达标
    - MEDIUM: 最佳分数 >= 中阈值，或有案例+法律依据
    - LOW: 未达到上述条件
    """

    def __init__(
        self,
        high_threshold: float = 0.32,
        medium_threshold: float = 0.18,
    ):
        """
        初始化风险检测器

        Args:
            high_threshold: 高风险阈值 (默认 0.32)
            medium_threshold: 中风险阈值 (默认 0.18)
        """
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold

    def assess(
        self,
        query_text: str,
        hits: list[SearchHit],
    ) -> RiskAssessmentResult:
        """
        执行风险评估

        Args:
            query_text: 查询文本（用于日志/调试）
            hits: 检索结果列表

        Returns:
            RiskAssessmentResult 包含风险等级、置信度、建议等
        """
        if not hits:
            return RiskAssessmentResult(
                risk_level="low",
                confidence=0.0,
                matched_subtypes=[],
                matched_tags=[],
                recommendations=["未检索到明显关联知识，建议继续人工核验。"],
                hits=[],
            )

        # 聚合分数
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

        # 类别覆盖检查
        has_case = category_scores.get("case", 0.0) > 0
        has_law = category_scores.get("law", 0.0) > 0
        has_photo = category_scores.get("photo_type", 0.0) > 0

        # 证据分数 = 最佳分数 + 类别覆盖加分
        # 加分逻辑：有案例 +0.08, 有法律 +0.05, 有图片 +0.05
        evidence_score = (
            best_score
            + 0.08 * int(has_case)
            + 0.05 * int(has_law)
            + 0.05 * int(has_photo)
        )

        # 判定风险等级
        risk_level = self._determine_risk_level(best_score, evidence_score)

        # 提取 top 子类型和标签
        top_subtypes = [
            name
            for name, _ in sorted(
                subtype_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]
        ]
        top_tags = [
            name
            for name, _ in sorted(
                tag_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:6]
        ]

        # 生成建议
        recommendations = self._generate_recommendations(top_subtypes)

        # 计算置信度
        confidence = min(0.99, round(evidence_score, 4))

        return RiskAssessmentResult(
            risk_level=risk_level,
            confidence=confidence,
            matched_subtypes=top_subtypes,
            matched_tags=top_tags,
            recommendations=recommendations,
            hits=[
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
        )

    def _determine_risk_level(
        self,
        best_score: float,
        evidence_score: float,
    ) -> str:
        """
        判定风险等级

        Args:
            best_score: 最高相似度分数
            evidence_score: 证据综合分数

        Returns:
            "high" | "medium" | "low"
        """
        # 高风险条件:
        # 1. 最佳分数 >= 高阈值
        # 2. 证据分数 >= 高阈值 + 0.08 且 最佳分数 >= 中阈值
        if best_score >= self.high_threshold:
            return "high"
        if evidence_score >= self.high_threshold + 0.08 and best_score >= self.medium_threshold:
            return "high"

        # 中风险条件:
        # 1. 最佳分数 >= 中阈值
        # 2. 证据分数 >= 中阈值 + 0.08
        if best_score >= self.medium_threshold:
            return "medium"
        if evidence_score >= self.medium_threshold + 0.08:
            return "medium"

        return "low"

    def _generate_recommendations(self, subtypes: list[str]) -> list[str]:
        """
        生成针对性建议

        Args:
            subtypes: 匹配到的诈骗子类型列表

        Returns:
            建议列表
        """
        # 基础建议
        recommendations = [
            "暂停转账、扫码、共享屏幕、提供验证码或安装陌生应用。",
            "通过官方客服电话、官方 App 或线下渠道二次核验身份与业务真实性。",
            "保留聊天记录、转账截图、链接、电话号码和图片线索，便于后续处置。",
        ]

        # 根据子类型添加针对性建议
        for subtype in subtypes:
            advice = SUBTYPE_ADVICE.get(subtype)
            if advice:
                recommendations.append(advice)

        # 去重保持顺序
        return self._unique(recommendations)

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        """去重列表保持顺序"""
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    def get_stats(self) -> dict[str, Any]:
        """
        获取检测器统计信息

        Returns:
            统计信息字典
        """
        return {
            "high_threshold": self.high_threshold,
            "medium_threshold": self.medium_threshold,
            "supported_subtypes": list(SUBTYPE_ADVICE.keys()),
        }
