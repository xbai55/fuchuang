from __future__ import annotations

from dataclasses import dataclass, field
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
    backend: str = "tfidf"
    dense_model: str = "BAAI/bge-base-zh-v1.5"
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


@dataclass(slots=True)
class AppConfig:
    paths: PathsConfig
    index: IndexConfig
    warning: WarningConfig
    sources: SourcesConfig
    photo_types_seed_file: Path


def _dict(data: dict[str, Any] | None) -> dict[str, Any]:
    return data or {}


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    root = config_path.parent.parent if config_path.parent.name == "configs" else config_path.parent
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    paths_raw = _dict(raw.get("paths"))
    index_raw = _dict(raw.get("index"))
    warning_raw = _dict(raw.get("warning"))
    sources_raw = _dict(raw.get("sources"))

    def _resolve(value: str, fallback: str) -> Path:
        return root / Path(paths_raw.get(value, fallback))

    paths = PathsConfig(
        raw_documents=_resolve("raw_documents", "data/raw/documents.jsonl"),
        processed_documents=_resolve("processed_documents", "data/processed/documents.jsonl"),
        chunks=_resolve("chunks", "data/processed/chunks.jsonl"),
        index_dir=_resolve("index_dir", "artifacts/index"),
    )
    index = IndexConfig(
        backend=index_raw.get("backend", "tfidf"),
        dense_model=index_raw.get("dense_model", "BAAI/bge-base-zh-v1.5"),
        chunk_size=int(index_raw.get("chunk_size", 420)),
        chunk_overlap=int(index_raw.get("chunk_overlap", 80)),
        top_k=int(index_raw.get("top_k", 6)),
    )
    warning = WarningConfig(
        high_threshold=float(warning_raw.get("high_threshold", 0.32)),
        medium_threshold=float(warning_raw.get("medium_threshold", 0.18)),
    )

    def _search_source(name: str) -> SearchSourceConfig:
        section = _dict(sources_raw.get(name))
        return SearchSourceConfig(
            enabled=bool(section.get("enabled", True)),
            search_terms=list(section.get("search_terms", [])),
            title_include=list(section.get("title_include", [])),
            page_size=int(section.get("page_size", 10)),
            max_pages_per_query=int(section.get("max_pages_per_query", 1)),
            position=int(section.get("position", 0)),
        )

    seed_urls = [
        SeedUrlConfig(
            url=item["url"],
            category=item["category"],
            subtype=item.get("subtype"),
            tags=list(item.get("tags", [])),
        )
        for item in sources_raw.get("seed_urls", [])
    ]
    sources = SourcesConfig(
        seed_urls=seed_urls,
        npc=_search_source("npc"),
        court=_search_source("court"),
        gov_images=_search_source("gov_images"),
    )
    photo_types_seed_file = root / Path(raw.get("photo_types_seed_file", "configs/photo_types.seed.yaml"))

    return AppConfig(
        paths=paths,
        index=index,
        warning=warning,
        sources=sources,
        photo_types_seed_file=photo_types_seed_file,
    )
