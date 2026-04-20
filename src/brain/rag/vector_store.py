"""
Vector store implementations for RAG.
Supports ChromaDB and FAISS backends.
"""
import hashlib
import json
import sqlite3
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class VectorDocument:
    """Document with embedding and metadata."""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = None


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    async def add_documents(self, documents: List[VectorDocument]) -> None:
        """Add documents to the store."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict] = None,
    ) -> List[VectorDocument]:
        """Search for similar documents."""
        pass

    @abstractmethod
    async def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        pass


class LocalHashEmbeddingFunction:
    """Small deterministic embedding function with no network or model dependency."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    @staticmethod
    def name() -> str:
        return "local-hash"

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "LocalHashEmbeddingFunction":
        return LocalHashEmbeddingFunction(dimensions=int(config.get("dimensions", 384)))

    def get_config(self) -> Dict[str, Any]:
        return {"dimensions": self.dimensions}

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> List[str]:
        return ["cosine", "l2", "ip"]

    def __call__(self, input) -> List[List[float]]:
        return [self._embed(str(text or "")).tolist() for text in input]

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        tokens = self._tokens(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign

        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector

    @staticmethod
    def _tokens(text: str) -> List[str]:
        compact = "".join(ch.lower() for ch in text if not ch.isspace())
        tokens: List[str] = []
        for n in (1, 2, 3):
            if len(compact) >= n:
                tokens.extend(compact[i : i + n] for i in range(len(compact) - n + 1))
        return tokens


class ChromaVectorStore(VectorStore):
    """
    ChromaDB-based vector store.

    Features:
    - Persistent storage
    - Embedding-based search
    - Metadata filtering
    """

    def __init__(
        self,
        collection_name: str = "fraud_cases",
        persist_directory: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory or "./data/vector_store"
        self.embedding_model = embedding_model or "local-hash"

        self._client = None
        self._collection = None
        self._embedding_func = None
        self._local_conn: sqlite3.Connection | None = None

    async def _initialize(self):
        """Lazy initialization."""
        if self._client is not None or self._local_conn is not None:
            return

        if self.embedding_model in {"local-hash", "hash", ""}:
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            self._embedding_func = LocalHashEmbeddingFunction()
            self._local_conn = sqlite3.connect(Path(self.persist_directory) / "local_vectors.sqlite3")
            self._local_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embedding TEXT NOT NULL
                )
                """
            )
            self._local_conn.commit()
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            # Create persistent client
            self._client = chromadb.PersistentClient(path=self.persist_directory)

            if self.embedding_model in {"chroma-default-onnx", "default"}:
                self._embedding_func = embedding_functions.DefaultEmbeddingFunction()
            else:
                # Local sentence-transformers model. This requires a healthy
                # PyTorch install and a locally cached/downloadable model.
                self._embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.embedding_model,
                )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_func,
            )

        except ImportError:
            print("[警告] ChromaDB not installed, using mock implementation")
            self._client = None

    async def add_documents(self, documents: List[VectorDocument]) -> None:
        """Add documents to ChromaDB."""
        await self._initialize()

        if self._collection is None:
            if self._local_conn is None:
                raise RuntimeError("Vector store not initialized")

            rows = []
            embeddings = self._embedding_func([doc.content for doc in documents])
            for doc, embedding in zip(documents, embeddings):
                rows.append(
                    (
                        doc.id,
                        doc.content,
                        json.dumps(doc.metadata or {}, ensure_ascii=False),
                        json.dumps(embedding),
                    )
                )
            self._local_conn.executemany(
                """
                INSERT INTO vectors(id, content, metadata, embedding)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content=excluded.content,
                    metadata=excluded.metadata,
                    embedding=excluded.embedding
                """,
                rows,
            )
            self._local_conn.commit()
            return

        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata or {} for doc in documents]

        write_method = getattr(self._collection, "upsert", None) or self._collection.add
        write_method(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
        )

    async def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict] = None,
    ) -> List[VectorDocument]:
        """Search for similar documents."""
        await self._initialize()

        if self._collection is None:
            if self._local_conn is None:
                return []

            query_embedding = np.asarray(self._embedding_func([query])[0], dtype=np.float32)
            rows = self._local_conn.execute(
                "SELECT id, content, metadata, embedding FROM vectors"
            ).fetchall()

            scored: list[tuple[float, VectorDocument]] = []
            for doc_id, content, metadata_raw, embedding_raw in rows:
                metadata = json.loads(metadata_raw or "{}")
                if filter_dict and any(metadata.get(k) != v for k, v in filter_dict.items()):
                    continue
                embedding = np.asarray(json.loads(embedding_raw), dtype=np.float32)
                score = float(np.dot(query_embedding, embedding))
                scored.append(
                    (
                        score,
                        VectorDocument(id=doc_id, content=content, metadata=metadata),
                    )
                )

            scored.sort(key=lambda item: item[0], reverse=True)
            return [doc for _, doc in scored[:k]]

        results = self._collection.query(
            query_texts=[query],
            n_results=k,
            where=filter_dict,
        )

        documents = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                documents.append(VectorDocument(
                    id=doc_id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                ))

        return documents

    async def delete(self, doc_id: str) -> None:
        """Delete a document."""
        await self._initialize()

        if self._local_conn is not None:
            self._local_conn.execute("DELETE FROM vectors WHERE id = ?", (doc_id,))
            self._local_conn.commit()
        elif self._collection is not None:
            self._collection.delete(ids=[doc_id])

    async def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        await self._initialize()

        if self._local_conn is not None:
            count = self._local_conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            return {
                "count": count,
                "collection": self.collection_name,
                "persist_directory": self.persist_directory,
                "backend": "sqlite-local-hash",
                "embedding_model": self.embedding_model,
            }

        if self._collection is None:
            return {"count": 0, "status": "not_initialized"}

        count = self._collection.count()
        return {
            "count": count,
            "collection": self.collection_name,
            "persist_directory": self.persist_directory,
        }
