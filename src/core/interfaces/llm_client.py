"""
Unified LLM client for all nodes.
Eliminates duplicate LLM initialization and calling code.
"""
import os
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

from src.core.utils.json_utils import get_text_content, extract_json_from_text
from src.core.utils.multimodal_payloads import LLMUserContent


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    parsed_json: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, int]] = None
    model: str = ""


class LLMClient:
    """
    Unified LLM client for all workflow nodes.

    Eliminates duplicate:
    - Model initialization
    - Message formatting
    - JSON parsing from responses
    """

    # Default configuration
    DEFAULT_MODEL = "moonshot-v1-8k"  # Kimi default model
    DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"  # Kimi API endpoint

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        timeout: int = 30,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        # Read from env vars with defaults
        self.model_name = model or os.getenv("LLM_MODEL", self.DEFAULT_MODEL)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        # API key priority: parameter > LLM_API_KEY > MOONSHOT_API_KEY > OPENAI_API_KEY
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key not found. Please set one of: LLM_API_KEY, MOONSHOT_API_KEY, or OPENAI_API_KEY "
                "environment variable, or pass api_key parameter."
            )

        # Base URL priority: parameter > LLM_BASE_URL > default Kimi URL
        self.base_url = base_url or os.getenv("LLM_BASE_URL", self.DEFAULT_BASE_URL)

        # Initialize LangChain chat model
        self._llm = ChatOpenAI(
            model=self.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def achat(
        self,
        system_prompt: str,
        user_prompt: LLMUserContent,
        parse_json: bool = True,
        config: Optional[RunnableConfig] = None,
    ) -> LLMResponse:
        """
        Async chat completion with optional JSON parsing.

        Args:
            system_prompt: System message content
            user_prompt: User message content
            parse_json: Whether to attempt JSON parsing
            config: Optional LangChain config

        Returns:
            LLMResponse with content and optional parsed JSON
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Invoke LLM
        response = await self._llm.ainvoke(messages, config=config)
        content = get_text_content(response)

        # Parse JSON if requested
        parsed_json = None
        if parse_json:
            parsed_json = extract_json_from_text(content)

        return LLMResponse(
            content=content,
            parsed_json=parsed_json,
            model=self.model_name,
        )

    def chat(
        self,
        system_prompt: str,
        user_prompt: LLMUserContent,
        parse_json: bool = True,
        config: Optional[RunnableConfig] = None,
    ) -> LLMResponse:
        """
        Sync chat completion with optional JSON parsing.
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = self._llm.invoke(messages, config=config)
        content = get_text_content(response)

        parsed_json = None
        if parse_json:
            parsed_json = extract_json_from_text(content)

        return LLMResponse(
            content=content,
            parsed_json=parsed_json,
            model=self.model_name,
        )

    async def achat_with_history(
        self,
        messages: List[BaseMessage],
        parse_json: bool = True,
        config: Optional[RunnableConfig] = None,
    ) -> LLMResponse:
        """
        Async chat with full message history.
        """
        response = await self._llm.ainvoke(messages, config=config)
        content = get_text_content(response)

        parsed_json = None
        if parse_json:
            parsed_json = extract_json_from_text(content)

        return LLMResponse(
            content=content,
            parsed_json=parsed_json,
            model=self.model_name,
        )

    async def warmup(self, prompt: str = "仅回复OK") -> bool:
        """Trigger a lightweight request to reduce first-token latency."""
        try:
            await self.achat(
                system_prompt="你是服务预热助手，请仅返回最短确认。",
                user_prompt=prompt,
                parse_json=False,
            )
            return True
        except Exception as exc:
            print(f"[llm_warmup] {self.model_name} warmup failed: {exc}")
            return False

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "LLMClient":
        """
        Create LLMClient from configuration dict.

        Args:
            config: Dict with model, temperature, max_tokens, timeout, base_url

        Returns:
            Configured LLMClient instance
        """
        return cls(
            model=config.get("model"),
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 1500),
            timeout=config.get("timeout", 30),
            base_url=config.get("base_url"),
        )
