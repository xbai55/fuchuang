"""
Core interfaces and base classes.
"""
from src.core.interfaces.llm_client import LLMClient, LLMResponse
from src.core.interfaces.base_node import BaseNode

__all__ = ["LLMClient", "LLMResponse", "BaseNode"]
