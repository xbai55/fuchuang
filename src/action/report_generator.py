"""
Report generator for final anti-fraud reports.
Compiles all analysis results into a comprehensive report.
"""
from datetime import datetime
from typing import Dict, Any, List

from src.core.models import GlobalState, RiskLevel
from src.core.interfaces import LLMClient
from src.core.utils import load_node_config


class ReportGenerator:
    """
    Generates comprehensive anti-fraud reports.

    Compiles information from:
    - Perception results
    - Risk assessment
    - Intervention actions
    """

    # Default system prompt
    DEFAULT_SYSTEM_PROMPT = """你是一位专业的反诈报告撰写专家。

请根据提供的分析结果，生成一份完整的反诈安全报告。

报告应包含：
1. 执行摘要
2. 风险评估详情
3. 检测到的异常
4. 建议和防范措施
5. 参考案例和法律依据

报告格式应使用Markdown，结构清晰，便于阅读。"""

    # Default user prompt template
    DEFAULT_USER_TEMPLATE = """请生成反诈安全报告：

## 输入内容
{input_text}

## 多模态分析
{perception_summary}

## 风险评估
- 风险分数: {risk_score}/100
- 风险等级: {risk_level}
- 诈骗类型: {scam_type}
- 风险线索: {risk_clues}

## 干预措施
- 警告信息: {warning_message}
- 建议操作: {action_items}

## 相似案例
{similar_cases}

## 法律依据
{legal_basis}

请生成完整的Markdown格式报告。"""

    def __init__(self, llm_client: 'LLMClient' = None):
        """
        Initialize report generator.

        Args:
            llm_client: Optional LLM client
        """
        config = load_node_config("report_generation")

        if llm_client:
            self.llm = llm_client
        else:
            self.llm = LLMClient.from_config(config)

        self.system_prompt = config.get("system_prompt", self.DEFAULT_SYSTEM_PROMPT)
        self.user_template = config.get("user_prompt", self.DEFAULT_USER_TEMPLATE)

    async def generate(self, state: GlobalState) -> str:
        """
        Generate comprehensive report.

        Args:
            state: Current workflow state

        Returns:
            Markdown formatted report
        """
        # Build context
        context = self._build_context(state)

        # Build user prompt
        user_prompt = self.user_template.format(**context)

        try:
            # Call LLM
            response = await self.llm.achat(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                parse_json=False,  # Report is free text
            )

            # Add timestamp and header
            report = self._format_report(response.content, state)
            return report

        except Exception as e:
            print(f"[错误] 生成报告失败: {e}")
            return self._fallback_report(state)

    def _build_context(self, state: GlobalState) -> Dict[str, Any]:
        """
        Build context for prompt formatting.

        Args:
            state: Global state

        Returns:
            Context dictionary
        """
        # Input text
        input_text = state.get_combined_text()[:500]  # Limit length

        # Perception summary
        perception_parts = []
        for result in state.perception_results:
            summary = result.to_prompt_text()
            if summary:
                perception_parts.append(summary)
        perception_summary = "\n\n".join(perception_parts) if perception_parts else "无"

        # Risk assessment
        risk = state.risk_assessment
        risk_score = risk.score if risk else 0
        risk_level = risk.level.value if risk else "unknown"
        scam_type = risk.scam_type if risk else "未知"
        risk_clues = "\n".join([f"- {c}" for c in risk.clues]) if risk and risk.clues else "无"

        # Intervention
        intervention = state.intervention
        warning_message = intervention.warning_message if intervention else ""
        action_items = "\n".join([f"- {a}" for a in intervention.action_items]) if intervention else "无"

        # Similar cases
        cases_text = "\n\n".join([
            f"### {c.title}\n{c.content[:200]}..."
            for c in state.similar_cases[:3]
        ]) if state.similar_cases else "无相似案例"

        # Legal basis
        legal_basis = "\n".join([f"- {l}" for l in state.legal_basis]) if state.legal_basis else "无"

        return {
            "input_text": input_text,
            "perception_summary": perception_summary,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "scam_type": scam_type,
            "risk_clues": risk_clues,
            "warning_message": warning_message,
            "action_items": action_items,
            "similar_cases": cases_text,
            "legal_basis": legal_basis,
        }

    def _format_report(self, content: str, state: GlobalState) -> str:
        """
        Format report with header and timestamp.

        Args:
            content: Report content
            state: Global state

        Returns:
            Formatted report
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        risk = state.risk_assessment

        header = f"""# 反诈安全分析报告

**生成时间**: {timestamp}
**风险等级**: {risk.level.value if risk else 'unknown'}
**风险分数**: {risk.score if risk else 0}/100
**诈骗类型**: {risk.scam_type if risk else 'unknown'}

---

"""

        return header + content

    def _fallback_report(self, state: GlobalState) -> str:
        """
        Generate fallback report when LLM fails.

        Args:
            state: Global state

        Returns:
            Fallback report
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        risk = state.risk_assessment
        intervention = state.intervention

        parts = [
            "# 反诈安全分析报告",
            "",
            f"**生成时间**: {timestamp}",
            f"**风险等级**: {risk.level.value if risk else 'unknown'}",
            f"**风险分数**: {risk.score if risk else 0}/100",
            "",
            "## 执行摘要",
            "",
            intervention.warning_message if intervention else "系统已完成风险分析。",
            "",
            "## 建议措施",
            "",
        ]

        if intervention and intervention.action_items:
            for item in intervention.action_items:
                parts.append(f"- {item}")
        else:
            parts.append("- 保持警惕，谨慎对待可疑信息")

        parts.extend([
            "",
            "## 风险提示",
            "",
        ])

        if risk and risk.clues:
            for clue in risk.clues:
                parts.append(f"- {clue}")
        else:
            parts.append("- 未检测到明显风险特征")

        return "\n".join(parts)