"""
Intervention service - unified interface for action layer.
Combines alert generation, guardian notification, and report generation.
"""
from typing import Dict, Any

from src.core.models import GlobalState, Intervention
from src.action.alert_generator import AlertGenerator
from src.action.guardian_notifier import GuardianNotifier
from src.action.report_generator import ReportGenerator


class InterventionService:
    """
    Unified service for intervention actions.

    Coordinates:
    - Alert generation
    - Guardian notification
    - Report generation
    """

    def __init__(
        self,
        alert_generator: AlertGenerator = None,
        guardian_notifier: GuardianNotifier = None,
        report_generator: ReportGenerator = None,
    ):
        """
        Initialize intervention service.

        Args:
            alert_generator: Optional AlertGenerator instance
            guardian_notifier: Optional GuardianNotifier instance
            report_generator: Optional ReportGenerator instance
        """
        self.alert_generator = alert_generator or AlertGenerator()
        self.guardian_notifier = guardian_notifier or GuardianNotifier()
        self.report_generator = report_generator or ReportGenerator()

    async def execute(self, state: GlobalState) -> Dict[str, Any]:
        """
        Execute complete intervention workflow.

        Args:
            state: Current workflow state

        Returns:
            Complete intervention results
        """
        # Generate alert
        intervention = await self.alert_generator.generate(state)
        state.intervention = intervention

        # Send guardian notification if needed
        notification_result = await self.guardian_notifier.notify(state, intervention)
        state.guardian_notification = notification_result

        # Generate report
        report = await self.report_generator.generate(state)
        state.final_report = report

        return {
            "intervention": intervention,
            "guardian_notification": notification_result,
            "report": report,
        }

    async def generate_alert_only(self, state: GlobalState) -> Intervention:
        """
        Generate only the alert (faster, for real-time responses).

        Args:
            state: Current workflow state

        Returns:
            Intervention object
        """
        intervention = await self.alert_generator.generate(state)
        state.intervention = intervention
        return intervention

    async def should_alert_guardian(self, state: GlobalState) -> bool:
        """
        Check if guardian should be notified.

        Args:
            state: Current workflow state

        Returns:
            True if guardian should be notified
        """
        return await self.guardian_notifier.should_notify(state)
