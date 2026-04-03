"""
Intervention node.
Uses the InterventionService from the action layer.
"""
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from src.core.interfaces import BaseNode
from src.core.models import GlobalState, Intervention
from action import InterventionService


class InterventionNode(BaseNode):
    """
    Graph node for intervention generation.

    Input: GlobalState with risk_assessment
    Output: Updated GlobalState with intervention

    This replaces the 104-line intervention_node.py with a cleaner
    implementation using the InterventionService.
    """

    def __init__(self, intervention_service: InterventionService = None):
        super().__init__("intervention")
        self.service = intervention_service or InterventionService()

    async def process(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> Dict[str, Any]:
        """
        Generate intervention.

        Args:
            state: Global state
            config: Runnable config

        Returns:
            Dict with intervention
        """
        # Generate alert
        intervention = await self.service.generate_alert_only(state)

        # Send guardian notification if needed
        guardian_notification = await self.service.guardian_notifier.notify(state, intervention)

        return {
            "intervention": intervention,
            "guardian_notification": guardian_notification,
        }

    def _extract_input(self, state: GlobalState) -> GlobalState:
        return state

    def _output_to_dict(self, output: Dict[str, Any]) -> Dict[str, Any]:
        return output

    def _get_fallback_output(self) -> Dict[str, Any]:
        """Return fallback intervention on failure."""
        return {
            "intervention": Intervention(
                warning_message="系统已分析完成，请查看详细报告。",
                guardian_alert=False,
                action_items=["如有疑问请咨询专业人士"],
            )
        }
