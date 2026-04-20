import json
import shutil
import sys
import types
from pathlib import Path
from uuid import uuid4


def _isolate_rag_imports(monkeypatch, root: Path) -> None:
    for name, path in (
        ("src.brain", root / "src" / "brain"),
        ("src.brain.rag", root / "src" / "brain" / "rag"),
        ("src.core", root / "src" / "core"),
        ("src.core.utils", root / "src" / "core" / "utils"),
    ):
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, module)

    json_utils = types.ModuleType("src.core.utils.json_utils")
    json_utils.safe_json_loads = lambda text, default=None: json.loads(text) if text else default
    monkeypatch.setitem(sys.modules, "src.core.utils.json_utils", json_utils)


def _make_temp_root() -> Path:
    base_dir = Path(__file__).resolve().parents[1] / ".manual_checks"
    base_dir.mkdir(parents=True, exist_ok=True)
    root = base_dir / f"hot-reload-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_hot_reload_keeps_configured_hybrid_backend(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    _isolate_rag_imports(monkeypatch, root)

    from src.brain.rag.hot_reload import ingest_documents
    from src.brain.rag.models import KnowledgeDocument

    temp_root = _make_temp_root()
    try:
        config_path = temp_root / "rag.yaml"
        config_path.write_text(
            """
paths:
  raw_documents: data/raw/documents.jsonl
  processed_documents: data/processed/documents.jsonl
  chunks: data/processed/chunks.jsonl
  index_dir: data/index
index:
  backend: hybrid
  dense_model: local-hash
  chunk_size: 80
  chunk_overlap: 10
  top_k: 3
warning:
  high_threshold: 0.32
  medium_threshold: 0.18
sources:
  seed_urls: []
photo_types_seed_file: config/photo_types.seed.yaml
""".strip(),
            encoding="utf-8",
        )

        doc = KnowledgeDocument(
            doc_id="case-1",
            url="https://example.test/case-1",
            canonical_url="https://example.test/case-1",
            source_site="example.test",
            category="case",
            title="测试案例",
            content="这是一个用于验证 hot reload 的本地案例文本，长度足够切分并建立索引。" * 3,
            summary="测试案例",
            source_name="unit",
            tags=[],
        )

        result = ingest_documents([doc], config_path)
        manifest = json.loads((temp_root / "data" / "index" / "manifest.json").read_text(encoding="utf-8"))

        assert result["backend"] == "hybrid"
        assert manifest["backend"] == "hybrid"
        assert manifest["index_backend"] == "tfidf"
        assert str(temp_root / "data" / "index") == result["index_dir"]
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
