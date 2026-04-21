import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.language_prompts import build_single_pass_system_prompt
from backend.risk_guardrails import (
    apply_critical_warning_floor,
    build_critical_text_guardrail_warning,
    is_authoritative_anti_fraud_notice,
)


def test_police_transfer_threat_is_high_risk_guardrail():
    warning = build_critical_text_guardrail_warning(
        "有人打电话给我说是警察，让我马上把钱转到指定账户，否则报警"
    )

    assert warning is not None
    assert warning["risk_level"] == "high"
    assert warning["risk_score"] >= 90
    assert warning["guardian_alert"] is True
    assert warning["scam_type"] == "冒充公检法诈骗"


def test_common_fraud_types_have_high_risk_guardrails():
    samples = [
        ("客服说退款需要我提供验证码并打开屏幕共享", "冒充客服退款诈骗"),
        ("做刷单任务要先垫付充值，完成后返利", "刷单返利诈骗"),
        ("贷款放款前要先交保证金和解冻费", "虚假贷款诈骗"),
        ("投资老师说有内幕消息，充值USDT稳赚高收益", "虚假投资理财诈骗"),
        ("裸聊视频被录下来了，对方要求转账封口费", "裸聊敲诈诈骗"),
        ("领导微信让我马上给对公账户转账", "冒充领导诈骗"),
        ("有人说我儿子被抓了，要马上汇款处理", "冒充亲属紧急求助诈骗"),
        ("对方说可以注销校园贷修复征信，但要先交手续费", "征信修复/注销校园贷诈骗"),
        ("对方让我下载远程协助软件并共享屏幕查看银行卡", "远程控制诈骗"),
    ]

    for text, scam_type in samples:
        warning = build_critical_text_guardrail_warning(text)

        assert warning is not None, text
        assert warning["risk_level"] == "high", text
        assert warning["risk_score"] >= 85, text
        assert warning["scam_type"] == scam_type


def test_critical_guardrail_floor_overrides_low_llm_score():
    warning = build_critical_text_guardrail_warning(
        "有人打电话给我说是警察，让我马上把钱转到指定账户，否则报警"
    )
    low_llm_result = {
        "risk_score": 12,
        "risk_level": "low",
        "score_source": "single_pass_llm",
        "guardian_alert": False,
        "risk_clues": [],
    }

    guarded = apply_critical_warning_floor(low_llm_result, warning)

    assert guarded["risk_level"] == "high"
    assert guarded["risk_score"] >= 90
    assert guarded["guardian_alert"] is True
    assert guarded["score_source"] == "critical_text_guardrail_floor"


def test_critical_guardrail_floor_survives_source_rewrite():
    warning = build_critical_text_guardrail_warning(
        "有人打电话给我说是警察，让我马上把钱转到指定账户，否则报警"
    )
    warning = {**warning, "source": "rules_rag_image_ai_fusion"}

    guarded = apply_critical_warning_floor({"risk_score": 12, "risk_level": "low"}, warning)

    assert guarded["risk_level"] == "high"
    assert guarded["risk_score"] >= 90


def test_fraud_detection_pipeline_invokes_critical_guardrails():
    source = (ROOT / "backend" / "api" / "fraud_detection.py").read_text(encoding="utf-8")

    assert "build_critical_text_guardrail_warning" in source
    assert "apply_critical_warning_floor" in source


def test_single_pass_prompt_contains_law_enforcement_transfer_floor():
    prompt = build_single_pass_system_prompt("基础提示", "zh-CN")

    assert "警察" in prompt
    assert "转账" in prompt
    assert "高风险" in prompt
    assert "刷单返利" in prompt
    assert "冒充客服" in prompt


def test_critical_guardrail_exposes_popup_and_score_explanation():
    warning = build_critical_text_guardrail_warning(
        "\u6709\u4eba\u6253\u7535\u8bdd\u8bf4\u662f\u8b66\u5bdf\uff0c"
        "\u8ba9\u6211\u9a6c\u4e0a\u628a\u94b1\u8f6c\u5230\u6307\u5b9a\u8d26\u6237"
    )

    assert warning is not None
    assert warning["popup_severity"] == "blocking"
    assert warning["voice_warning_required"] is True
    assert warning["matched_rule_ids"] == ["critical:law_enforcement_transfer"]
    assert warning["score_breakdown"]["source"] == "critical_text_guardrail"

    guarded = apply_critical_warning_floor(
        {"risk_score": 12, "risk_level": "low", "guardian_alert": False},
        warning,
    )

    assert guarded["critical_guardrail_triggered"] is True
    assert guarded["popup_severity"] == "blocking"
    assert guarded["voice_warning_required"] is True
    assert guarded["matched_rule_ids"] == ["critical:law_enforcement_transfer"]


def test_qr_and_link_lure_is_high_risk_guardrail():
    warning = build_critical_text_guardrail_warning(
        "对方让我长按识别二维码领取补贴，再点链接下载APP填写信息。"
    )

    assert warning is not None
    assert warning["risk_level"] == "high"
    assert warning["risk_score"] >= 85
    assert warning["scam_type"] == "二维码/链接诱导诈骗"


def test_default_fast_warning_rules_include_qr_and_link_soft_and_hard_rules():
    config = json.loads((ROOT / "config" / "fast_warning_rules.json").read_text(encoding="utf-8"))
    rule_ids = {rule["rule_id"] for rule in config.get("structured_rules") or []}

    assert "soft.qr_link_redirect" in rule_ids
    assert "hard.qr_link_reward_lure" in rule_ids


def test_authoritative_anti_fraud_notice_is_recognized():
    text = "【国家反诈中心】公安部刑侦局提醒您：凡是要求您点击链接下载App进行理赔、退税或办贷款的，都是诈骗！如有疑问请拨打96110咨询。"

    assert is_authoritative_anti_fraud_notice(text) is True
    assert build_critical_text_guardrail_warning(text) is None
