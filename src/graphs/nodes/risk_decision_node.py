"""
Risk decision node.
Routes to different actions based on risk level.
"""
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from src.core.interfaces import BaseNode
from src.core.models import GlobalState, RiskLevel


class RiskDecisionNode(BaseNode):
    """
    Graph node for risk-based routing decision.

    Input: GlobalState with risk_assessment
    Output: Risk level string for conditional routing

    This replaces the 13-line risk_decision_node.py with a cleaner
    implementation using the new state model.
    """

    def __init__(self):
        super().__init__("risk_decision")

    async def process(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> str:
        """
        Determine risk level for routing.

        Args:
            state: Global state
            config: Runnable config

        Returns:
            Risk level string (low/medium/high)
        """
        if not state.risk_assessment:
            return "low"

        return state.risk_assessment.level.value

    def _extract_input(self, state: GlobalState) -> GlobalState:
        return state

    def _output_to_dict(self, output: str) -> Dict[str, Any]:
        """Return routing decision - not merged into state."""
        return {}

    def _get_fallback_output(self) -> Dict[str, Any]:
        return {}
