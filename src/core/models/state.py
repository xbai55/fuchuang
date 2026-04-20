"""
Global state models for LangGraph workflow.
Simplified and structured state management.
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UserRole(str, Enum):
    """User persona types."""

    ELDERLY = "elderly"
    CHILD = "child"
    YOUNG_ADULT = "young_adult"
    STUDENT = "student"
    MALE = "male"
    FEMALE = "female"
    ENTERPRISE_STAFF = "enterprise_staff"
    SELF_EMPLOYED = "self_employed"
    RETIRED_GROUP = "retired_group"
    PUBLIC_OFFICER = "public_officer"
    FINANCE_PRACTITIONER = "finance_practitioner"
    OTHER = "other"
    GENERAL = "general"


class EmergencyContact(BaseModel):
    """Emergency or guardian contact that can be linked during escalation."""

    name: str = Field("", description="Contact name")
    phone: str = Field("", description="Contact phone number")
    email: str = Field("", description="Contact email address")
    relationship: str = Field("", description="Relationship to the user")
    is_guardian: bool = Field(False, description="Whether this contact is the primary guardian")


class UserContext(BaseModel):
    """User context information passed through the pipeline."""

    user_role: UserRole = Field(UserRole.GENERAL, description="User persona type")
    guardian_name: Optional[str] = Field(None, description="Guardian name for alerts")
    guardian_phone: Optional[str] = Field(None, description="Guardian phone number for alerts")
    user_id: Optional[str] = Field(None, description="User ID")
    notify_enabled: bool = Field(True, description="Whether notifications are enabled")
    notify_guardian_alert: bool = Field(True, description="Whether guardian alert notifications are enabled")
    emergency_contacts: List[EmergencyContact] = Field(
        default_factory=list,
        description="Emergency contacts available for escalation",
    )


class RiskAssessment(BaseModel):
    """Risk assessment output from brain layer."""

    score: int = Field(0, ge=0, le=100, description="Risk score 0-100")
    level: RiskLevel = Field(RiskLevel.LOW, description="Risk level")
    scam_type: str = Field("", description="Identified scam type")
    clues: List[str] = Field(default_factory=list, description="Risk clues identified")
    reasoning: str = Field("", description="Assessment reasoning")


class Intervention(BaseModel):
    """Intervention action output."""

    warning_message: str = Field("", description="Warning message to user")
    guardian_alert: bool = Field(False, description="Whether to alert guardian")
    alert_reason: str = Field("", description="Reason for guardian alert")
    action_items: List[str] = Field(default_factory=list, description="Recommended actions")
    escalation_actions: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Structured escalation actions such as hotlines and guardian contact",
    )


class GuardianNotification(BaseModel):
    """Result of notifying a guardian or emergency contact."""

    notified: bool = Field(False, description="Whether any guardian notification was dispatched")
    dispatch_id: str = Field("", description="Notification dispatch identifier")
    guardian_name: str = Field("", description="Guardian name")
    guardian_phone: str = Field("", description="Guardian phone number")
    channel: str = Field("", description="Notification channel")
    provider: str = Field("", description="Notification provider name")
    status: str = Field("", description="Notification delivery status")
    provider_message_id: str = Field("", description="Provider message identifier")
    failure_reason: str = Field("", description="Failure reason when dispatch fails")
    message: str = Field("", description="Notification content")
    hotline_numbers: List[str] = Field(default_factory=list, description="Suggested anti-fraud hotline numbers")
    linked_contacts: List[EmergencyContact] = Field(
        default_factory=list,
        description="Contacts linked to the escalation",
    )


class RetrievedCase(BaseModel):
    """Retrieved similar fraud case from RAG."""

    case_id: str = Field("", description="Case identifier")
    title: str = Field("", description="Case title")
    content: str = Field("", description="Case content")
    similarity: float = Field(0.0, description="Similarity score")
    source: str = Field("", description="Case source")


class GlobalState(BaseModel):
    """
    Simplified global state for the anti-fraud workflow.

    Replaces the original 20-field state with a cleaner structure
    organized by layer (perception, brain, action).
    """

    input_text: Optional[str] = Field(None, description="Direct text input")
    input_files: List["MediaFile"] = Field(default_factory=list, description="Media file inputs")
    user_context: UserContext = Field(default_factory=UserContext, description="User context")

    perception_results: List["PerceptionResult"] = Field(
        default_factory=list,
        description="Perception layer outputs",
    )

    intent: Optional[str] = Field(None, description="Detected user intent")
    similar_cases: List[RetrievedCase] = Field(default_factory=list, description="Retrieved similar cases")
    legal_basis: List[str] = Field(default_factory=list, description="Relevant legal references")
    risk_assessment: Optional[RiskAssessment] = Field(None, description="Risk assessment")
    short_term_memory_summary: str = Field("", description="Summary of recent user risk context")

    intervention: Optional[Intervention] = Field(None, description="Intervention decision")
    guardian_notification: Optional[GuardianNotification] = Field(None, description="Guardian notification result")

    final_report: Optional[str] = Field(None, description="Final report text")

    workflow_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow execution metadata",
    )

    class Config:
        from src.core.models.media import MediaFile, PerceptionResult

    def get_combined_text(self) -> str:
        """Get combined text from all inputs and perception results."""

        parts = []

        if self.input_text:
            parts.append(self.input_text)

        for result in self.perception_results:
            if result.text_content:
                parts.append(result.text_content)

        return "\n\n".join(parts)

    def get_highest_risk_indicators(self) -> List[str]:
        """Collect all risk indicators from perception results."""

        indicators = []
        for result in self.perception_results:
            indicators.extend(result.get_risk_indicators())
        return indicators


from src.core.models.media import MediaFile, PerceptionResult

GlobalState.model_rebuild()
