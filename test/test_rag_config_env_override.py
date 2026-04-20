import shutil
from pathlib import Path

from src.brain.rag.config import load_rag_config


ROOT = Path(__file__).resolve().parents[1]


def _make_temp_dir(name: str) -> Path:
    path = ROOT / ".pytest-local" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_config(tmp_path: Path, backend: str = "hybrid") -> Path:
    config_path = tmp_path / "rag.yaml"
    config_path.write_text(
        f"""
paths:
  raw_documents: data/raw/documents.jsonl
  processed_documents: data/processed/documents.jsonl
  chunks: data/processed/chunks.jsonl
  index_dir: data/index
index:
  backend: {backend}
  dense_model: local-hash
  chunk_size: 420
  chunk_overlap: 80
  top_k: 6
warning:
  high_threshold: 0.32
  medium_threshold: 0.18
sources:
  seed_urls: []
photo_types_seed_file: config/photo_types.seed.yaml
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_rag_index_backend_env_overrides_yaml(monkeypatch):
    config_path = _write_config(_make_temp_dir("rag-config-env-override"), backend="hybrid")
    monkeypatch.setenv("RAG_INDEX_BACKEND", "tfidf")

    config = load_rag_config(config_path)

    assert config.index.backend == "tfidf"


def test_invalid_rag_index_backend_env_falls_back_to_yaml(monkeypatch):
    config_path = _write_config(_make_temp_dir("rag-config-env-invalid"), backend="hybrid")
    monkeypatch.setenv("RAG_INDEX_BACKEND", "unsupported-backend")

    config = load_rag_config(config_path)

    assert config.index.backend == "hybrid"
