from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class PathsConfig:
    raw_documents: Path
    processed_documents: Path
    chunks: Path
    index_dir: Path


@dataclass(slots=True)
class IndexConfig:
    backend: str = "tfidf"  # tfidf, sentence-transformer, hybrid
    dense_model: str = "local-hash"
    chunk_size: int = 420
    chunk_overlap: int = 80
    top_k: int = 6


@dataclass(slots=True)
class WarningConfig:
    high_threshold: float = 0.32
    medium_threshold: float = 0.18


@dataclass(slots=True)
class SeedUrlConfig:
    url: str
    category: str
    subtype: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchSourceConfig:
    enabled: bool = True
    search_terms: list[str] = field(default_factory=list)
    title_include: list[str] = field(default_factory=list)
    page_size: int = 10
    max_pages_per_query: int = 1
    position: int = 0


@dataclass(slots=True)
class SourcesConfig:
    seed_urls: list[SeedUrlConfig] = field(default_factory=list)
    npc: SearchSourceConfig = field(default_factory=SearchSourceConfig)
    court: SearchSourceConfig = field(default_factory=SearchSourceConfig)
    gov_images: SearchSourceConfig = field(default_factory=SearchSourceConfig)
    local_case_directories: list[Path] = field(default_factory=list)


@dataclass
class RAGConfig:
    paths: PathsConfig
    index: IndexConfig
    warning: WarningConfig
    sources: SourcesConfig
    photo_types_seed_file: Path


_SUPPORTED_INDEX_BACKENDS = {"tfidf", "hybrid", "sentence-transformer"}


def _dict(data: dict[str, Any] | None) -> dict[str, Any]:
    return data or {}


def _resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _normalize_index_backend(value: Any, default: str = "tfidf") -> str:
    candidate = str(value or "").strip().lower()
    if candidate in _SUPPORTED_INDEX_BACKENDS:
        return candidate
    return default


def _resolve_index_backend(configured_backend: Any) -> str:
    fallback = _normalize_index_backend(configured_backend, default="tfidf")
    env_backend = os.getenv("RAG_INDEX_BACKEND", "")
    return _normalize_index_backend(env_backend, default=fallback)


def _build_search_source(section: dict[str, Any] | None) -> SearchSourceConfig:
    section = _dict(section)
    return SearchSourceConfig(
        enabled=bool(section.get("enabled", True)),
        search_terms=list(section.get("search_terms", [])),
        title_include=list(section.get("title_include", [])),
        page_size=int(section.get("page_size", 10)),
        max_pages_per_query=int(section.get("max_pages_per_query", 1)),
        position=int(section.get("position", 0)),
    )


def _build_sources(root: Path, sources_raw: dict[str, Any] | None) -> SourcesConfig:
    sources_raw = _dict(sources_raw)
    seed_urls = [
        SeedUrlConfig(
            url=item["url"],
            category=item["category"],
            subtype=item.get("subtype"),
            tags=list(item.get("tags", [])),
        )
        for item in sources_raw.get("seed_urls", [])
    ]
    return SourcesConfig(
        seed_urls=seed_urls,
        npc=_build_search_source(sources_raw.get("npc")),
        court=_build_search_source(sources_raw.get("court")),
        gov_images=_build_search_source(sources_raw.get("gov_images")),
        local_case_directories=[
            _resolve_path(root, item)
            for item in sources_raw.get("local_case_directories", [])
        ],
    )


def load_rag_config(path: str | Path) -> RAGConfig:
    config_path = Path(path)
    root = config_path.parent.parent if config_path.parent.name == "configs" else config_path.parent

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    paths_raw = _dict(raw.get("paths"))
    index_raw = _dict(raw.get("index"))
    warning_raw = _dict(raw.get("warning"))

    def _resolve(value: str, fallback: str) -> Path:
        return _resolve_path(root, paths_raw.get(value, fallback))

    paths = PathsConfig(
        raw_documents=_resolve("raw_documents", "data/raw/documents.jsonl"),
        processed_documents=_resolve("processed_documents", "data/processed/documents.jsonl"),
        chunks=_resolve("chunks", "data/processed/chunks.jsonl"),
        index_dir=_resolve("index_dir", "artifacts/index"),
    )
    resolved_backend = _resolve_index_backend(index_raw.get("backend", "tfidf"))
    index = IndexConfig(
        backend=resolved_backend,
        dense_model=index_raw.get("dense_model", "local-hash"),
        chunk_size=int(index_raw.get("chunk_size", 420)),
        chunk_overlap=int(index_raw.get("chunk_overlap", 80)),
        top_k=int(index_raw.get("top_k", 6)),
    )
    warning = WarningConfig(
        high_threshold=float(warning_raw.get("high_threshold", 0.32)),
        medium_threshold=float(warning_raw.get("medium_threshold", 0.18)),
    )
    sources = _build_sources(root, raw.get("sources"))
    photo_types_seed_file = _resolve_path(
        root,
        raw.get("photo_types_seed_file", "configs/photo_types.seed.yaml"),
    )

    return RAGConfig(
        paths=paths,
        index=index,
        warning=warning,
        sources=sources,
        photo_types_seed_file=photo_types_seed_file,
    )


def load_rag_config_from_dict(config: dict[str, Any]) -> RAGConfig:
    root = Path(config.get("root", "."))

    paths_config = _dict(config.get("paths"))
    paths = PathsConfig(
        raw_documents=_resolve_path(root, paths_config.get("raw_documents", "data/raw/documents.jsonl")),
        processed_documents=_resolve_path(root, paths_config.get("processed_documents", "data/processed/documents.jsonl")),
        chunks=_resolve_path(root, paths_config.get("chunks", "data/processed/chunks.jsonl")),
        index_dir=_resolve_path(root, paths_config.get("index_dir", "artifacts/index")),
    )

    index_config = _dict(config.get("index"))
    resolved_backend = _resolve_index_backend(index_config.get("backend", "tfidf"))
    index = IndexConfig(
        backend=resolved_backend,
        dense_model=index_config.get("dense_model", "local-hash"),
        chunk_size=int(index_config.get("chunk_size", 420)),
        chunk_overlap=int(index_config.get("chunk_overlap", 80)),
        top_k=int(index_config.get("top_k", 6)),
    )

    warning_config = _dict(config.get("warning"))
    warning = WarningConfig(
        high_threshold=float(warning_config.get("high_threshold", 0.32)),
        medium_threshold=float(warning_config.get("medium_threshold", 0.18)),
    )

    sources = _build_sources(root, config.get("sources"))
    photo_types_seed_file = _resolve_path(
        root,
        config.get("photo_types_seed_file", "configs/photo_types.seed.yaml"),
    )

    return RAGConfig(
        paths=paths,
        index=index,
        warning=warning,
        sources=sources,
        photo_types_seed_file=photo_types_seed_file,
    )
