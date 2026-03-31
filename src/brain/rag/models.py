"""
融合 RAG 数据模型
兼容现有 RetrievedCase 和 RAG 的 KnowledgeChunk
从 rag/src/fraud_rag/models.py 迁移并扩展
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional


@dataclass(slots=True)
class ImageAsset:
    """图片资源 - 从 RAG 迁移"""
    url: str
    title: str = ""
    caption: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageAsset":
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            caption=data.get("caption", ""),
        )


@dataclass(slots=True)
class KnowledgeDocument:
    """知识文档 - 从 RAG 迁移"""
    doc_id: str
    url: str
    canonical_url: str
    source_site: str
    category: str  # law, case, photo_type, image_article
    title: str
    content: str
    summary: str = ""
    published_at: Optional[str] = None
    source_name: Optional[str] = None
    subtype: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    images: List[ImageAsset] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["images"] = [image.to_dict() for image in self.images]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeDocument":
        return cls(
            doc_id=data["doc_id"],
            url=data["url"],
            canonical_url=data.get("canonical_url", data["url"]),
            source_site=data.get("source_site", ""),
            category=data["category"],
            title=data["title"],
            content=data["content"],
            summary=data.get("summary", ""),
            published_at=data.get("published_at"),
            source_name=data.get("source_name"),
            subtype=data.get("subtype"),
            tags=list(data.get("tags", [])),
            images=[ImageAsset.from_dict(item) for item in data.get("images", [])],
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class KnowledgeChunk:
    """知识片段 - 从 RAG 迁移"""
    chunk_id: str
    doc_id: str
    category: str  # law, case, photo_type, image_article
    subtype: Optional[str]
    title: str
    text: str
    source_url: str
    source_site: str
    published_at: Optional[str] = None
    source_name: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeChunk":
        return cls(
            chunk_id=data["chunk_id"],
            doc_id=data["doc_id"],
            category=data["category"],
            subtype=data.get("subtype"),
            title=data["title"],
            text=data["text"],
            source_url=data["source_url"],
            source_site=data.get("source_site", ""),
            published_at=data.get("published_at"),
            source_name=data.get("source_name"),
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class SearchHit:
    """检索结果 - 从 RAG 迁移"""
    score: float
    chunk: KnowledgeChunk

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(float(self.score), 6),
            "chunk": self.chunk.to_dict(),
        }


@dataclass
class RiskAssessmentResult:
    """风险评估结果 - 从 detector 迁移"""
    risk_level: str  # low, medium, high
    confidence: float
    matched_subtypes: List[str]
    matched_tags: List[str]
    recommendations: List[str]
    hits: List[dict]

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "matched_subtypes": self.matched_subtypes,
            "matched_tags": self.matched_tags,
            "recommendations": self.recommendations,
            "hits": self.hits,
        }


# ============ 模型转换适配器 ============

def convert_search_hit_to_retrieved_case(hit: SearchHit) -> "RetrievedCase":
    """
    将 SearchHit 转换为现有的 RetrievedCase 格式

    Args:
        hit: RAG 检索结果

    Returns:
        兼容现有接口的 RetrievedCase
    """
    from src.core.models.state import RetrievedCase

    chunk = hit.chunk
    return RetrievedCase(
        case_id=chunk.chunk_id,
        title=chunk.title,
        content=chunk.text,
        similarity=hit.score,
        source=chunk.source_site,
    )


def convert_search_hits_to_retrieved_cases(hits: List[SearchHit]) -> List["RetrievedCase"]:
    """
    批量转换 SearchHit 列表为 RetrievedCase 列表

    Args:
        hits: RAG 检索结果列表

    Returns:
        RetrievedCase 列表
    """
    return [convert_search_hit_to_retrieved_case(hit) for hit in hits]


def create_search_hit_from_retrieved_case(
    case: "RetrievedCase",
    category: str = "case",
    subtype: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> SearchHit:
    """
    将 RetrievedCase 转换为 SearchHit

    Args:
        case: 现有案例格式
        category: 知识类别
        subtype: 子类型
        tags: 标签列表

    Returns:
        SearchHit 对象
    """
    chunk = KnowledgeChunk(
        chunk_id=case.case_id,
        doc_id=case.case_id,
        category=category,
        subtype=subtype,
        title=case.title,
        text=case.content,
        source_url=case.source,
        source_site=case.source,
        tags=tags or [],
    )
    return SearchHit(score=case.similarity, chunk=chunk)
