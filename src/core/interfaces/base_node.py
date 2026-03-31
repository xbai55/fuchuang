"""
Base class for LangGraph nodes.
Provides common functionality and standardized interface.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar

from langchain_core.runnables import RunnableConfig

from src.core.models.state import GlobalState


InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class BaseNode(ABC, Generic[InputType, OutputType]):
    """
    Base class for all workflow nodes.

    Provides:
    - Standardized run interface
    - Config loading
    - Error handling
    - Logging
    """

    def __init__(self, name: str):
        self.name = name
        self._config: Dict[str, Any] = {}

    @abstractmethod
    async def process(
        self,
        state: InputType,
        config: RunnableConfig,
    ) -> OutputType:
        """
        Process the input state and return output.

        Args:
            state: Input state (typed)
            config: LangChain runnable config

        Returns:
            Output state (typed)
        """
        pass

    async def run(
        self,
        state: GlobalState,
        config: RunnableConfig,
    ) -> Dict[str, Any]:
        """
        Run the node with the full global state.

        This is the method registered with LangGraph.
        It extracts relevant input, processes, and merges output.

        Args:
            state: Full global state
            config: LangChain runnable config

        Returns:
            Dict of output fields to merge into state
        """
        try:
            # Extract typed input from global state
            typed_input = self._extract_input(state)

            # Process
            output = await self.process(typed_input, config)

            # Convert output to dict for state merging
            return self._output_to_dict(output)

        except Exception as e:
            # Log error and return safe fallback
            print(f"[错误] Node {self.name} failed: {e}")
            return self._get_fallback_output()

    @abstractmethod
    def _extract_input(self, state: GlobalState) -> InputType:
        """
        Extract typed input from global state.

        Args:
            state: Full global state

        Returns:
            Typed input for this node
        """
        pass

    @abstractmethod
    def _output_to_dict(self, output: OutputType) -> Dict[str, Any]:
        """
        Convert typed output to dict for state merging.

        Args:
            output: Typed output

        Returns:
            Dict of state fields
        """
        pass

    @abstractmethod
    def _get_fallback_output(self) -> Dict[str, Any]:
        """
        Get safe fallback output when processing fails.

        Returns:
            Dict with default/safe values
        """
        pass

    def load_config(self, config: RunnableConfig) -> Dict[str, Any]:
        """
        Load node-specific configuration.

        Args:
            config: Runnable config

        Returns:
            Node configuration dict
        """
        metadata = config.get("metadata", {})
        return metadata.get(f"{self.name}_config", {})
