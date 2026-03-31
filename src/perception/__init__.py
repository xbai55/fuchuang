"""
Perception layer for multi-modal input processing.
Handles OCR, Audio, Video, and Text inputs with unified interface.
"""
from src.perception.interfaces.base_processor import BaseProcessor
from src.perception.models.perception_models import ProcessorConfig, ProcessingContext
from src.perception.manager import PerceptionManager

__all__ = [
    "BaseProcessor",
    "ProcessorConfig",
    "ProcessingContext",
    "PerceptionManager",
]
