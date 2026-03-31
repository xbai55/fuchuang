"""
Guardian notifier for high-risk alerts.
Handles notification to guardians when high fraud risk is detected.
"""
from typing import Dict, Any, Optional

from src.core.models import GlobalState, Intervention, RiskLevel


class GuardianNotifier:
    """
    Notifies guardians when high-risk fraud is detected.

    Currently logs alerts; can be extended to send SMS, email, etc.
    """

    def __init__(self):
        """Initialize guardian notifier."""
        self._alert_history: list = []

    async def notify(
        self,
        state: GlobalState,
        intervention: Intervention,
    ) -> Dict[str, Any]:
        """
        Send notification to guardian if alert is triggered.

        Args:
            state: Current workflow state
            intervention: Intervention result with alert flag

        Returns:
            Notification result
        """
        if not intervention.guardian_alert:
            return {"notified": False, "reason": "Alert not triggered"}

        guardian_name = state.user_context.guardian_name
        if not guardian_name:
            return {"notified": False, "reason": "No guardian configured"}

        # Build notification message
        message = self._build_notification_message(state, intervention)

        # Log the alert (in production, send SMS/email)
        alert_record = {
            "guardian": guardian_name,
            "user_role": state.user_context.user_role.value,
            "risk_score": state.risk_assessment.score if state.risk_assessment else 0,
            "message": message,
            "alert_reason": intervention.alert_reason,
        }
        self._alert_history.append(alert_record)

        # TODO: Implement actual notification (SMS, email, push)
        print(f"[监护人通知] 发送给 {guardian_name}: {message[:100]}...")

        return {
            "notified": True,
            "guardian": guardian_name,
            "message": message,
        }

    def _build_notification_message(
        self,
        state: GlobalState,
        intervention: Intervention,
    ) -> str:
        """
        Build notification message for guardian.

        Args:
            state: Global state
            intervention: Intervention result

        Returns:
            Notification message
        """
        risk = state.risk_assessment
        user_role = state.user_context.user_role.value

        parts = [
            f"【反诈预警】您的{user_role}家属可能遭遇诈骗！",
            f"",
            f"风险等级: {risk.level.value if risk else 'unknown'}",
            f"风险分数: {risk.score if risk else 0}/100",
            f"诈骗类型: {risk.scam_type if risk else 'unknown'}",
            f"",
            f"预警原因: {intervention.alert_reason}",
            f"",
            f"建议立即联系家属确认情况。",
        ]

        return "\n".join(parts)

    def get_alert_history(self) -> list:
        """
        Get alert history.

        Returns:
            List of alert records
        """
        return self._alert_history.copy()

    async def should_notify(
        self,
        state: GlobalState,
    ) -> bool:
        """
        Determine if notification should be sent.

        Args:
            state: Current workflow state

        Returns:
            True if should notify
        """
        # Must have guardian configured
        if not state.user_context.guardian_name:
            return False

        # Must have risk assessment
        if not state.risk_assessment:
            return False

        # High risk always notifies
        if state.risk_assessment.level == RiskLevel.HIGH:
            return True

        # Medium risk may notify depending on context
        if state.risk_assessment.level == RiskLevel.MEDIUM:
            # Check for specific high-risk indicators
            for result in state.perception_results:
                if result.fake_analysis and result.fake_analysis.is_fake:
                    return True

        return False