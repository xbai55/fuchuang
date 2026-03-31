"""
Vector store implementations for RAG.
Supports ChromaDB and FAISS backends.
"""
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


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
        self.embedding_model = embedding_model or "text-embedding-3-small"

        self._client = None
        self._collection = None
        self._embedding_func = None

    async def _initialize(self):
        """Lazy initialization."""
        if self._client is not None:
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            # Create persistent client
            self._client = chromadb.PersistentClient(path=self.persist_directory)

            # Create embedding function
            self._embedding_func = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
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

        if not self._collection:
            print("[警告] Vector store not initialized")
            return

        ids = [doc.id for doc in documents]
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata or {} for doc in documents]

        self._collection.add(
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

        if not self._collection:
            return []

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

        if self._collection:
            self._collection.delete(ids=[doc_id])

    async def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        await self._initialize()

        if not self._collection:
            return {"count": 0, "status": "not_initialized"}

        count = self._collection.count()
        return {
            "count": count,
            "collection": self.collection_name,
            "persist_directory": self.persist_directory,
        }