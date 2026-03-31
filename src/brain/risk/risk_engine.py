"""
Risk assessment engine.
Uses LLM to evaluate fraud risk based on perception and RAG results.
增强版：集成 RAG RiskDetector 进行精细化评估
"""
from typing import Dict, Any, List, Optional

from src.core.models import (
    GlobalState,
    RiskAssessment,
    RiskLevel,
    PerceptionResult,
    RetrievedCase,
)
from src.core.interfaces import LLMClient
from src.core.utils import load_node_config


class RiskEngine:
    """
    Risk assessment engine using LLM and RAG.

    评估维度：
    - Perception results (text, fake analysis)
    - Retrieved similar cases (RAG 检索)
    - RAG RiskDetector 精细化分析 (8种诈骗子类型)
    - User context

    双重评估机制：
    1. LLM 综合评估 - 理解力强，处理复杂场景
    2. RAG Detector 规则评估 - 基于知识库匹配，可解释性强
    """

    # Risk level thresholds
    LOW_THRESHOLD = 40
    HIGH_THRESHOLD = 75

    # Default system prompt for risk assessment
    DEFAULT_SYSTEM_PROMPT = """你是一位专业的反诈骗风险评估专家。

请根据提供的信息，对潜在的诈骗风险进行全面评估。

输出必须是一个有效的JSON对象，包含以下字段：
{
    "risk_score": 0-100的整数，表示风险分数,
    "risk_level": "low" | "medium" | "high"，表示风险等级,
    "scam_type": "识别的诈骗类型名称",
    "risk_clues": ["风险线索1", "风险线索2", ...],
    "reasoning": "评估理由的简要说明"
}

评估标准：
- risk_score < 40: 低风险 (low)
- 40 <= risk_score <= 75: 中风险 (medium)
- risk_score > 75: 高风险 (high)

请确保JSON格式正确，可以被解析。"""

    # Default user prompt template
    DEFAULT_USER_TEMPLATE = """请对以下情况进行风险评估：

## 用户输入内容
{input_text}

## 多模态分析结果
{perception_summary}

## 相似案例参考
{similar_cases}

## RAG 知识库分析
{rag_analysis}

## 用户画像
- 用户类型: {user_role}

请输出JSON格式的风险评估结果。"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        use_rag_detector: bool = True,
        rag_high_threshold: float = 0.32,
        rag_medium_threshold: float = 0.18,
    ):
        """
        Initialize risk engine.

        Args:
            llm_client: Optional LLM client (creates default if not provided)
            use_rag_detector: 是否使用 RAG 风险检测器
            rag_high_threshold: RAG 高风险阈值
            rag_medium_threshold: RAG 中风险阈值
        """
        config = load_node_config("risk_assessment")

        if llm_client:
            self.llm = llm_client
        else:
            self.llm = LLMClient.from_config(config)

        self.system_prompt = config.get("system_prompt", self.DEFAULT_SYSTEM_PROMPT)
        self.user_template = config.get("user_prompt", self.DEFAULT_USER_TEMPLATE)

        # RAG Detector 配置
        self.use_rag_detector = use_rag_detector
        self._rag_detector = None
        if use_rag_detector:
            from src.brain.rag.detector import RiskDetector
            self._rag_detector = RiskDetector(
                high_threshold=rag_high_threshold,
                medium_threshold=rag_medium_threshold,
            )

    async def assess(
        self,
        state: GlobalState,
    ) -> RiskAssessment:
        """
        Assess fraud risk based on current state.

        评估流程：
        1. 使用 RAG Detector 进行知识库匹配评估
        2. 使用 LLM 进行综合理解评估
        3. 融合两种评估结果

        Args:
            state: Current workflow state

        Returns:
            RiskAssessment result
        """
        # 步骤 1: RAG 基于知识库的评估
        rag_assessment = None
        if self.use_rag_detector and self._rag_detector:
            rag_assessment = await self._assess_with_rag(state)

        # 步骤 2: LLM 综合评估
        llm_assessment = await self._assess_with_llm(state, rag_assessment)

        # 步骤 3: 融合评估结果
        if rag_assessment:
            return self._merge_assessments(llm_assessment, rag_assessment)

        return llm_assessment

    async def _assess_with_rag(
        self,
        state: GlobalState,
    ) -> Optional[RiskAssessment]:
        """
        使用 RAG RiskDetector 进行评估

        Args:
            state: Global state

        Returns:
            RiskAssessment or None
        """
        if not self._rag_detector:
            return None

        from src.brain.rag.models import create_search_hit_from_retrieved_case

        query = state.get_combined_text()
        if not query:
            return None

        # 构建 SearchHit 列表
        search_hits = [
            create_search_hit_from_retrieved_case(
                case,
                category=getattr(case, 'category', 'case'),
                subtype=getattr(case, 'subtype', None),
                tags=getattr(case, 'tags', []),
            )
            for case in state.similar_cases
        ]

        # 执行 RAG 评估
        result = self._rag_detector.assess(query, search_hits)

        # 转换为 RiskAssessment
        score = int(result.confidence * 100)

        # 映射风险等级
        level_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
        }
        level = level_map.get(result.risk_level, RiskLevel.LOW)

        # 提取诈骗类型
        scam_type = result.matched_subtypes[0] if result.matched_subtypes else ""

        return RiskAssessment(
            score=score,
            level=level,
            scam_type=scam_type,
            clues=result.matched_tags,
            reasoning=f"RAG知识库匹配: 命中{len(result.hits)}条相关知识, 子类型: {', '.join(result.matched_subtypes)}",
        )

    async def _assess_with_llm(
        self,
        state: GlobalState,
        rag_assessment: Optional[RiskAssessment] = None,
    ) -> RiskAssessment:
        """
        使用 LLM 进行综合评估

        Args:
            state: Global state
            rag_assessment: 可选的 RAG 评估结果

        Returns:
            RiskAssessment
        """
        # Build context from state
        context = self._build_assessment_context(state, rag_assessment)

        # Build user prompt
        user_prompt = self.user_template.format(**context)

        try:
            # Call LLM
            response = await self.llm.achat(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                parse_json=True,
            )

            # Parse result
            if response.parsed_json:
                return self._parse_assessment(response.parsed_json)
            else:
                # Fallback if JSON parsing failed
                return self._fallback_assessment(state)

        except Exception as e:
            print(f"[错误] 风险评估失败: {e}")
            return self._fallback_assessment(state)

    def _build_assessment_context(
        self,
        state: GlobalState,
        rag_assessment: Optional[RiskAssessment] = None,
    ) -> Dict[str, Any]:
        """
        Build context dict for prompt formatting.

        Args:
            state: Global state
            rag_assessment: RAG 评估结果

        Returns:
            Context dictionary
        """
        # Get combined text
        input_text = state.get_combined_text()

        # Build perception summary
        perception_parts = []
        for result in state.perception_results:
            summary = result.to_prompt_text()
            if summary:
                perception_parts.append(summary)
        perception_summary = "\n\n".join(perception_parts) if perception_parts else "无多模态分析结果"

        # Build similar cases text
        cases_text = self._format_similar_cases(state.similar_cases)

        # Build RAG analysis text
        rag_analysis = self._format_rag_analysis(rag_assessment)

        # Get user role
        user_role = state.user_context.user_role.value

        return {
            "input_text": input_text,
            "perception_summary": perception_summary,
            "similar_cases": cases_text,
            "rag_analysis": rag_analysis,
            "user_role": user_role,
        }

    def _format_rag_analysis(self, assessment: Optional[RiskAssessment]) -> str:
        """
        格式化 RAG 分析结果

        Args:
            assessment: RAG 评估结果

        Returns:
            格式化文本
        """
        if not assessment:
            return "未启用 RAG 分析"

        return f"""
- RAG风险分数: {assessment.score}/100
- RAG风险等级: {assessment.level.value}
- 识别的子类型: {assessment.scam_type}
- 风险线索: {', '.join(assessment.clues) if assessment.clues else '无'}
- 评估依据: {assessment.reasoning}
"""

    def _format_similar_cases(self, cases: List[RetrievedCase]) -> str:
        """
        Format similar cases for prompt.

        Args:
            cases: List of retrieved cases

        Returns:
            Formatted text
        """
        if not cases:
            return "无相似案例"

        parts = []
        for i, case in enumerate(cases[:5], 1):
            parts.append(f"{i}. {case.title} (相似度: {case.similarity:.2f})\n   {case.content[:200]}...")

        return "\n\n".join(parts)

    def _parse_assessment(self, data: Dict[str, Any]) -> RiskAssessment:
        """
        Parse LLM response into RiskAssessment.

        Args:
            data: Parsed JSON data

        Returns:
            RiskAssessment object
        """
        score = int(data.get("risk_score", 0))

        # Determine level from score if not provided
        level_str = data.get("risk_level", "")
        if not level_str:
            if score < self.LOW_THRESHOLD:
                level = RiskLevel.LOW
            elif score <= self.HIGH_THRESHOLD:
                level = RiskLevel.MEDIUM
            else:
                level = RiskLevel.HIGH
        else:
            level = RiskLevel(level_str.lower())

        # Parse risk clues
        clues = data.get("risk_clues", [])
        if isinstance(clues, str):
            clues = [clues]

        return RiskAssessment(
            score=score,
            level=level,
            scam_type=data.get("scam_type", ""),
            clues=clues,
            reasoning=data.get("reasoning", ""),
        )

    def _merge_assessments(
        self,
        llm_assessment: RiskAssessment,
        rag_assessment: RiskAssessment,
    ) -> RiskAssessment:
        """
        融合 LLM 和 RAG 的评估结果

        策略：
        - 分数：取两者加权平均（RAG 40%，LLM 60%）
        - 等级：取两者较高者
        - 线索：合并去重
        - 理由：组合两者

        Args:
            llm_assessment: LLM 评估结果
            rag_assessment: RAG 评估结果

        Returns:
            融合后的 RiskAssessment
        """
        # 加权分数
        merged_score = int(rag_assessment.score * 0.4 + llm_assessment.score * 0.6)

        # 取较高风险等级
        level_priority = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}
        llm_priority = level_priority.get(llm_assessment.level, 1)
        rag_priority = level_priority.get(rag_assessment.level, 1)
        merged_level = llm_assessment.level if llm_priority >= rag_priority else rag_assessment.level

        # 合并线索
        merged_clues = list(dict.fromkeys(
            rag_assessment.clues + llm_assessment.clues
        ))

        # 合并理由
        merged_reasoning = f"[LLM分析] {llm_assessment.reasoning}\n[RAG分析] {rag_assessment.reasoning}"

        # 优先使用 RAG 识别的具体子类型
        scam_type = rag_assessment.scam_type or llm_assessment.scam_type

        return RiskAssessment(
            score=merged_score,
            level=merged_level,
            scam_type=scam_type,
            clues=merged_clues,
            reasoning=merged_reasoning,
        )

    def _fallback_assessment(self, state: GlobalState) -> RiskAssessment:
        """
        Generate fallback assessment when LLM fails.

        Uses heuristics based on perception results.

        Args:
            state: Global state

        Returns:
            Fallback RiskAssessment
        """
        score = 0
        clues = []

        # Check for fake content
        for result in state.perception_results:
            if result.fake_analysis and result.fake_analysis.is_fake:
                score += 30
                clues.append(f"检测到AI伪造内容 (置信度: {result.fake_analysis.fake_probability:.2f})")

        # Check for fraud keywords
        fraud_keywords = ["转账", "验证码", "安全账户", "公安局", "洗钱", "专案组"]
        text = state.get_combined_text().lower()
        for keyword in fraud_keywords:
            if keyword in text:
                score += 10
                clues.append(f"检测到可疑关键词: {keyword}")

        # Cap score
        score = min(score, 100)

        # Determine level
        if score < self.LOW_THRESHOLD:
            level = RiskLevel.LOW
        elif score <= self.HIGH_THRESHOLD:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.HIGH

        return RiskAssessment(
            score=score,
            level=level,
            scam_type="未知" if score == 0 else "潜在诈骗",
            clues=clues,
            reasoning="基于规则回退评估" if score > 0 else "未检测到明显风险",
        )

    def get_risk_level_from_score(self, score: int) -> RiskLevel:
        """
        Get risk level from score.

        Args:
            score: Risk score (0-100)

        Returns:
            RiskLevel
        """
        if score < self.LOW_THRESHOLD:
            return RiskLevel.LOW
        elif score <= self.HIGH_THRESHOLD:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.HIGH

    def get_stats(self) -> Dict[str, Any]:
        """
        获取引擎统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "use_rag_detector": self.use_rag_detector,
            "low_threshold": self.LOW_THRESHOLD,
            "high_threshold": self.HIGH_THRESHOLD,
        }

        if self._rag_detector:
            stats["rag_detector"] = self._rag_detector.get_stats()

        return stats
