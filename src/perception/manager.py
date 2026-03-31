"""
Perception Manager - Unified entry point for multi-modal processing.

This module provides the main interface for processing various media types
(text, audio, image, video) with parallel execution and unified output.
"""
import asyncio
from typing import Dict, List, Optional, Type

from src.core.models import MediaFile, MediaType, PerceptionResult
from src.core.utils.async_utils import AsyncTaskGroup
from src.perception.interfaces.base_processor import BaseProcessor
from src.perception.models.perception_models import ProcessorConfig, ProcessingContext
from src.perception.processors import (
    TextProcessor,
    OCRProcessor,
    AudioProcessor,
    VideoProcessor,
)


class PerceptionManager:
    """
    Unified entry point for multi-modal perception processing.

    Features:
    - Parallel processing of multiple media files
    - Automatic processor selection by media type
    - Model pooling for efficient resource usage
    - Unified PerceptionResult output

    Example:
        manager = PerceptionManager()
        results = await manager.process([
            MediaFile(type=MediaType.AUDIO, url="/path/to/audio.wav"),
            MediaFile(type=MediaType.IMAGE, url="/path/to/image.jpg"),
        ])
    """

    def __init__(self, config: Optional[ProcessorConfig] = None):
        """
        Initialize the perception manager.

        Args:
            config: Optional processor configuration
        """
        self.config = config or ProcessorConfig()

        # Initialize processors
        self._processors: Dict[str, BaseProcessor] = {
            "text": TextProcessor(),
            "audio": AudioProcessor(self.config),
            "image": OCRProcessor(self.config),
            "video": VideoProcessor(self.config),
        }

        # Track initialization state
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all processors."""
        if self._initialized:
            return

        # Initialize all processors in parallel
        init_tasks = [
            processor.initialize()
            for processor in self._processors.values()
        ]
        await asyncio.gather(*init_tasks, return_exceptions=True)

        self._initialized = True
        print("✅ 感知层所有处理器初始化完成")

    async def process(
        self,
        media_files: List[MediaFile],
        context: Optional[ProcessingContext] = None,
    ) -> List[PerceptionResult]:
        """
        Process multiple media files in parallel.

        Args:
            media_files: List of media files to process
            context: Optional processing context

        Returns:
            List of PerceptionResult, one per input file
        """
        await self.initialize()

        if not media_files:
            return []

        # Convert context to dict for processors
        context_dict = context.model_dump() if context else {}

        # Create processing tasks
        tasks = []
        for media_file in media_files:
            processor = self._get_processor(media_file.type)
            if processor:
                task = self._process_with_error_handling(
                    processor, media_file, context_dict
                )
                tasks.append(task)
            else:
                # No processor available, return empty result
                tasks.append(asyncio.create_task(
                    self._create_empty_result(media_file)
                ))

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"[错误] 处理失败 [{media_files[i].type}]: {result}")
                processed_results.append(
                    PerceptionResult(
                        text_content="",
                        source_media=media_files[i],
                        metadata={"error": str(result)},
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def process_single(
        self,
        media_file: MediaFile,
        context: Optional[ProcessingContext] = None,
    ) -> PerceptionResult:
        """
        Process a single media file.

        Args:
            media_file: Media file to process
            context: Optional processing context

        Returns:
            PerceptionResult
        """
        results = await self.process([media_file], context)
        return results[0] if results else PerceptionResult(text_content="")

    def _get_processor(self, media_type: MediaType) -> Optional[BaseProcessor]:
        """
        Get the appropriate processor for a media type.

        Args:
            media_type: Type of media

        Returns:
            Processor instance or None
        """
        return self._processors.get(media_type.value)

    async def _process_with_error_handling(
        self,
        processor: BaseProcessor,
        media_file: MediaFile,
        context: dict,
    ) -> PerceptionResult:
        """
        Process with error handling and timeout.

        Args:
            processor: Processor to use
            media_file: Media file to process
            context: Processing context

        Returns:
            PerceptionResult
        """
        try:
            # Process with 30 second timeout
            return await asyncio.wait_for(
                processor.process(media_file, context),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            print(f"[警告] 处理超时 [{media_file.type}]: {media_file.url}")
            return PerceptionResult(
                text_content="",
                source_media=media_file,
                metadata={"error": "Processing timeout"},
            )
        except Exception as e:
            print(f"[错误] 处理异常 [{media_file.type}]: {e}")
            raise

    async def _create_empty_result(
        self,
        media_file: MediaFile,
    ) -> PerceptionResult:
        """Create an empty result for unsupported types."""
        return PerceptionResult(
            text_content="",
            source_media=media_file,
            metadata={"error": f"Unsupported media type: {media_file.type}"},
        )

    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all processors.

        Returns:
            Dict mapping processor name to health status
        """
        health = {}
        for name, processor in self._processors.items():
            try:
                health[name] = await processor.health_check()
            except Exception as e:
                print(f"[错误] 健康检查失败 [{name}]: {e}")
                health[name] = False
        return health

    def get_supported_types(self) -> List[str]:
        """
        Get list of supported media types.

        Returns:
            List of supported type strings
        """
        return list(self._processors.keys())
