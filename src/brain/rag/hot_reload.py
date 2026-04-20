"""
RAG 知识库热更新
支持将新文档增量写入已有索引，无需完整重建。
流程：解析文档 → 分块 → 去重 → 追加 chunks.jsonl → 重建 TF-IDF → 保存。
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.brain.rag.config import load_rag_config
from src.brain.rag.indexer import SimilarityIndex
from src.brain.rag.models import KnowledgeChunk, KnowledgeDocument
from src.brain.rag.pipeline import chunk_text, sha1_text, read_jsonl
from src.brain.rag.auto_build import get_rag_config_path

_HOT_RELOAD_LOCK = threading.Lock()
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_existing_chunk_ids(chunks_path: Path) -> set[str]:
    if not chunks_path.exists():
        return set()
    ids: set[str] = set()
    with chunks_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    ids.add(json.loads(line)["chunk_id"])
                except (KeyError, json.JSONDecodeError):
                    pass
    return ids


def _documents_to_chunks(
    documents: list[KnowledgeDocument],
    chunk_size: int,
    chunk_overlap: int,
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for doc in documents:
        text_chunks = chunk_text(doc.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for position, text in enumerate(text_chunks, start=1):
            chunk_id = sha1_text(doc.doc_id, str(position), text[:60])
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    doc_id=doc.doc_id,
                    category=doc.category,
                    subtype=doc.subtype,
                    title=doc.title,
                    text=text,
                    source_url=doc.url,
                    source_site=doc.source_site,
                    published_at=doc.published_at,
                    source_name=doc.source_name,
                    tags=list(doc.tags),
                    metadata={"position": position, **doc.metadata},
                )
            )
    return chunks


def _append_chunks_to_jsonl(chunks_path: Path, new_chunks: list[KnowledgeChunk]) -> None:
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with chunks_path.open("a", encoding="utf-8") as fh:
        for chunk in new_chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")


def _run_coro_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_holder: dict[str, Any] = {}
    error_holder: dict[str, BaseException] = {}

    def _worker() -> None:
        try:
            result_holder["result"] = asyncio.run(coro)
        except BaseException as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder.get("result")


def _build_chromadb_index(
    chunks: list[KnowledgeChunk],
    index_dir: Path,
    dense_model: str,
) -> dict[str, Any]:
    try:
        from src.brain.rag.vector_store import ChromaVectorStore, VectorDocument

        store = ChromaVectorStore(
            collection_name="fraud_cases",
            persist_directory=str(index_dir / "chromadb"),
            embedding_model=dense_model,
        )
        documents = [
            VectorDocument(
                id=chunk.chunk_id,
                content=chunk.text,
                metadata={
                    "title": chunk.title,
                    "category": chunk.category,
                    "subtype": chunk.subtype,
                    "source": chunk.source_site,
                    "tags": chunk.tags,
                },
            )
            for chunk in chunks
        ]
        _run_coro_sync(store.add_documents(documents))
        return {
            "chromadb_status": "success",
            "chromadb_count": len(documents),
            "chromadb_dir": str(index_dir / "chromadb"),
            "embedding_model": dense_model,
        }
    except Exception as exc:
        return {
            "chromadb_status": "failed",
            "chromadb_error": str(exc),
            "chromadb_dir": str(index_dir / "chromadb"),
            "embedding_model": dense_model,
        }


def _rebuild_index(
    chunks_path: Path,
    index_dir: Path,
    backend: str,
    dense_model: str,
) -> tuple[SimilarityIndex, dict[str, Any]]:
    rows = read_jsonl(chunks_path)
    all_chunks = [KnowledgeChunk.from_dict(r) for r in rows]
    index_backend = backend if backend != "hybrid" else "tfidf"
    index = SimilarityIndex.build(all_chunks, backend=index_backend, dense_model=dense_model)
    index.save(index_dir)

    stats: dict[str, Any] = {
        "backend": backend,
        "index_backend": index.backend,
        "index_dir": str(index_dir),
    }
    if backend in ("hybrid", "sentence-transformer"):
        stats.update(_build_chromadb_index(all_chunks, index_dir, dense_model))
    return index, stats


def _update_raw_documents(raw_path: Path, documents: list[KnowledgeDocument]) -> None:
    """将新文档追加到 raw documents JSONL（便于将来重建时不丢失）。"""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("a", encoding="utf-8") as fh:
        for doc in documents:
            fh.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")


def ingest_documents(
    documents: list[KnowledgeDocument],
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    将新文档增量导入 RAG 知识库，并热更新 TF-IDF 索引。

    Args:
        documents: KnowledgeDocument 列表
        config_path: RAG 配置路径，None 时使用默认值

    Returns:
        {added_chunks, skipped_chunks, total_chunks, status}
    """
    if not documents:
        return {"added_chunks": 0, "skipped_chunks": 0, "total_chunks": 0, "status": "no_documents"}

    resolved = get_rag_config_path(config_path)
    if not resolved.exists():
        return {"status": "config_not_found", "error": str(resolved)}

    config = load_rag_config(resolved)

    with _HOT_RELOAD_LOCK:
        existing_ids = _load_existing_chunk_ids(config.paths.chunks)
        new_chunks = _documents_to_chunks(
            documents,
            chunk_size=config.index.chunk_size,
            chunk_overlap=config.index.chunk_overlap,
        )

        deduped = [c for c in new_chunks if c.chunk_id not in existing_ids]
        skipped = len(new_chunks) - len(deduped)

        if not deduped:
            total = len(read_jsonl(config.paths.chunks))
            return {
                "added_chunks": 0,
                "skipped_chunks": skipped,
                "total_chunks": total,
                "status": "all_duplicate",
            }

        _append_chunks_to_jsonl(config.paths.chunks, deduped)
        _update_raw_documents(config.paths.raw_documents, documents)

        index, index_stats = _rebuild_index(
            config.paths.chunks,
            config.paths.index_dir,
            config.index.backend,
            config.index.dense_model,
        )

        # 更新 manifest
        manifest_path = config.paths.index_dir / "manifest.json"
        manifest = {
            "backend": config.index.backend,
            "index_backend": index.backend,
            "model_name": index.model_name,
            "chunk_count": len(index.chunks),
            "last_hot_reload": _iso_now(),
            **index_stats,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "added_chunks": len(deduped),
            "skipped_chunks": skipped,
            "total_chunks": len(index.chunks),
            **index_stats,
            "status": "ok",
        }


async def ingest_documents_async(
    documents: list[KnowledgeDocument],
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """异步包装 ingest_documents，在线程池中执行以避免阻塞事件循环。"""
    return await asyncio.to_thread(ingest_documents, documents, config_path)
