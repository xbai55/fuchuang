"""
Core data models for the anti-fraud system.
"""
from src.core.models.media import MediaFile, MediaType, PerceptionResult, FakeAnalysis, OCRResult
from src.core.models.state import (
    GlobalState,
    UserContext,
    RiskAssessment,
    Intervention,
    RiskLevel,
    UserRole,
    RetrievedCase,
)

__all__ = [
    # Media models
    "MediaFile",
    "MediaType",
    "PerceptionResult",
    "FakeAnalysis",
    "OCRResult",
    # State models
    "GlobalState",
    "UserContext",
    "RiskAssessment",
    "Intervention",
    "RiskLevel",
    "UserRole",
]
