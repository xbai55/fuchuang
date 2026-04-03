"""
Base interface for all media processors.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.models import MediaFile, PerceptionResult


class BaseProcessor(ABC):
    """
    Abstract base class for all media processors.

    All processors (OCR, Audio, Video, Text) must implement this interface
    to ensure consistent behavior across the perception layer.
    """

    def __init__(self, name: str):
        self.name = name
        self._initialized = False
        self._init_lock = asyncio.Lock()

    @property
    @abstractmethod
    def supported_types(self) -> List[str]:
        """
        Return the list of media types this processor supports.

        Returns:
            List of MediaType values (e.g., ["image", "video"])
        """
        pass

    @abstractmethod
    async def process(
        self,
        media_file: MediaFile,
        context: Optional[dict] = None,
    ) -> PerceptionResult:
        """
        Process a media file and return standardized perception result.

        Args:
            media_file: The media file to process
            context: Optional processing context (e.g., task_id, user_role)

        Returns:
            Standardized PerceptionResult
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the processor is healthy and ready.

        Returns:
            True if healthy, False otherwise
        """
        pass

    async def initialize(self) -> None:
        """
        Initialize the processor (load models, etc.).

        This is called lazily before the first process() call.
        """
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return
            await self._load_models()
            self._initialized = True

    @abstractmethod
    async def _load_models(self) -> None:
        """
        Load required models. Called by initialize().
        """
        pass

    def can_process(self, media_file: MediaFile) -> bool:
        """
        Check if this processor can handle the given media file.

        Args:
            media_file: Media file to check

        Returns:
            True if can process, False otherwise
        """
        return media_file.type.value in self.supported_types
