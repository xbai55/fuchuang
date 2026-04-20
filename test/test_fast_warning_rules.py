import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import fraud_detection as fd


def _reset_rule_cache() -> None:
    fd._get_fast_warning_rule_overrides.cache_clear()


def _workspace_tmp_dir(name: str) -> Path:
    path = ROOT / ".pytest-local" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_structured_hard_rule_applies_floor_score_and_explanations(monkeypatch):
    config_path = _workspace_tmp_dir("fast-warning-hard") / "fast_warning_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "structured_rules": [
                    {
                        "rule_id": "hard.police_transfer_now",
                        "type": "pattern",
                        "pattern": "法务专员.{0,8}对公监管账户",
                        "weight": 18,
                        "severity": "hard",
                        "floor_score": 90,
                        "clue": "身份冒充并要求转到监管账户",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FAST_WARNING_RULES_PATH", str(config_path))
    _reset_rule_cache()

    warning = fd._build_fast_text_warning("对方说自己是法务专员，让我把钱转到对公监管账户。", has_media=False)

    assert warning is not None
    assert warning["risk_level"] == "high"
    assert warning["risk_score"] >= 90
    assert "hard.police_transfer_now" in warning["matched_rule_ids"]
    assert warning["signal_severity"] == "hard"
    assert warning["popup_severity"] == "blocking"
    assert warning["matched_spans"]
    assert warning["source_priority"][0] == "fast_text_rules"
    assert any(
        component["id"] == "hard.police_transfer_now" and component.get("floor_applied") is True
        for component in warning["score_breakdown"]["components"]
    )


def test_soft_consultative_rule_does_not_force_high_risk(monkeypatch):
    config_path = _workspace_tmp_dir("fast-warning-soft") / "fast_warning_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "structured_rules": [
                    {
                        "rule_id": "soft.customer_service_refund",
                        "type": "keyword",
                        "keyword": "客服",
                        "weight": 10,
                        "severity": "soft",
                        "floor_score": 0,
                    },
                    {
                        "rule_id": "soft.refund",
                        "type": "keyword",
                        "keyword": "退款",
                        "weight": 10,
                        "severity": "soft",
                        "floor_score": 0,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FAST_WARNING_RULES_PATH", str(config_path))
    _reset_rule_cache()

    warning = fd._build_fast_text_warning("我想了解客服退款诈骗怎么识别，做科普分享用。", has_media=False)

    assert warning is not None
    assert warning["risk_level"] != "high"
    assert warning["popup_severity"] != "blocking"
    assert warning["signal_severity"] == "soft"
    assert warning["consultative_context"] is True
    assert "soft.customer_service_refund" in warning["matched_rule_ids"]
    assert "soft.refund" in warning["matched_rule_ids"]
    assert warning["guardian_intervention_required"] is False


def test_critical_warning_exposes_matched_spans_and_source_priority():
    warning = fd.build_critical_text_guardrail_warning(
        "有人打电话给我说是警察，让我马上把钱转到指定账户，否则报警"
    )

    assert warning is not None
    assert warning["matched_spans"]
    assert warning["source_priority"][0] == "critical_text_guardrail"
    assert warning["score_breakdown"]["floor_score"] >= 90


def test_default_config_uses_structured_rules_instead_of_legacy_rule_buckets():
    config = json.loads((ROOT / "config" / "fast_warning_rules.json").read_text(encoding="utf-8"))

    assert config.get("structured_rules")
    assert not config.get("pattern_rules")
    assert not config.get("keyword_weights")
    assert not config.get("combination_rules")

    for rule in config["structured_rules"][:10]:
        assert rule["severity"] in {"hard", "soft"}
        assert "rule_id" in rule
        assert "floor_score" in rule

    for profile in (config.get("role_profiles") or {}).values():
        assert profile.get("structured_rules")
        assert not profile.get("pattern_rules")
        assert not profile.get("keyword_weights")
        assert not profile.get("combination_rules")
