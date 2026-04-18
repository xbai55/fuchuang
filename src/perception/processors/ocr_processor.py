"""
OCR processor for image and video frame text extraction.
Uses PaddleOCR for Chinese text recognition.
"""
import asyncio
import os
from time import perf_counter
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
        self._fake_analyzer = None
        self._fake_model_error: Optional[str] = None

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
            from video_module.video_inference import get_shared_video_fake_analyzer

            self._ocr_processor = AsyncKeyframeOCRProcessor(
                use_angle_cls=self.config.ocr_use_angle_cls,
                lang=self.config.ocr_lang,
            )

            # Reuse the same visual fake analyzer used by video processing.
            model_path = self.config.video_model_path
            if not model_path:
                model_path = str(multimodal_path / "video_module" / "weights" / "final_model.pth")

            try:
                self._fake_analyzer = get_shared_video_fake_analyzer(
                    weight_path=model_path,
                    snap_timestamp_sec=self.config.video_snap_timestamp,
                )
                self._fake_model_error = None
            except Exception as exc:
                self._fake_analyzer = None
                self._fake_model_error = str(exc)
                print(f"[警告] 图片AI率检测模型初始化失败，将仅执行OCR: {exc}")
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
                ocr_result = await self._process_image(file_path, context)
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

    async def _process_image(
        self,
        image_path: str,
        context: Optional[dict] = None,
    ) -> PerceptionResult:
        """Process a single image."""

        metadata: dict = {}
        image_received_at = perf_counter()
        if self._fake_model_error:
            metadata["fake_model_error"] = self._fake_model_error

        context_dict = context if isinstance(context, dict) else {}
        context_metadata = context_dict.get("metadata") if isinstance(context_dict.get("metadata"), dict) else {}
        prefer_ai_rate = bool(context_metadata.get("prefer_ai_rate_early_warning", False))

        skip_threshold_raw = context_metadata.get("image_ai_ocr_skip_threshold", 0.74)
        try:
            skip_threshold = float(skip_threshold_raw)
        except (TypeError, ValueError):
            skip_threshold = 0.74
        skip_threshold = max(0.5, min(0.99, skip_threshold))

        # Extract OCR results
        ocr_results = []
        texts = []

        fake_analysis = None
        if self._fake_analyzer is not None:
            fake_started_at = perf_counter()
            fake_prob = await run_in_threadpool(
                self._fake_analyzer.predict_image_path,
                image_path,
            )
            metadata["image_fake_analysis_ms"] = round((perf_counter() - fake_started_at) * 1000, 2)
            fake_analysis = FakeAnalysis(
                is_fake=bool(fake_prob > 0.6),
                fake_probability=float(fake_prob),
                model_used="EfficientNet-B0",
                details={
                    "source": "video_model_reuse_for_image",
                    "snap_timestamp": self.config.video_snap_timestamp,
                },
            )

        source_media = MediaFile(type=MediaType.IMAGE, url=image_path)

        # AI-rate-priority fast path for earlier warning responsiveness.
        if (
            prefer_ai_rate
            and fake_analysis is not None
            and float(fake_analysis.fake_probability) >= skip_threshold
        ):
            metadata.update(
                {
                    "ai_rate_priority_mode": True,
                    "ocr_skipped_due_to_high_ai_rate": True,
                    "ocr_skip_threshold": skip_threshold,
                    "ocr_total_ms": round((perf_counter() - image_received_at) * 1000, 2),
                    "ocr_text_length": 0,
                }
            )
            return PerceptionResult(
                text_content="",
                fake_analysis=fake_analysis,
                ocr_results=[],
                metadata=metadata,
                source_media=source_media,
            )

        ocr_started_at = perf_counter()
        result = await self._ocr_processor.process_keyframes([image_path])
        metadata["ocr_engine_ms"] = round((perf_counter() - ocr_started_at) * 1000, 2)

        for item in self._extract_text_items(result):
            confidence = float(item.get("confidence", 0))
            if confidence > 0.5:
                text_value = str(item.get("text", ""))
                ocr_results.append(OCRResult(
                    text=text_value,
                    confidence=confidence,
                    bbox=self._normalize_bbox(item.get("bbox")),
                ))
                if text_value:
                    texts.append(text_value)

        summary = self._extract_summary_texts(result)
        text_content = " ".join(summary) if summary else " ".join(texts)

        if prefer_ai_rate:
            metadata["ai_rate_priority_mode"] = True

        metadata["ocr_total_ms"] = round((perf_counter() - image_received_at) * 1000, 2)
        metadata["ocr_text_length"] = len(text_content)

        return PerceptionResult(
            text_content=text_content,
            fake_analysis=fake_analysis,
            ocr_results=ocr_results,
            metadata=metadata,
            source_media=source_media,
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

        for item in self._extract_text_items(ocr_result):
            confidence = float(item.get("confidence", 0))
            if confidence > 0.5:
                text_value = str(item.get("text", ""))
                ocr_results.append(OCRResult(
                    text=text_value,
                    confidence=confidence,
                    bbox=self._normalize_bbox(item.get("bbox")),
                ))
                if text_value:
                    texts.append(text_value)

        summary = self._extract_summary_texts(ocr_result)
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

    def _extract_text_items(self, ocr_result: dict) -> List[dict]:
        """Extract normalized OCR items from legacy/new payload formats."""
        if not isinstance(ocr_result, dict):
            return []

        if isinstance(ocr_result.get("details"), list):
            return [item for item in ocr_result["details"] if isinstance(item, dict)]

        frames_results = ocr_result.get("frames_results")
        if not isinstance(frames_results, dict):
            return []

        items: List[dict] = []
        for frame in frames_results.values():
            if not isinstance(frame, dict):
                continue
            frame_texts = frame.get("texts")
            if not isinstance(frame_texts, list):
                continue
            for item in frame_texts:
                if isinstance(item, dict):
                    items.append(item)

        return items

    def _extract_summary_texts(self, ocr_result: dict) -> List[str]:
        if not isinstance(ocr_result, dict):
            return []

        summary = ocr_result.get("summary_texts")
        if not isinstance(summary, list):
            return []

        texts: List[str] = []
        for item in summary:
            if isinstance(item, dict):
                text_value = item.get("text")
                if text_value:
                    texts.append(str(text_value))
            elif isinstance(item, str):
                if item:
                    texts.append(item)
        return texts

    def _normalize_bbox(self, bbox: object) -> Optional[List[int]]:
        if bbox is None:
            return None

        if hasattr(bbox, "tolist"):
            try:
                bbox = bbox.tolist()
            except Exception:
                pass

        flat: List[int] = []

        def _collect(value: object) -> None:
            if hasattr(value, "tolist"):
                try:
                    value = value.tolist()
                except Exception:
                    pass

            if isinstance(value, (list, tuple)):
                for child in value:
                    _collect(child)
                return

            try:
                flat.append(int(round(float(value))))
            except Exception:
                return

        _collect(bbox)
        return flat or None
