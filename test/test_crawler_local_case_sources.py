import json
import shutil
from pathlib import Path
from uuid import uuid4

from src.brain.rag.config import load_rag_config_from_dict
from src.brain.rag.crawler import collect_documents


def _make_temp_root() -> Path:
    base_dir = Path(__file__).resolve().parents[1] / ".tmp_pytest"
    base_dir.mkdir(parents=True, exist_ok=True)
    root = base_dir / f"crawler-local-case-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def _make_config(root: Path, directories: list[str]):
    return load_rag_config_from_dict(
        {
            "root": str(root),
            "paths": {
                "raw_documents": "data/raw/documents.jsonl",
                "processed_documents": "data/processed/documents.jsonl",
                "chunks": "data/processed/chunks.jsonl",
                "index_dir": "data/index",
            },
            "index": {
                "backend": "hybrid",
                "dense_model": "local-hash",
                "chunk_size": 120,
                "chunk_overlap": 20,
                "top_k": 3,
            },
            "warning": {
                "high_threshold": 0.32,
                "medium_threshold": 0.18,
            },
            "sources": {
                "seed_urls": [],
                "npc": {"enabled": False},
                "court": {"enabled": False},
                "gov_images": {"enabled": False},
                "local_case_directories": directories,
            },
            "photo_types_seed_file": "config/photo_types.seed.yaml",
        }
    )


def test_collect_documents_includes_local_case_directory():
    root = _make_temp_root()
    try:
        case_dir = root / "local_cases"
        case_dir.mkdir()
        sample_file = case_dir / "sogou_cases.json"
        sample_file.write_text(
            json.dumps(
                {
                    "website_name": "搜狗反诈",
                    "source_url": "https://www.sogou.com/web?query=%E5%8F%8D%E8%AF%88",
                    "source_data": [
                        {
                            "title": "反诈防骗案例",
                            "content": "这是一个关于刷单返利诈骗的案例，包含作案手法与防范提醒。",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        docs = collect_documents(_make_config(root, ["local_cases"]))

        assert len(docs) == 1
        doc = docs[0]
        assert doc.category == "case"
        assert doc.title == "反诈防骗案例"
        assert "刷单返利诈骗" in doc.content
        assert doc.source_name == "搜狗反诈"
        assert doc.source_site == "www.sogou.com"
        assert doc.canonical_url.startswith("local-case://")
        assert doc.metadata["source_file"] == "sogou_cases.json"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_collect_documents_skips_missing_local_case_directory():
    root = _make_temp_root()
    try:
        docs = collect_documents(_make_config(root, ["missing-local-cases"]))
        assert docs == []
    finally:
        shutil.rmtree(root, ignore_errors=True)
