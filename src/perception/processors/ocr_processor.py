"""
OCR processor for image and video frame text extraction.
Uses PaddleOCR for Chinese text recognition.
"""
import asyncio
import os
from pathlib import Path
from typing import List, Optional

from src.core.models import MediaFile, MediaType, PerceptionResult, OCRResult, FakeAnalysis
from src.core.utils import run_in_threadpool, is_url
from src.perception.interfaces.base_processor import BaseProcessor
from src.perception.models.perception_models import ProcessorConfig


class OCRProcessor(BaseProcessor):
    """
    OCR processor using PaddleOCR.

    Supports images and video frames for text extraction.
    """

    def __init__(self, config: Optional[ProcessorConfig] = None):
        super().__init__("ocr_processor")
        self.config = config or ProcessorConfig()
        self._ocr_processor = None

    @property
    def supported_types(self) -> List[str]:
        return ["image", "video"]

    async def _load_models(self) -> None:
        """Load PaddleOCR model."""
        try:
            # Import here to avoid loading at module level
            import sys
            project_root = Path(__file__).parent.parent.parent.parent
            multimodal_path = project_root / "multimodal_input"
            if str(multimodal_path) not in sys.path:
                sys.path.insert(0, str(multimodal_path))

            from ocr.ocr_async_processor import AsyncKeyframeOCRProcessor

            self._ocr_processor = AsyncKeyframeOCRProcessor(
                use_angle_cls=self.config.ocr_use_angle_cls,
                lang=self.config.ocr_lang,
            )
        except Exception as e:
            print(f"[错误] OCR模型加载失败: {e}")
            raise

    async def process(
        self,
        media_file: MediaFile,
        context: Optional[dict] = None,
    ) -> PerceptionResult:
        """
        Process image or video for OCR.

        Args:
            media_file: Image or video file
            context: Processing context

        Returns:
            PerceptionResult with OCR results
        """
        await self.initialize()

        file_path = media_file.url

        # Handle URL downloads if needed
        if is_url(file_path):
            # TODO: Download and cache
            return PerceptionResult(
                text_content="",
                source_media=media_file,
                metadata={"error": "URL not supported yet"},
            )

        try:
            if media_file.type == MediaType.IMAGE:
                # Process single image
                ocr_result = await self._process_image(file_path)
            else:  # Video
                # Process video - extract keyframes first
                ocr_result = await self._process_video(file_path, context)

            return ocr_result

        except Exception as e:
            print(f"[错误] OCR处理失败: {e}")
            return PerceptionResult(
                text_content="",
                source_media=media_file,
                metadata={"error": str(e)},
            )

    async def _process_image(self, image_path: str) -> PerceptionResult:
        """Process a single image."""
        result = await self._ocr_processor.process_keyframes([image_path])

        # Extract OCR results
        ocr_results = []
        texts = []

        if "details" in result:
            for item in result["details"]:
                if item.get("confidence", 0) > 0.5:
                    ocr_results.append(OCRResult(
                        text=item.get("text", ""),
                        confidence=item.get("confidence", 0),
                        bbox=item.get("bbox"),
                    ))
                    texts.append(item["text"])

        summary = result.get("summary_texts", [])
        text_content = " ".join(summary) if summary else " ".join(texts)

        return PerceptionResult(
            text_content=text_content,
            ocr_results=ocr_results,
            source_media=MediaFile(type=MediaType.IMAGE, url=image_path),
        )

    async def _process_video(
        self,
        video_path: str,
        context: Optional[dict],
    ) -> PerceptionResult:
        """Process video by extracting keyframes."""
        task_id = context.get("task_id", "default") if context else "default"

        # Import keyframe extractor
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.parent
        multimodal_path = project_root / "multimodal_input"
        if str(multimodal_path) not in sys.path:
            sys.path.insert(0, str(multimodal_path))

        from video_module.keyframe_extractor import KeyframeExtractor

        # Create keyframe extractor
        keyframe_extractor = KeyframeExtractor(
            output_root=str(multimodal_path / "video_module" / "keyframes"),
            interval_sec=self.config.keyframe_interval,
            scene_threshold=self.config.keyframe_scene_threshold,
            max_frames=self.config.keyframe_max_frames,
        )

        # Extract keyframes
        keyframe_result = await run_in_threadpool(
            keyframe_extractor.extract,
            video_path,
            task_id,
        )

        # Get keyframe paths
        keyframe_paths = keyframe_result.frame_paths if hasattr(keyframe_result, 'frame_paths') else []

        if not keyframe_paths:
            return PerceptionResult(
                text_content="",
                source_media=MediaFile(type=MediaType.VIDEO, url=video_path),
                metadata={"keyframe_count": 0},
            )

        # Process keyframes with OCR
        ocr_result = await self._ocr_processor.process_keyframes(keyframe_paths)

        # Extract results
        ocr_results = []
        texts = []

        if "details" in ocr_result:
            for item in ocr_result["details"]:
                if item.get("confidence", 0) > 0.5:
                    ocr_results.append(OCRResult(
                        text=item.get("text", ""),
                        confidence=item.get("confidence", 0),
                        bbox=item.get("bbox"),
                    ))
                    texts.append(item["text"])

        summary = ocr_result.get("summary_texts", [])
        text_content = " ".join(summary) if summary else " ".join(texts)

        return PerceptionResult(
            text_content=text_content,
            ocr_results=ocr_results,
            source_media=MediaFile(type=MediaType.VIDEO, url=video_path),
            metadata={
                "keyframe_count": len(keyframe_paths),
                "keyframe_dir": getattr(keyframe_result, 'frame_dir', None),
            },
        )

    async def health_check(self) -> bool:
        """Check if OCR model is loaded."""
        return self._ocr_processor is not None