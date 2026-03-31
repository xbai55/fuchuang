"""
RAG (Retrieval-Augmented Generation) module
融合 TF-IDF 和 ChromaDB 的统一检索方案
"""
from src.brain.rag.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    SearchHit,
    RiskAssessmentResult,
    ImageAsset,
    convert_search_hit_to_retrieved_case,
    convert_search_hits_to_retrieved_cases,
    create_search_hit_from_retrieved_case,
)
from src.brain.rag.config import RAGConfig, load_rag_config, load_rag_config_from_dict
from src.brain.rag.indexer import SimilarityIndex
from src.brain.rag.detector import RiskDetector, SUBTYPE_ADVICE
from src.brain.rag.retriever import FraudCaseRetriever
from src.brain.rag.pipeline import KnowledgePipeline
from src.brain.rag.vector_store import VectorStore, ChromaVectorStore, VectorDocument

__all__ = [
    # Models
    "KnowledgeChunk",
    "KnowledgeDocument",
    "SearchHit",
    "RiskAssessmentResult",
    "ImageAsset",
    # Config
    "RAGConfig",
    "load_rag_config",
    "load_rag_config_from_dict",
    # Core Components
    "SimilarityIndex",
    "RiskDetector",
    "FraudCaseRetriever",
    "KnowledgePipeline",
    # Vector Store
    "VectorStore",
    "ChromaVectorStore",
    "VectorDocument",
    # Utilities
    "SUBTYPE_ADVICE",
    "convert_search_hit_to_retrieved_case",
    "convert_search_hits_to_retrieved_cases",
    "create_search_hit_from_retrieved_case",
]
