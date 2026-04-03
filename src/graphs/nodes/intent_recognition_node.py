"""
Intent recognition node.
"""
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from src.brain import IntentRecognizer
from src.core.interfaces import BaseNode
from src.core.models import GlobalState


class IntentRecognitionNode(BaseNode):
    """Independent node for intent, profile, and short-term memory."""

    def __init__(self, recognizer: IntentRecognizer = None):
        super().__init__("intent_recognition")
        self.recognizer = recognizer or IntentRecognizer()

    async def process(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> Dict[str, Any]:
        return await self.recognizer.analyze(state)

    def _extract_input(self, state: GlobalState) -> GlobalState:
        return state

    def _output_to_dict(self, output: Dict[str, Any]) -> Dict[str, Any]:
        return output

    def _get_fallback_output(self) -> Dict[str, Any]:
        return {
            "intent": "general_consultation",
            "short_term_memory_summary": "",
            "workflow_metadata": {},
        }
