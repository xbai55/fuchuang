"""
Report generation node.
Uses the ReportGenerator from the action layer.
"""
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from src.core.interfaces import BaseNode
from src.core.models import GlobalState
from action import ReportGenerator


class ReportNode(BaseNode):
    """
    Graph node for report generation.

    Input: GlobalState with all previous results
    Output: Updated GlobalState with final_report

    This replaces the 91-line report_generation_node.py with a cleaner
    implementation using the ReportGenerator.
    """

    def __init__(self, report_generator: ReportGenerator = None):
        super().__init__("report_generation")
        self.generator = report_generator or ReportGenerator()

    async def process(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> Dict[str, Any]:
        """
        Generate final report.

        Args:
            state: Global state
            config: Runnable config

        Returns:
            Dict with final_report
        """
        # Generate report
        report = await self.generator.generate(state)

        return {"final_report": report}

    def _extract_input(self, state: GlobalState) -> GlobalState:
        return state

    def _output_to_dict(self, output: Dict[str, Any]) -> Dict[str, Any]:
        return output

    def _get_fallback_output(self) -> Dict[str, Any]:
        """Return fallback report on failure."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "final_report": f"""# 反诈安全分析报告

**生成时间**: {timestamp}

报告生成遇到问题，请稍后重试或联系技术支持。

**基本建议**:
- 保持警惕，不要轻信陌生来电
- 不要透露验证码、密码等敏感信息
- 如有疑问请拨打110或反诈专线96110
"""
        }
