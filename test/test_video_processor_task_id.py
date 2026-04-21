import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.models import MediaFile, MediaType
from src.perception.processors.video_processor import VideoProcessor


class _FakeAnalyzer:
    def predict_from_path(self, _file_path: str) -> float:
        return 0.1


class _FakeKeyframeResult:
    frame_paths = []
    frame_dir = "fake-dir"


class _FakeKeyframeExtractor:
    def __init__(self) -> None:
        self.task_ids: list[str | None] = []

    def extract(self, _file_path: str, task_id: str | None) -> _FakeKeyframeResult:
        self.task_ids.append(task_id)
        return _FakeKeyframeResult()


async def _run_process(extractor: _FakeKeyframeExtractor) -> tuple[list[str | None], dict]:
    processor = VideoProcessor()
    processor._initialized = True
    processor._fake_analyzer = _FakeAnalyzer()
    processor._keyframe_extractor = extractor
    processor._ocr_enabled = False

    result = await processor.process(
        MediaFile(type=MediaType.VIDEO, url="demo.mp4"),
        context={"task_id": None},
    )
    return extractor.task_ids, result.model_dump()


def test_video_processor_defaults_task_id_when_context_value_is_none(monkeypatch):
    import src.perception.processors.video_processor as video_processor_module

    async def _fake_run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(video_processor_module, "run_in_threadpool", _fake_run_in_threadpool)
    monkeypatch.setattr(video_processor_module, "is_url", lambda _value: False)

    extractor = _FakeKeyframeExtractor()
    task_ids, result = asyncio.run(_run_process(extractor))

    assert task_ids == ["default"]
    assert result["metadata"]["keyframe_count"] == 0
