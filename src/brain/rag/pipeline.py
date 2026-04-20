"""
知识库构建管道
从 rag/src/fraud_rag/pipeline.py 迁移
整合文档爬取、分块、索引构建流程
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import List, Iterable, Optional

from src.brain.rag.models import KnowledgeChunk, KnowledgeDocument
from src.brain.rag.indexer import SimilarityIndex
from src.brain.rag.config import RAGConfig, load_rag_config_from_dict
from src.brain.rag.crawler import collect_documents


def sha1_text(*parts: str) -> str:
    """生成文本的 SHA1 哈希"""
    digest = hashlib.sha1()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def ensure_parent(path: Path) -> None:
    """确保父目录存在"""
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    """写入 JSON Lines 文件"""
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    """读取 JSON Lines 文件"""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def unique_preserve(items: Iterable[str]) -> list[str]:
    """去重列表保持顺序"""
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def normalize_whitespace(text: str) -> str:
    """规范化空白字符"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    """清理文本"""
    text = normalize_whitespace(text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def build_summary(text: str, limit: int = 160) -> str:
    """构建摘要"""
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _split_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    """分割长段落"""
    if len(paragraph) <= chunk_size:
        return [paragraph]
    parts = re.split(r"(?<=[。！？；])", paragraph)
    parts = [part.strip() for part in parts if part.strip()]
    output: list[str] = []
    current = ""
    for part in parts:
        if not current:
            current = part
            continue
        if len(current) + len(part) <= chunk_size:
            current += part
            continue
        output.append(current)
        current = part
    if current:
        output.append(current)
    return output or [paragraph]


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    将文本分块

    Args:
        text: 原始文本
        chunk_size: 每块最大字符数
        chunk_overlap: 块间重叠字符数

    Returns:
        文本块列表
    """
    text = clean_text(text)
    if not text:
        return []

    paragraphs: list[str] = []
    for paragraph in text.split("\n"):
        paragraphs.extend(_split_long_paragraph(paragraph.strip(), chunk_size))

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue
        candidate = current + "\n" + paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.append(current.strip())
        overlap = current[-chunk_overlap:].strip() if chunk_overlap > 0 else ""
        current = f"{overlap}\n{paragraph}".strip() if overlap else paragraph
    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


class KnowledgePipeline:
    """
    知识库构建管道

    Pipeline:
    1. crawl - 从数据源收集文档
    2. chunk - 文档分块
    3. index - 构建索引 (TF-IDF + 可选 ChromaDB)

    Usage:
        pipeline = KnowledgePipeline(config)

        # 执行完整流程
        stats = await pipeline.build_all()

        # 分步执行
        docs = await pipeline.crawl()
        chunks = pipeline.chunk()
        stats = await pipeline.build_index()
    """

    def __init__(self, config: Optional[RAGConfig | dict] = None):
        """
        初始化管道

        Args:
            config: RAGConfig 对象或配置字典
        """
        if config is None:
            config = {}

        if isinstance(config, dict):
            self.config = load_rag_config_from_dict(config)
        else:
            self.config = config

        # 确保数据目录存在
        self.config.paths.raw_documents.parent.mkdir(parents=True, exist_ok=True)
        self.config.paths.processed_documents.parent.mkdir(parents=True, exist_ok=True)
        self.config.paths.chunks.parent.mkdir(parents=True, exist_ok=True)
        self.config.paths.index_dir.mkdir(parents=True, exist_ok=True)

    async def crawl(self) -> list[dict]:
        """
        爬取文档

        Returns:
            文档字典列表
        """
        # 从配置的数据源爬取
        documents = await self._collect_documents()

        # 保存原始文档
        write_jsonl(
            self.config.paths.raw_documents,
            [doc.to_dict() for doc in documents]
        )

        # 同时保存处理后的文档（当前版本不做额外处理）
        write_jsonl(
            self.config.paths.processed_documents,
            [doc.to_dict() for doc in documents]
        )

        return [doc.to_dict() for doc in documents]

    async def _collect_documents(self) -> list[KnowledgeDocument]:
        """
        收集文档（从配置的数据源）

        Returns:
            KnowledgeDocument 列表
        """
        return await asyncio.to_thread(collect_documents, self.config)

    def chunk(self) -> list[KnowledgeChunk]:
        """
        文档分块

        Returns:
            KnowledgeChunk 列表
        """
        rows = read_jsonl(self.config.paths.processed_documents)
        chunks: list[KnowledgeChunk] = []

        for row in rows:
            text_chunks = chunk_text(
                row["content"],
                chunk_size=self.config.index.chunk_size,
                chunk_overlap=self.config.index.chunk_overlap,
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

        # 保存分块
        write_jsonl(
            self.config.paths.chunks,
            [chunk.to_dict() for chunk in chunks]
        )

        return chunks

    async def build_index(self, backend: Optional[str] = None) -> dict:
        """
        构建索引

        Args:
            backend: 索引类型 (tfidf, sentence-transformer, hybrid)

        Returns:
            统计信息字典
        """
        chosen_backend = backend or self.config.index.backend

        rows = read_jsonl(self.config.paths.chunks)
        chunks = [KnowledgeChunk.from_dict(row) for row in rows]

        if not chunks:
            return {
                "chunks": 0,
                "index_dir": str(self.config.paths.index_dir),
                "status": "no_chunks",
            }

        # 构建 TF-IDF 索引
        index = SimilarityIndex.build(
            chunks,
            backend=chosen_backend if chosen_backend != "hybrid" else "tfidf",
            dense_model=self.config.index.dense_model,
        )
        index.save(self.config.paths.index_dir)

        # 同时添加到 ChromaDB（如果启用）
        chromadb_stats = {}
        if chosen_backend in ("hybrid", "sentence-transformer"):
            chromadb_stats = await self._build_chromadb_index(chunks)

        return {
            "chunks": len(chunks),
            "index_dir": str(self.config.paths.index_dir),
            "backend": chosen_backend,
            **chromadb_stats,
        }

    async def _build_chromadb_index(self, chunks: list[KnowledgeChunk]) -> dict:
        """
        构建 ChromaDB 索引

        Args:
            chunks: 知识片段列表

        Returns:
            统计信息
        """
        try:
            from src.brain.rag.vector_store import ChromaVectorStore, VectorDocument

            store = ChromaVectorStore(
                collection_name="fraud_cases",
                persist_directory=str(self.config.paths.index_dir / "chromadb"),
                embedding_model=self.config.index.dense_model,
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

            await store.add_documents(documents)

            return {
                "chromadb_status": "success",
                "chromadb_count": len(documents),
                "embedding_model": self.config.index.dense_model,
            }

        except Exception as e:
            return {
                "chromadb_status": "failed",
                "chromadb_error": str(e),
                "embedding_model": self.config.index.dense_model,
            }

    async def build_all(self, backend: Optional[str] = None) -> dict:
        """
        执行完整构建流程

        Args:
            backend: 索引类型

        Returns:
            完整统计信息
        """
        docs = await self.crawl()
        chunks = self.chunk()
        index_stats = await self.build_index(backend=backend)

        return {
            "documents": len(docs),
            "chunks": len(chunks),
            **index_stats,
        }

    def load_index(self) -> SimilarityIndex:
        """
        加载已构建的索引

        Returns:
            SimilarityIndex 实例
        """
        return SimilarityIndex.load(self.config.paths.index_dir)

    def get_stats(self) -> dict:
        """
        获取管道统计信息

        Returns:
            统计信息字典
        """
        return {
            "config": {
                "backend": self.config.index.backend,
                "chunk_size": self.config.index.chunk_size,
                "chunk_overlap": self.config.index.chunk_overlap,
            },
            "paths": {
                "raw_documents": str(self.config.paths.raw_documents),
                "chunks": str(self.config.paths.chunks),
                "index_dir": str(self.config.paths.index_dir),
            },
            "data": {
                "documents": len(read_jsonl(self.config.paths.raw_documents)),
                "chunks": len(read_jsonl(self.config.paths.chunks)),
            },
        }
