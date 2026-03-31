from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .crawler import collect_documents
from .index import SimilarityIndex
from .models import KnowledgeChunk
from .text import chunk_text
from .utils import read_jsonl, sha1_text, write_jsonl


def crawl_documents(config: AppConfig) -> list[dict]:
    documents = collect_documents(config)
    write_jsonl(config.paths.raw_documents, [doc.to_dict() for doc in documents])
    write_jsonl(config.paths.processed_documents, [doc.to_dict() for doc in documents])
    return [doc.to_dict() for doc in documents]


def build_chunks(config: AppConfig) -> list[KnowledgeChunk]:
    rows = read_jsonl(config.paths.processed_documents)
    chunks: list[KnowledgeChunk] = []
    for row in rows:
        text_chunks = chunk_text(
            row["content"],
            chunk_size=config.index.chunk_size,
            chunk_overlap=config.index.chunk_overlap,
        )
        for position, text in enumerate(text_chunks, start=1):
            chunk_id = sha1_text(row["doc_id"], str(position), text[:60])
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    doc_id=row["doc_id"],
                    category=row["category"],
                    subtype=row.get("subtype"),
                    title=row["title"],
                    text=text,
                    source_url=row["url"],
                    source_site=row.get("source_site", ""),
                    published_at=row.get("published_at"),
                    source_name=row.get("source_name"),
                    tags=list(row.get("tags", [])),
                    metadata={"position": position, **dict(row.get("metadata", {}))},
                )
            )
    write_jsonl(config.paths.chunks, [chunk.to_dict() for chunk in chunks])
    return chunks


def build_index(config: AppConfig, *, backend: str | None = None) -> SimilarityIndex:
    rows = read_jsonl(config.paths.chunks)
    chunks = [KnowledgeChunk.from_dict(row) for row in rows]
    chosen_backend = backend or config.index.backend
    index = SimilarityIndex.build(
        chunks,
        backend=chosen_backend,
        dense_model=config.index.dense_model,
    )
    index.save(config.paths.index_dir)
    return index


def build_all(config: AppConfig, *, backend: str | None = None) -> dict[str, int]:
    docs = crawl_documents(config)
    chunks = build_chunks(config)
    build_index(config, backend=backend)
    return {
        "documents": len(docs),
        "chunks": len(chunks),
    }


def load_index(index_dir: str | Path) -> SimilarityIndex:
    return SimilarityIndex.load(Path(index_dir))
