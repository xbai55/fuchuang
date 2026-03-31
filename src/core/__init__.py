"""
Core layer for the anti-fraud system.
Provides shared utilities, models, and interfaces.
"""
from src.core.utils import (
    extract_json_from_text,
    safe_json_loads,
    get_text_content,
    load_node_config,
    get_prompt_template,
    create_temp_file,
    cleanup_temp_files,
    is_url,
    run_in_threadpool,
    asyncio_timeout,
)
from src.core.models import (
    MediaFile,
    MediaType,
    PerceptionResult,
    FakeAnalysis,
    OCRResult,
    GlobalState,
    UserContext,
    RiskAssessment,
    Intervention,
    RiskLevel,
)
from src.core.interfaces import LLMClient, LLMResponse, BaseNode

__all__ = [
    # Utils
    "extract_json_from_text",
    "safe_json_loads",
    "get_text_content",
    "load_node_config",
    "get_prompt_template",
    "create_temp_file",
    "cleanup_temp_files",
    "is_url",
    "run_in_threadpool",
    "asyncio_timeout",
    # Models
    "MediaFile",
    "MediaType",
    "PerceptionResult",
    "FakeAnalysis",
    "OCRResult",
    "GlobalState",
    "UserContext",
    "RiskAssessment",
    "Intervention",
    "RiskLevel",
    # Interfaces
    "LLMClient",
    "LLMResponse",
    "BaseNode",
]
