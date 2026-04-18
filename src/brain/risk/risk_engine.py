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
from src.core.utils import format_role_profile_text, load_node_config, normalize_user_role
from src.core.utils.risk_personalization import build_personalized_thresholds, risk_level_from_score


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
- 组合画像:
{combined_profile}

## 短期记忆
{short_term_memory_summary}

## 长期行为画像
{long_term_memory_summary}

## 个性化阈值
- low_threshold: {dynamic_low_threshold}
- high_threshold: {dynamic_high_threshold}
- 调整依据: {threshold_adjustment_reasons}

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
        metadata = dict(state.workflow_metadata or {})
        dynamic_thresholds = build_personalized_thresholds(
            user_role=state.user_context.user_role.value,
            short_term_events=list(metadata.get("recent_detections") or []),
            history_profile=dict(metadata.get("history_profile") or {}),
            age_group=str(metadata.get("age_group") or "unknown"),
            gender=str(metadata.get("gender") or "unknown"),
            occupation=str(metadata.get("occupation") or "other"),
        )
        low_threshold = int(dynamic_thresholds.get("low_threshold", self.LOW_THRESHOLD))
        high_threshold = int(dynamic_thresholds.get("high_threshold", self.HIGH_THRESHOLD))

        # 步骤 1: RAG 基于知识库的评估
        rag_assessment = None
        if self.use_rag_detector and self._rag_detector:
            rag_assessment = await self._assess_with_rag(
                state,
                low_threshold=low_threshold,
                high_threshold=high_threshold,
            )

        # 步骤 2: LLM 综合评估
        llm_assessment = await self._assess_with_llm(
            state,
            rag_assessment,
            low_threshold=low_threshold,
            high_threshold=high_threshold,
            dynamic_thresholds=dynamic_thresholds,
        )

        # 步骤 3: 融合评估结果
        if rag_assessment:
            final_assessment = self._merge_assessments(
                llm_assessment,
                rag_assessment,
                low_threshold=low_threshold,
                high_threshold=high_threshold,
            )
        else:
            final_assessment = llm_assessment

        self._append_threshold_note(final_assessment, dynamic_thresholds)
        return final_assessment

    async def _assess_with_rag(
        self,
        state: GlobalState,
        low_threshold: int,
        high_threshold: int,
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

        # 映射风险等级：融合 detector 等级与个性化分段
        level_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
        }
        detector_level = level_map.get(result.risk_level, RiskLevel.LOW)
        dynamic_level = RiskLevel(risk_level_from_score(score, low_threshold, high_threshold))
        level = self._max_risk_level(detector_level, dynamic_level)

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
        low_threshold: int = LOW_THRESHOLD,
        high_threshold: int = HIGH_THRESHOLD,
        dynamic_thresholds: Optional[Dict[str, Any]] = None,
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
        context = self._build_assessment_context(
            state,
            rag_assessment,
            dynamic_thresholds=dynamic_thresholds,
        )

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
                return self._parse_assessment(
                    response.parsed_json,
                    low_threshold=low_threshold,
                    high_threshold=high_threshold,
                )
            else:
                # Fallback if JSON parsing failed
                return self._fallback_assessment(
                    state,
                    low_threshold=low_threshold,
                    high_threshold=high_threshold,
                )

        except Exception as e:
            print(f"[错误] 风险评估失败: {e}")
            return self._fallback_assessment(
                state,
                low_threshold=low_threshold,
                high_threshold=high_threshold,
            )

    def _build_assessment_context(
        self,
        state: GlobalState,
        rag_assessment: Optional[RiskAssessment] = None,
        dynamic_thresholds: Optional[Dict[str, Any]] = None,
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
        user_role = normalize_user_role(state.user_context.user_role.value)

        threshold_meta = dynamic_thresholds or {}
        short_term_summary = state.short_term_memory_summary or "暂无短期交互记忆"
        history_profile = dict((state.workflow_metadata or {}).get("history_profile") or {})
        combined_profile = str((state.workflow_metadata or {}).get("combined_profile_text") or "none")
        long_term_summary = self._format_history_profile(history_profile)
        threshold_reasons = threshold_meta.get("adjustment_reasons") or []
        threshold_reason_text = "；".join(str(item) for item in threshold_reasons) if threshold_reasons else "无"

        return {
            "input_text": input_text,
            "perception_summary": perception_summary,
            "similar_cases": cases_text,
            "rag_analysis": rag_analysis,
            "user_role": user_role,
            "role_profile": format_role_profile_text(user_role),
            "combined_profile": combined_profile,
            "short_term_memory_summary": short_term_summary,
            "long_term_memory_summary": long_term_summary,
            "dynamic_low_threshold": int(threshold_meta.get("low_threshold", self.LOW_THRESHOLD)),
            "dynamic_high_threshold": int(threshold_meta.get("high_threshold", self.HIGH_THRESHOLD)),
            "threshold_adjustment_reasons": threshold_reason_text,
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

    def _format_history_profile(self, history_profile: Dict[str, Any]) -> str:
        """Format long-term user behavior profile for prompts."""
        if not history_profile:
            return "暂无长期历史行为记录"

        total_count = int(history_profile.get("total_count", 0) or 0)
        if total_count <= 0:
            return "暂无长期历史行为记录"

        avg_score = float(history_profile.get("avg_score", 0.0) or 0.0)
        high_ratio = float(history_profile.get("high_ratio", 0.0) or 0.0)
        medium_ratio = float(history_profile.get("medium_ratio", 0.0) or 0.0)
        trend = "上升" if history_profile.get("rising_risk") else "平稳"

        return (
            f"历史检测 {total_count} 次，平均风险分 {avg_score:.1f}/100，"
            f"高风险占比 {high_ratio:.0%}，中风险占比 {medium_ratio:.0%}，最近趋势 {trend}"
        )

    def _parse_assessment(
        self,
        data: Dict[str, Any],
        low_threshold: int,
        high_threshold: int,
    ) -> RiskAssessment:
        """
        Parse LLM response into RiskAssessment.

        Args:
            data: Parsed JSON data

        Returns:
            RiskAssessment object
        """
        score = int(data.get("risk_score", 0))
        score_level = RiskLevel(risk_level_from_score(score, low_threshold, high_threshold))

        # Determine level from score if not provided
        level_str = data.get("risk_level", "")
        if not level_str:
            level = score_level
        else:
            try:
                llm_level = RiskLevel(level_str.lower())
            except ValueError:
                llm_level = score_level
            level = self._max_risk_level(llm_level, score_level)

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
        low_threshold: int,
        high_threshold: int,
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

        # 取较高风险等级，并确保符合个性化阈值分段
        score_level = RiskLevel(risk_level_from_score(merged_score, low_threshold, high_threshold))
        merged_level = self._max_risk_level(llm_assessment.level, rag_assessment.level, score_level)

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

    def _fallback_assessment(
        self,
        state: GlobalState,
        low_threshold: int,
        high_threshold: int,
    ) -> RiskAssessment:
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
        level = RiskLevel(risk_level_from_score(score, low_threshold, high_threshold))

        return RiskAssessment(
            score=score,
            level=level,
            scam_type="未知" if score == 0 else "潜在诈骗",
            clues=clues,
            reasoning="基于规则回退评估" if score > 0 else "未检测到明显风险",
        )

    def get_risk_level_from_score(
        self,
        score: int,
        low_threshold: Optional[int] = None,
        high_threshold: Optional[int] = None,
    ) -> RiskLevel:
        """
        Get risk level from score.

        Args:
            score: Risk score (0-100)

        Returns:
            RiskLevel
        """
        return RiskLevel(
            risk_level_from_score(
                score,
                low_threshold=self.LOW_THRESHOLD if low_threshold is None else int(low_threshold),
                high_threshold=self.HIGH_THRESHOLD if high_threshold is None else int(high_threshold),
            )
        )

    @staticmethod
    def _max_risk_level(*levels: RiskLevel) -> RiskLevel:
        level_priority = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}
        best = RiskLevel.LOW
        best_priority = 0
        for level in levels:
            priority = level_priority.get(level, 0)
            if priority > best_priority:
                best = level
                best_priority = priority
        return best

    def _append_threshold_note(self, assessment: RiskAssessment, threshold_meta: Dict[str, Any]) -> None:
        """Append personalized threshold details to assessment reasoning."""
        low_threshold = int(threshold_meta.get("low_threshold", self.LOW_THRESHOLD))
        high_threshold = int(threshold_meta.get("high_threshold", self.HIGH_THRESHOLD))
        reasons = threshold_meta.get("adjustment_reasons") or []
        reason_text = "；".join(str(item) for item in reasons) if reasons else "无"
        suffix = f"[个性化阈值] low<{low_threshold}, high>{high_threshold}；依据: {reason_text}"

        base_reasoning = (assessment.reasoning or "").strip()
        assessment.reasoning = f"{base_reasoning}\n{suffix}" if base_reasoning else suffix

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
