"""
Knowledge search node with RAG.
Replaces the placeholder implementation with real RAG.
"""
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from src.core.interfaces import BaseNode
from src.core.models import GlobalState
from brain import KnowledgeSearchService


class KnowledgeSearchNode(BaseNode):
    """
    Graph node for knowledge retrieval using RAG.

    Input: GlobalState with perception_results
    Output: Updated GlobalState with similar_cases and legal_basis

    This replaces the 18-line placeholder implementation with
    a full RAG-based search.
    """

    def __init__(self, knowledge_service: KnowledgeSearchService = None):
        super().__init__("knowledge_search")
        self.service = knowledge_service or KnowledgeSearchService()

    async def process(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> Dict[str, Any]:
        """
        Search for similar cases and legal basis.

        Args:
            state: Global state
            config: Runnable config

        Returns:
            Dict with similar_cases and legal_basis
        """
        # Perform search
        similar_cases, legal_basis = await self.service.search(state)

        return {
            "similar_cases": similar_cases,
            "legal_basis": legal_basis,
        }

    def _extract_input(self, state: GlobalState) -> GlobalState:
        return state

    def _output_to_dict(self, output: Dict[str, Any]) -> Dict[str, Any]:
        return output

    def _get_fallback_output(self) -> Dict[str, Any]:
        """Return default values on failure."""
        return {
            "similar_cases": [],
            "legal_basis": [
                "《中华人民共和国刑法》第二百六十六条：诈骗罪",
                "《中华人民共和国反电信网络诈骗法》",
            ],
        }
