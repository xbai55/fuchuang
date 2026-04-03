"""
Guardian notifier for high-risk alerts.
"""
from datetime import datetime
from typing import List
from uuid import uuid4

from src.core.models import (
    EmergencyContact,
    GlobalState,
    GuardianNotification,
    Intervention,
    RiskLevel,
)
from src.action.sms_service import SmsNotificationService


class GuardianNotifier:
    """Builds structured guardian and emergency escalation records."""

    HOTLINE_NUMBERS = ["110", "96110"]

    def __init__(self):
        self._alert_history: List[dict] = []
        self.sms_service = SmsNotificationService()

    async def notify(
        self,
        state: GlobalState,
        intervention: Intervention,
    ) -> GuardianNotification:
        if not intervention.guardian_alert:
            return GuardianNotification(
                notified=False,
                status="not_triggered",
                hotline_numbers=self.HOTLINE_NUMBERS,
            )

        if not (state.user_context.notify_enabled and state.user_context.notify_guardian_alert):
            return GuardianNotification(
                notified=False,
                channel="sms",
                provider=self.sms_service.provider_name,
                status="disabled",
                failure_reason="Guardian SMS notifications are disabled in user settings.",
                hotline_numbers=self.HOTLINE_NUMBERS,
            )

        contacts = self._resolve_contacts(state)
        if not contacts:
            return GuardianNotification(
                notified=False,
                channel="sms",
                provider=self.sms_service.provider_name,
                status="no_contact",
                failure_reason="No guardian or emergency contact is configured.",
                message="No guardian or emergency contact is configured.",
                hotline_numbers=self.HOTLINE_NUMBERS,
            )

        primary = next((contact for contact in contacts if contact.phone), None)
        if primary is None:
            return GuardianNotification(
                notified=False,
                channel="sms",
                provider=self.sms_service.provider_name,
                status="missing_phone",
                failure_reason="Guardian or emergency contact exists but no phone number is available.",
                hotline_numbers=self.HOTLINE_NUMBERS,
                linked_contacts=contacts,
            )

        message = self._build_notification_message(state, intervention, primary)
        sms_result = await self.sms_service.send_guardian_alert(
            phone_number=primary.phone,
            message_payload=self._build_message_payload(state, intervention),
        )
        notification = GuardianNotification(
            notified=sms_result.success,
            dispatch_id=f"dispatch_{uuid4().hex[:12]}",
            guardian_name=primary.name,
            guardian_phone=primary.phone,
            channel="sms",
            provider=sms_result.provider,
            status=sms_result.status,
            provider_message_id=sms_result.provider_message_id or sms_result.request_id,
            failure_reason=sms_result.error,
            message=message,
            hotline_numbers=self.HOTLINE_NUMBERS,
            linked_contacts=contacts,
        )

        self._alert_history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "dispatch_id": notification.dispatch_id,
                "guardian_name": notification.guardian_name,
                "guardian_phone": notification.guardian_phone,
                "risk_level": state.risk_assessment.level.value if state.risk_assessment else "unknown",
                "risk_score": state.risk_assessment.score if state.risk_assessment else 0,
                "status": notification.status,
                "provider": notification.provider,
                "provider_message_id": notification.provider_message_id,
                "failure_reason": notification.failure_reason,
            }
        )
        print(
            f"[guardian_notifier] sms {notification.status} "
            f"{notification.dispatch_id} -> {notification.guardian_phone}"
        )
        return notification

    def _resolve_contacts(self, state: GlobalState) -> List[EmergencyContact]:
        contacts: List[EmergencyContact] = []
        if state.user_context.guardian_name or state.user_context.guardian_phone:
            contacts.append(
                EmergencyContact(
                    name=state.user_context.guardian_name or "Guardian",
                    phone=state.user_context.guardian_phone or "",
                    relationship="guardian",
                    is_guardian=True,
                )
            )

        for contact in state.user_context.emergency_contacts:
            if not any(existing.phone == contact.phone for existing in contacts if existing.phone):
                contacts.append(contact)

        contacts.sort(key=lambda item: (not item.is_guardian, item.name))
        return contacts

    def _build_notification_message(
        self,
        state: GlobalState,
        intervention: Intervention,
        contact: EmergencyContact,
    ) -> str:
        risk = state.risk_assessment
        return (
            f"User role: {state.user_context.user_role.value}\n"
            f"Guardian/contact: {contact.name} ({contact.phone or 'no-phone'})\n"
            f"Risk level: {risk.level.value if risk else 'unknown'}\n"
            f"Risk score: {risk.score if risk else 0}/100\n"
            f"Scam type: {risk.scam_type if risk and risk.scam_type else 'unknown'}\n"
            f"Reason: {intervention.alert_reason or 'High-risk anti-fraud escalation triggered.'}\n"
            f"Recommended hotlines: {', '.join(self.HOTLINE_NUMBERS)}"
        )

    def _build_message_payload(
        self,
        state: GlobalState,
        intervention: Intervention,
    ) -> dict:
        risk = state.risk_assessment
        return {
            "userRole": state.user_context.user_role.value,
            "riskLevel": risk.level.value if risk else "unknown",
            "riskScore": str(risk.score if risk else 0),
            "scamType": risk.scam_type if risk and risk.scam_type else "unknown",
            "alertReason": intervention.alert_reason or "High-risk anti-fraud escalation triggered.",
            "hotline": "/".join(self.HOTLINE_NUMBERS),
        }

    def get_alert_history(self) -> list:
        return self._alert_history.copy()

    async def should_notify(self, state: GlobalState) -> bool:
        if not state.user_context.notify_enabled or not state.user_context.notify_guardian_alert:
            return False
        if not self._resolve_contacts(state):
            return False
        if not state.risk_assessment:
            return False
        if state.risk_assessment.level == RiskLevel.HIGH:
            return True
        return state.risk_assessment.level == RiskLevel.MEDIUM and state.risk_assessment.score >= 60
