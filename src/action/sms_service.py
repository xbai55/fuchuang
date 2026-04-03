"""
Provider-agnostic SMS notification interface.
Aliyun SMS API integration scripts are removed temporarily.
Only one unified interface is reserved for future provider binding.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class SmsSendResult:
    success: bool
    provider: str
    status: str
    provider_message_id: str = ""
    request_id: str = ""
    error: str = ""


class SmsNotificationService:
    """
    Unified SMS notification interface placeholder.

    The workflow keeps calling `send_guardian_alert`, while concrete provider
    adapters are intentionally not included for now.
    """

    def __init__(self, provider_name: str = "reserved_interface"):
        self.provider_name = provider_name

    def is_configured(self) -> bool:
        return False

    async def send_guardian_alert(
        self,
        phone_number: str,
        message_payload: Dict[str, str],
    ) -> SmsSendResult:
        _ = (phone_number, message_payload)
        return SmsSendResult(
            success=False,
            provider=self.provider_name,
            status="provider_not_bound",
            error="No SMS provider is currently bound. Only the unified interface is reserved.",
        )
