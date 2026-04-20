import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import fraud_detection as fd


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self):
        self.saved_rows = []

    def query(self, model):
        return _FakeQuery([])

    def add(self, row):
        self.saved_rows.append(row)

    def commit(self):
        return None


def _fake_user(role: str, language: str = "zh-CN"):
    return SimpleNamespace(
        id=1001,
        user_role=role,
        language=language,
        guardian_name="监护人",
        notify_enabled=False,
        notify_high_risk=False,
        notify_guardian_alert=False,
        age_group="adult",
        gender="unknown",
        occupation="other",
    )


def _run_role_detection_case(monkeypatch, *, language: str, message: str):
    captured_prompts: dict[str, str] = {}

    monkeypatch.setattr(fd, "_save_uploads_with_timing", lambda *args, **kwargs: (None, None, None, {}))
    monkeypatch.setattr(fd, "_should_use_single_pass", lambda **kwargs: True)
    monkeypatch.setattr(
        fd,
        "_build_user_memory_context",
        lambda db, current_user, message: {
            "short_term_memory_summary": "暂无短期风险记忆" if language != "en-US" else "No recent memory",
            "long_term_memory_summary": "暂无长期历史行为记录" if language != "en-US" else "No long-term history",
            "combined_profile_text": "画像占位" if language != "en-US" else "profile-placeholder",
            "dynamic_thresholds": {
                "low_threshold": 40,
                "high_threshold": 75,
                "adjustment_reasons": ["baseline"],
            },
        },
    )

    async def _fake_fast_warning(*args, **kwargs):
        return {
            "risk_score": 18,
            "risk_level": "low",
            "warning_message": "test-warning" if language == "en-US" else "测试预警",
            "risk_clues": ["test-clue" if language == "en-US" else "测试线索"],
            "source": "fast_fallback",
        }

    monkeypatch.setattr(fd, "_build_fast_early_warning", _fake_fast_warning)

    async def _fake_send_email(*args, **kwargs):
        return None

    monkeypatch.setattr(fd, "send_high_risk_email_if_needed", _fake_send_email)

    async def _fake_record_request(*args, **kwargs):
        return None

    monkeypatch.setattr(fd.monitoring_service, "record_request", _fake_record_request)

    async def _fake_single_pass(*, message, user_role, early_warning, has_media, language, memory_context, dynamic_thresholds, **kwargs):
        prompt = fd._build_single_pass_user_prompt(
            message=message,
            user_role=user_role,
            early_warning=early_warning,
            has_media=has_media,
            memory_context=memory_context,
            dynamic_thresholds=dynamic_thresholds,
            language=language,
        )
        captured_prompts[user_role] = prompt
        return (
            {
                "risk_score": 58,
                "risk_level": "medium",
                "scam_type": "test_case",
                "guardian_alert": False,
                "warning_message": f"role:{user_role}",
                "risk_clues": [f"role:{user_role}"],
                "final_report": f"role={user_role}\n{prompt[:160]}",
                "action_items": [],
                "performance_timing": {},
            },
            1,
        )

    monkeypatch.setattr(fd, "_run_single_pass_detection_stream", _fake_single_pass)

    student_response = asyncio.run(
        fd.detect_fraud(
            message=message,
            language=language,
            current_user=_fake_user("student", language=language),
            db=_FakeDB(),
        )
    )
    finance_response = asyncio.run(
        fd.detect_fraud(
            message=message,
            language=language,
            current_user=_fake_user("finance", language=language),
            db=_FakeDB(),
        )
    )

    return student_response, finance_response, captured_prompts


def test_detect_fraud_same_message_differs_by_role(monkeypatch):
    student_response, finance_response, captured_prompts = _run_role_detection_case(
        monkeypatch,
        language="zh-CN",
        message="对方让我现在转账，还让我把验证码发过去，这正常吗？",
    )

    assert student_response["code"] == 200
    assert finance_response["code"] == 200

    assert "student" in captured_prompts
    assert "finance_practitioner" in captured_prompts
    assert "Role=student" in captured_prompts["student"]
    assert "Role=finance_practitioner" in captured_prompts["finance_practitioner"]
    assert captured_prompts["student"] != captured_prompts["finance_practitioner"]

    assert student_response["data"]["final_report"] != finance_response["data"]["final_report"]
    assert student_response["data"]["warning_message"] != finance_response["data"]["warning_message"]


def test_detect_fraud_en_us_prompt_branch_differs_by_role(monkeypatch):
    student_response, finance_response, captured_prompts = _run_role_detection_case(
        monkeypatch,
        language="en-US",
        message="The caller asks me to wire money now and share OTP. Is this a scam?",
    )

    assert student_response["code"] == 200
    assert finance_response["code"] == 200

    assert "student" in captured_prompts
    assert "finance_practitioner" in captured_prompts
    assert "Output language: English only." in captured_prompts["student"]
    assert "Output language: English only." in captured_prompts["finance_practitioner"]
    assert "Role=student" in captured_prompts["student"]
    assert "Role=finance_practitioner" in captured_prompts["finance_practitioner"]
    assert captured_prompts["student"] != captured_prompts["finance_practitioner"]

    assert student_response["data"]["final_report"] != finance_response["data"]["final_report"]
    assert student_response["data"]["warning_message"] != finance_response["data"]["warning_message"]
