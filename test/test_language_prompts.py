import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.language_prompts import (
    build_single_pass_system_prompt,
    localize_early_warning,
    normalize_output_language,
)
from src.core.utils.risk_personalization import build_role_prompt_guidance


def test_normalize_output_language_accepts_english_aliases():
    assert normalize_output_language("en-US") == "en-US"
    assert normalize_output_language("EN") == "en-US"
    assert normalize_output_language("zh-CN") == "zh-CN"
    assert normalize_output_language(None) == "zh-CN"


def test_single_pass_system_prompt_enforces_english_output():
    prompt = build_single_pass_system_prompt("ZH_PROMPT", "en-US")

    assert prompt != "ZH_PROMPT"
    assert "English only" in prompt
    assert "WARNING_MESSAGE" in prompt
    assert "---REPORT---" in prompt


def test_localize_early_warning_outputs_english_warning():
    warning = {
        "risk_score": 88,
        "risk_level": "high",
        "risk_clues": ["中文线索"],
        "warning_message": "中文警告",
        "source": "fast_fallback",
        "is_preliminary": True,
    }

    localized = localize_early_warning(warning, "en-US", has_media=True)

    assert localized is not warning
    assert localized["language"] == "en-US"
    assert localized["warning_message"].isascii()
    assert "Stop" in localized["warning_message"]
    assert all(item.isascii() for item in localized["risk_clues"])


def test_localize_early_warning_keeps_chinese_mode_untouched():
    warning = {
        "risk_score": 20,
        "risk_level": "low",
        "risk_clues": ["原始线索"],
        "warning_message": "原始警告",
    }

    assert localize_early_warning(warning, "zh-CN") is warning


def test_single_pass_system_prompt_zh_includes_qr_and_link_guardrail():
    prompt = build_single_pass_system_prompt("基础提示", "zh-CN")

    assert "基础提示" in prompt
    assert "二维码" in prompt
    assert "链接" in prompt
    assert "至少给中风险" in prompt


def test_build_role_prompt_guidance_returns_chinese_for_chinese_mode():
    guidance = build_role_prompt_guidance("elderly", "zh-CN")

    assert "Role=" not in guidance
    assert "请使用" in guidance
    assert "优先关注" in guidance
    assert "转账" in guidance


def test_single_pass_system_prompt_zh_mentions_official_anti_fraud_notice_exception():
    prompt = build_single_pass_system_prompt("基础提示", "zh-CN")

    assert "国家反诈中心" in prompt
    assert "96110" in prompt
    assert "官方反诈提醒" in prompt
