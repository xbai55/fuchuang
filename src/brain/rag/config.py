"""
RAG 配置管理
从 rag/src/fraud_rag/config.py 迁移并适配
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class PathsConfig:
    """路径配置"""
    raw_documents: Path
    processed_documents: Path
    chunks: Path
    index_dir: Path


@dataclass(slots=True)
class IndexConfig:
    """索引配置"""
    backend: str = "tfidf"  # tfidf, sentence-transformer, hybrid
    dense_model: str = "BAAI/bge-base-zh-v1.5"
    chunk_size: int = 420
    chunk_overlap: int = 80
    top_k: int = 6


@dataclass(slots=True)
class WarningConfig:
    """风险预警配置"""
    high_threshold: float = 0.32
    medium_threshold: float = 0.18


@dataclass(slots=True)
class SeedUrlConfig:
    """种子 URL 配置"""
    url: str
    category: str
    subtype: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchSourceConfig:
    """搜索源配置"""
    enabled: bool = True
    search_terms: list[str] = field(default_factory=list)
    title_include: list[str] = field(default_factory=list)
    page_size: int = 10
    max_pages_per_query: int = 1
    position: int = 0


@dataclass(slots=True)
class SourcesConfig:
    """数据源配置"""
    seed_urls: list[SeedUrlConfig] = field(default_factory=list)
    npc: SearchSourceConfig = field(default_factory=SearchSourceConfig)
    court: SearchSourceConfig = field(default_factory=SearchSourceConfig)
    gov_images: SearchSourceConfig = field(default_factory=SearchSourceConfig)


@dataclass
class RAGConfig:
    """RAG 完整配置"""
    paths: PathsConfig
    index: IndexConfig
    warning: WarningConfig
    sources: SourcesConfig
    photo_types_seed_file: Path


def _dict(data: dict[str, Any] | None) -> dict[str, Any]:
    """安全的字典转换"""
    return data or {}


def load_rag_config(path: str | Path) -> RAGConfig:
    """
    从 YAML 文件加载 RAG 配置

    Args:
        path: 配置文件路径

    Returns:
        RAGConfig 对象
    """
    config_path = Path(path)
    root = config_path.parent.parent if config_path.parent.name == "configs" else config_path.parent

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    paths_raw = _dict(raw.get("paths"))
    index_raw = _dict(raw.get("index"))
    warning_raw = _dict(raw.get("warning"))
    sources_raw = _dict(raw.get("sources"))

    def _resolve(value: str, fallback: str) -> Path:
        """解析相对路径"""
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
        """解析搜索源配置"""
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

    photo_types_seed_file = root / Path(
        raw.get("photo_types_seed_file", "configs/photo_types.seed.yaml")
    )

    return RAGConfig(
        paths=paths,
        index=index,
        warning=warning,
        sources=sources,
        photo_types_seed_file=photo_types_seed_file,
    )


def load_rag_config_from_dict(config: dict[str, Any]) -> RAGConfig:
    """
    从字典加载 RAG 配置

    Args:
        config: 配置字典

    Returns:
        RAGConfig 对象
    """
    root = Path(config.get("root", "."))

    paths_config = config.get("paths", {})
    paths = PathsConfig(
        raw_documents=root / Path(paths_config.get("raw_documents", "data/raw/documents.jsonl")),
        processed_documents=root / Path(paths_config.get("processed_documents", "data/processed/documents.jsonl")),
        chunks=root / Path(paths_config.get("chunks", "data/processed/chunks.jsonl")),
        index_dir=root / Path(paths_config.get("index_dir", "artifacts/index")),
    )

    index_config = config.get("index", {})
    index = IndexConfig(
        backend=index_config.get("backend", "tfidf"),
        dense_model=index_config.get("dense_model", "BAAI/bge-base-zh-v1.5"),
        chunk_size=index_config.get("chunk_size", 420),
        chunk_overlap=index_config.get("chunk_overlap", 80),
        top_k=index_config.get("top_k", 6),
    )

    warning_config = config.get("warning", {})
    warning = WarningConfig(
        high_threshold=warning_config.get("high_threshold", 0.32),
        medium_threshold=warning_config.get("medium_threshold", 0.18),
    )

    # 简化版：不解析复杂的数据源配置
    sources = SourcesConfig()

    photo_types_seed_file = root / Path(
        config.get("photo_types_seed_file", "configs/photo_types.seed.yaml")
    )

    return RAGConfig(
        paths=paths,
        index=index,
        warning=warning,
        sources=sources,
        photo_types_seed_file=photo_types_seed_file,
    )
