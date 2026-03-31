"""
Risk assessment node.
Uses the RiskEngine from the brain layer.
"""
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from src.core.interfaces import BaseNode
from src.core.models import GlobalState, RiskAssessment
from brain import RiskEngine


class RiskAssessmentNode(BaseNode):
    """
    Graph node for risk assessment.

    Input: GlobalState with perception_results and similar_cases
    Output: Updated GlobalState with risk_assessment

    This replaces the 107-line risk_assessment_node.py with a cleaner
    implementation using the RiskEngine.
    """

    def __init__(self, risk_engine: RiskEngine = None):
        super().__init__("risk_assessment")
        self.engine = risk_engine or RiskEngine()

    async def process(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> Dict[str, Any]:
        """
        Assess fraud risk.

        Args:
            state: Global state
            config: Runnable config

        Returns:
            Dict with risk_assessment
        """
        # Perform assessment
        assessment = await self.engine.assess(state)

        return {"risk_assessment": assessment}

    def _extract_input(self, state: GlobalState) -> GlobalState:
        return state

    def _output_to_dict(self, output: Dict[str, Any]) -> Dict[str, Any]:
        return output

    def _get_fallback_output(self) -> Dict[str, Any]:
        """Return fallback assessment on failure."""
        return {
            "risk_assessment": RiskAssessment(
                score=0,
                level="low",
                scam_type="未知",
                clues=["评估失败，使用默认安全等级"],
            )
        }
