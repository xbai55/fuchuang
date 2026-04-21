"""
Video processor for deepfake detection and keyframe analysis.
Uses EfficientNet-B0 for deepfake detection and parallel OCR.
"""
import asyncio
from pathlib import Path
from typing import List, Optional

from src.core.models import MediaFile, MediaType, PerceptionResult, FakeAnalysis
from src.core.utils import run_in_threadpool, is_url
from src.perception.interfaces.base_processor import BaseProcessor
from src.perception.models.perception_models import ProcessorConfig
from src.perception.processors.ocr_processor import OCRProcessor


class VideoProcessor(BaseProcessor):
    """
    Video processor using:
    - EfficientNet-B0 for deepfake detection
    - Keyframe extraction + OCR for content analysis

    Parallel processing:
    1. Deepfake detection
    2. Keyframe extraction + OCR
    """

    def __init__(
        self,
        config: Optional[ProcessorConfig] = None,
        shared_ocr_processor: Optional[OCRProcessor] = None,
    ):
        super().__init__("video_processor")
        self.config = config or ProcessorConfig()
        self._fake_analyzer = None
        self._keyframe_extractor = None
        self._ocr_processor = shared_ocr_processor
        self._ocr_enabled = False
        self._ocr_init_error: Optional[str] = None

    @property
    def supported_types(self) -> List[str]:
        return ["video"]

    async def _load_models(self) -> None:
        """Load video analysis models."""
        try:
            import sys
            project_root = Path(__file__).parent.parent.parent.parent
            multimodal_path = project_root / "multimodal_input"
            if str(multimodal_path) not in sys.path:
                sys.path.insert(0, str(multimodal_path))

            from video_module.video_inference import get_shared_video_fake_analyzer
            from video_module.keyframe_extractor import KeyframeExtractor

            # Load fake analyzer
            model_path = self.config.video_model_path
            if not model_path:
                model_path = str(multimodal_path / "video_module" / "weights" / "final_model.pth")

            self._fake_analyzer = get_shared_video_fake_analyzer(
                weight_path=model_path,
                snap_timestamp_sec=self.config.video_snap_timestamp,
            )

            # Create keyframe extractor
            self._keyframe_extractor = KeyframeExtractor(
                output_root=str(multimodal_path / "video_module" / "keyframes"),
                interval_sec=self.config.keyframe_interval,
                scene_threshold=self.config.keyframe_scene_threshold,
                max_frames=self.config.keyframe_max_frames,
            )

            # Reuse the shared OCR processor when available to avoid duplicate model load.
            if self._ocr_processor is None:
                self._ocr_processor = OCRProcessor(self.config)

            try:
                await self._ocr_processor.initialize()
                self._ocr_enabled = True
                self._ocr_init_error = None
            except Exception as exc:
                # Keep video deepfake detector available even if OCR backend fails.
                self._ocr_enabled = False
                self._ocr_init_error = str(exc)
                print(f"[警告] 视频OCR子模块初始化失败，已降级为仅深伪检测: {exc}")

        except Exception as e:
            print(f"[错误] 视频模型加载失败: {e}")
            raise

    async def process(
        self,
        media_file: MediaFile,
        context: Optional[dict] = None,
    ) -> PerceptionResult:
        """
        Process video file.

        Args:
            media_file: Video file
            context: Processing context with task_id

        Returns:
            PerceptionResult with deepfake analysis and OCR results
        """
        await self.initialize()

        file_path = media_file.url
        task_id = (context or {}).get("task_id") or "default"

        # Handle URLs
        if is_url(file_path):
            return PerceptionResult(
                text_content="",
                source_media=media_file,
                metadata={"error": "URL video not supported yet"},
            )

        try:
            # Run deepfake detection and keyframe extraction in parallel
            fake_task = run_in_threadpool(
                self._fake_analyzer.predict_from_path,
                file_path,
            )
            keyframe_task = run_in_threadpool(
                self._keyframe_extractor.extract,
                file_path,
                task_id,
            )

            fake_prob, keyframe_result = await asyncio.gather(
                fake_task,
                keyframe_task,
            )

            # Get keyframe paths
            keyframe_paths = keyframe_result.frame_paths if hasattr(keyframe_result, 'frame_paths') else []

            # Process keyframes with OCR if available
            ocr_text_content = ""
            ocr_results = []

            if (
                keyframe_paths
                and self._ocr_enabled
                and self._ocr_processor
                and getattr(self._ocr_processor, "_ocr_processor", None) is not None
            ):
                ocr_result = await self._ocr_processor._ocr_processor.process_keyframes(keyframe_paths)

                from src.core.models import OCRResult

                for item in self._ocr_processor._extract_text_items(ocr_result):
                    confidence = float(item.get("confidence", 0))
                    if confidence > 0.5:
                        ocr_results.append(OCRResult(
                            text=str(item.get("text", "")),
                            confidence=confidence,
                            bbox=self._ocr_processor._normalize_bbox(item.get("bbox")),
                        ))

                summary = self._ocr_processor._extract_summary_texts(ocr_result)
                ocr_text_content = " ".join(summary) if summary else ""

            # Determine if fake
            is_fake = fake_prob > 0.6

            # Create fake analysis
            fake_analysis = FakeAnalysis(
                is_fake=is_fake,
                fake_probability=float(fake_prob),
                model_used="EfficientNet-B0",
                details={
                    "keyframe_count": len(keyframe_paths),
                    "snap_timestamp": self.config.video_snap_timestamp,
                },
            )

            # Combine text content
            text_content = ocr_text_content

            return PerceptionResult(
                text_content=text_content,
                fake_analysis=fake_analysis,
                ocr_results=ocr_results,
                source_media=media_file,
                metadata={
                    "keyframe_count": len(keyframe_paths),
                    "keyframe_dir": getattr(keyframe_result, 'frame_dir', None),
                    "ocr_enabled": self._ocr_enabled,
                    "ocr_error": self._ocr_init_error if not self._ocr_enabled else None,
                },
            )

        except Exception as e:
            print(f"[错误] 视频处理失败: {e}")
            return PerceptionResult(
                text_content="",
                source_media=media_file,
                metadata={"error": str(e)},
            )

    async def health_check(self) -> bool:
        """Check if video models are loaded."""
        return self._fake_analyzer is not None
