"""
Global state models for LangGraph workflow.
Simplified and structured state management.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UserRole(str, Enum):
    """User persona types."""
    ELDERLY = "elderly"      # 老年人
    STUDENT = "student"      # 学生
    FINANCE = "finance"      # 金融从业者
    GENERAL = "general"      # 普通用户


class UserContext(BaseModel):
    """User context information passed through the pipeline."""
    user_role: UserRole = Field(UserRole.GENERAL, description="User persona type")
    guardian_name: Optional[str] = Field(None, description="Guardian name for alerts")
    user_id: Optional[str] = Field(None, description="User ID")


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
    # ============ Input Layer ============
    input_text: Optional[str] = Field(None, description="Direct text input")
    input_files: List["MediaFile"] = Field(default_factory=list, description="Media file inputs")
    user_context: UserContext = Field(default_factory=UserContext, description="User context")

    # ============ Perception Layer Output ============
    perception_results: List["PerceptionResult"] = Field(
        default_factory=list,
        description="Perception layer outputs"
    )

    # ============ Brain Layer Output ============
    intent: Optional[str] = Field(None, description="Detected user intent")
    similar_cases: List[RetrievedCase] = Field(
        default_factory=list,
        description="Retrieved similar cases"
    )
    legal_basis: List[str] = Field(default_factory=list, description="Relevant legal references")
    risk_assessment: Optional[RiskAssessment] = Field(None, description="Risk assessment")

    # ============ Action Layer Output ============
    intervention: Optional[Intervention] = Field(None, description="Intervention decision")

    # ============ Final Output ============
    final_report: Optional[str] = Field(None, description="Final report text")

    # ============ Metadata ============
    workflow_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow execution metadata"
    )

    class Config:
        # Forward reference resolution
        from src.core.models.media import MediaFile, PerceptionResult

    def get_combined_text(self) -> str:
        """
        Get combined text from all inputs and perception results.

        Returns:
            Concatenated text suitable for analysis
        """
        parts = []

        # Add direct text input
        if self.input_text:
            parts.append(self.input_text)

        # Add perception result texts
        for result in self.perception_results:
            if result.text_content:
                parts.append(result.text_content)

        return "\n\n".join(parts)

    def get_highest_risk_indicators(self) -> List[str]:
        """
        Collect all risk indicators from perception results.

        Returns:
            List of risk indicator strings
        """
        indicators = []
        for result in self.perception_results:
            indicators.extend(result.get_risk_indicators())
        return indicators


# Resolve forward references
from src.core.models.media import MediaFile, PerceptionResult
GlobalState.model_rebuild()
