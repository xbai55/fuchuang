"""
Core utilities for the anti-fraud system.
"""
from src.core.utils.json_utils import extract_json_from_text, safe_json_loads, get_text_content
from src.core.utils.config_loader import load_node_config, get_prompt_template
from src.core.utils.file_utils import create_temp_file, cleanup_temp_files, is_url
from src.core.utils.async_utils import run_in_threadpool, asyncio_timeout
from src.core.utils.risk_personalization import (
    build_role_prompt_guidance,
    build_personalized_thresholds,
    format_combined_profile_text,
    format_role_profile_text,
    get_role_profile,
    get_combined_profile,
    normalize_age_group,
    normalize_gender,
    normalize_occupation,
    normalize_user_role,
    occupation_to_user_role,
    risk_level_from_score,
)

__all__ = [
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
    "build_role_prompt_guidance",
    "build_personalized_thresholds",
    "format_combined_profile_text",
    "format_role_profile_text",
    "get_combined_profile",
    "get_role_profile",
    "normalize_age_group",
    "normalize_gender",
    "normalize_occupation",
    "normalize_user_role",
    "occupation_to_user_role",
    "risk_level_from_score",
]
