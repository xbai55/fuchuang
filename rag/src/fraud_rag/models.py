from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ImageAsset:
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
    doc_id: str
    url: str
    canonical_url: str
    source_site: str
    category: str
    title: str
    content: str
    summary: str = ""
    published_at: str | None = None
    source_name: str | None = None
    subtype: str | None = None
    tags: list[str] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
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
    chunk_id: str
    doc_id: str
    category: str
    subtype: str | None
    title: str
    text: str
    source_url: str
    source_site: str
    published_at: str | None = None
    source_name: str | None = None
    tags: list[str] = field(default_factory=list)
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
    score: float
    chunk: KnowledgeChunk

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(float(self.score), 6),
            "chunk": self.chunk.to_dict(),
        }
