import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
TEST_RUNTIME_DIR = ROOT / "test" / ".runtime_multimodal"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import fraud_detection as fd
from src.brain.risk.risk_engine import RiskEngine
from src.core.interfaces.llm_client import LLMResponse
from src.core.models import GlobalState, MediaFile, MediaType, UserContext, UserRole


class _CaptureLLMClient:
    def __init__(self):
        self.calls = []

    async def achat(self, system_prompt, user_prompt, parse_json=True, config=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "parse_json": parse_json,
            }
        )
        return LLMResponse(
            content='{"risk_score": 82, "risk_level": "high", "scam_type": "video_test", "risk_clues": ["video"], "reasoning": "direct video"}',
            parsed_json={
                "risk_score": 82,
                "risk_level": "high",
                "scam_type": "video_test",
                "risk_clues": ["video"],
                "reasoning": "direct video",
            },
            model="fake-model",
        )


def _create_video_fixture() -> Path:
    TEST_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    video_path = TEST_RUNTIME_DIR / "sample.mp4"
    video_path.write_bytes(b"fake-video-bytes")
    return video_path


def test_risk_engine_sends_text_and_raw_video_to_llm():
    video_path = _create_video_fixture()

    llm = _CaptureLLMClient()
    engine = RiskEngine(llm_client=llm, use_rag_detector=False)
    state = GlobalState(
        input_text="请结合文字和视频判断风险",
        input_files=[MediaFile(type=MediaType.VIDEO, url=str(video_path))],
        user_context=UserContext(user_role=UserRole.GENERAL),
        workflow_metadata={"performance_timing": {}, "language": "zh-CN"},
    )

    assessment = asyncio.run(
        engine._assess_with_llm(
            state,
            low_threshold=40,
            high_threshold=75,
            dynamic_thresholds={
                "low_threshold": 40,
                "high_threshold": 75,
                "adjustment_reasons": [],
            },
        )
    )

    payload = llm.calls[0]["user_prompt"]
    assert isinstance(payload, list)
    assert payload[0]["type"] == "text"
    assert "请结合文字和视频判断风险" in payload[0]["text"]
    assert payload[1]["type"] == "video_url"
    assert payload[1]["video_url"]["url"].startswith("data:video/mp4;base64,")
    assert assessment.score == 82


def test_single_pass_stream_sends_text_and_raw_video_to_llm(monkeypatch):
    video_path = _create_video_fixture()

    published_events = []

    monkeypatch.setattr(fd, "_get_single_pass_model_config", lambda: {"base_url": "https://example.com/v1", "model": "fake"})
    monkeypatch.setattr(fd, "_is_ollama_native_streaming_enabled", lambda base_url: False)
    monkeypatch.setattr(fd, "_get_single_pass_fraud_llm", lambda: object())
    monkeypatch.setattr(fd, "_build_single_pass_user_prompt", lambda **kwargs: "PROMPT BODY")
    monkeypatch.setattr(fd, "_get_single_pass_system_prompt", lambda mode, language: "SYSTEM BODY")
    monkeypatch.setattr(fd.task_manager, "publish_task_event", lambda task_id, payload: published_events.append((task_id, payload)))
    monkeypatch.setattr(fd.task_manager, "update_task_progress", lambda *args, **kwargs: None)

    async def _fake_stream(messages, model_config, system_prompt):
        assert system_prompt == "SYSTEM BODY"
        assert isinstance(messages[1].content, list)
        assert messages[1].content[0]["type"] == "text"
        assert messages[1].content[0]["text"] == "PROMPT BODY"
        assert messages[1].content[1]["type"] == "video_url"
        assert messages[1].content[1]["video_url"]["url"].startswith("data:video/mp4;base64,")
        yield "RISK_SCORE: 76\n", "fake_backend"
        yield "RISK_LEVEL: high\n", "fake_backend"
        yield "SCAM_TYPE: raw_video_case\n", "fake_backend"
        yield "GUARDIAN_ALERT: false\n", "fake_backend"
        yield "WARNING_MESSAGE: test warning\n", "fake_backend"
        yield "---REPORT---\n", "fake_backend"
        yield "final report", "fake_backend"

    monkeypatch.setattr(fd, "_stream_single_pass_chunks", _fake_stream)

    result, total_chunks = asyncio.run(
        fd._run_single_pass_detection_stream(
            task_id="task-video",
            message="原始文本",
            user_role="general",
            early_warning={"risk_score": 10, "risk_level": "low", "warning_message": "fallback", "risk_clues": []},
            has_media=True,
            model_mode="flash",
            language="zh-CN",
            memory_context={"short_term_memory_summary": ""},
            dynamic_thresholds={"low_threshold": 40, "high_threshold": 75},
            video_path=str(video_path),
        )
    )

    assert result["risk_score"] == 76
    assert total_chunks >= 1
    assert any(event_payload.get("event") == "report_stream_started" for _, event_payload in published_events)
