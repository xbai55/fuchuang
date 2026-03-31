"""
Text processor for direct text input.
Simple pass-through with basic cleaning.
"""
from typing import List, Optional

from src.core.models import MediaFile, MediaType, PerceptionResult
from src.perception.interfaces.base_processor import BaseProcessor


class TextProcessor(BaseProcessor):
    """
    Processor for text input.

    Performs basic text cleaning and normalization.
    No model loading required.
    """

    def __init__(self):
        super().__init__("text_processor")

    @property
    def supported_types(self) -> List[str]:
        return ["text"]

    async def process(
        self,
        media_file: MediaFile,
        context: Optional[dict] = None,
    ) -> PerceptionResult:
        """
        Process text input.

        Args:
            media_file: Media file with text content
            context: Processing context

        Returns:
            PerceptionResult with text content
        """
        # Get text content from URL (for text type, URL contains the text)
        text_content = media_file.url

        # Basic cleaning
        text_content = self._clean_text(text_content)

        return PerceptionResult(
            text_content=text_content,
            source_media=media_file,
        )

    async def health_check(self) -> bool:
        """Always healthy - no models to load."""
        return True

    async def _load_models(self) -> None:
        """No models to load."""
        pass

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Strip whitespace
        text = text.strip()

        # Remove excessive newlines
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text