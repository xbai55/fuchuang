import asyncio
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import model_warmup


def test_warmup_models_preloads_fast_rag_bundle(monkeypatch):
    monkeypatch.setenv("MODEL_WARMUP_ENABLED", "true")
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "false")

    fake_graph = types.ModuleType("src.graphs.graph")
    fake_graph.get_main_graph = lambda: object()
    fake_graph.get_graph_components = lambda: {}
    monkeypatch.setitem(sys.modules, "src.graphs.graph", fake_graph)

    class _FakeManager:
        async def initialize(self):
            return None

        async def warmup(self):
            return {"audio": "skipped", "video": "skipped", "ocr": "skipped"}

    fake_manager_module = types.ModuleType("src.perception.manager")
    fake_manager_module.get_perception_manager = lambda: _FakeManager()
    monkeypatch.setitem(sys.modules, "src.perception.manager", fake_manager_module)

    preload_calls: list[str] = []

    async def _fake_get_fast_rag_bundle():
        preload_calls.append("called")
        return {"retriever": object(), "detector": object(), "top_k": 4}

    fake_fraud_detection = types.ModuleType("api.fraud_detection")
    fake_fraud_detection._get_fast_rag_bundle = _fake_get_fast_rag_bundle
    monkeypatch.setitem(sys.modules, "api.fraud_detection", fake_fraud_detection)

    result = asyncio.run(model_warmup.warmup_models())

    assert preload_calls == ["called"]
    assert result["steps"]["fast_rag"]["status"] == "ok"
