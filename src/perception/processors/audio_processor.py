"""
Audio processor for speech recognition and deepfake detection.
Uses FunASR for ASR/VAD and MobileNetV3 for deepfake detection.
"""
from pathlib import Path
from typing import List, Optional

from src.core.models import MediaFile, MediaType, PerceptionResult, FakeAnalysis
from src.core.utils import run_in_threadpool, is_url
from src.perception.interfaces.base_processor import BaseProcessor
from src.perception.models.perception_models import ProcessorConfig


class AudioProcessor(BaseProcessor):
    """
    Audio processor using:
    - MobileNetV3 for deepfake detection
    - Alibaba FunASR for ASR and VAD
    """

    def __init__(self, config: Optional[ProcessorConfig] = None):
        super().__init__("audio_processor")
        self.config = config or ProcessorConfig()
        self._fake_analyzer = None
        self._nlp_engine = None

    @property
    def supported_types(self) -> List[str]:
        return ["audio"]

    async def _load_models(self) -> None:
        """Load audio analysis models."""
        try:
            import sys
            project_root = Path(__file__).parent.parent.parent.parent
            multimodal_path = project_root / "multimodal_input"
            if str(multimodal_path) not in sys.path:
                sys.path.insert(0, str(multimodal_path))

            from audio_module.audio_inference import AudioFakeAnalyzer
            from audio_module.VAD import AntiFraudAudioEngine

            # Load fake analyzer
            model_path = self.config.audio_model_path
            if not model_path:
                model_path = str(multimodal_path / "audio_module" / "weights" / "latest_best_audio_model.pth")

            self._fake_analyzer = AudioFakeAnalyzer(weight_path=model_path)

            # Load NLP engine (ASR + VAD)
            self._nlp_engine = AntiFraudAudioEngine(device="cuda")

        except Exception as e:
            print(f"[错误] 音频模型加载失败: {e}")
            raise

    async def process(
        self,
        media_file: MediaFile,
        context: Optional[dict] = None,
    ) -> PerceptionResult:
        """
        Process audio file.

        Args:
            media_file: Audio file
            context: Processing context

        Returns:
            PerceptionResult with transcription and fake analysis
        """
        await self.initialize()

        file_path = media_file.url

        # Handle URLs
        if is_url(file_path):
            return PerceptionResult(
                text_content="",
                source_media=media_file,
                metadata={"error": "URL audio not supported yet"},
            )

        try:
            # Read audio content
            with open(file_path, "rb") as f:
                audio_content = f.read()

            # Process audio
            return await self._process_audio_bytes(audio_content, media_file)

        except Exception as e:
            print(f"[错误] 音频处理失败: {e}")
            return PerceptionResult(
                text_content="",
                source_media=media_file,
                metadata={"error": str(e)},
            )

    async def _process_audio_bytes(
        self,
        audio_content: bytes,
        source_media: MediaFile,
    ) -> PerceptionResult:
        """Process audio bytes."""
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.parent
        multimodal_path = project_root / "multimodal_input"
        if str(multimodal_path) not in sys.path:
            sys.path.insert(0, str(multimodal_path))

        from audio_module.audio_inference import convert_bytes_to_ndarray

        # Convert bytes to numpy array
        audio_ndarray = await run_in_threadpool(
            convert_bytes_to_ndarray,
            audio_content,
        )

        # Run fake detection and ASR in parallel
        fake_task = run_in_threadpool(
            self._fake_analyzer.predict,
            audio_ndarray,
        )
        nlp_task = run_in_threadpool(
            self._nlp_engine.process_pipeline,
            audio_ndarray,
        )

        fake_prob, (transcribed_text, vad_timestamps) = await asyncio.gather(
            fake_task,
            nlp_task,
        )

        # Determine if fake
        is_fake = fake_prob > 0.8

        # Create fake analysis
        fake_analysis = FakeAnalysis(
            is_fake=is_fake,
            fake_probability=float(fake_prob),
            model_used="MobileNetV3_Audio",
            details={"vad_timestamps": vad_timestamps},
        )

        return PerceptionResult(
            text_content=transcribed_text,
            fake_analysis=fake_analysis,
            source_media=source_media,
            metadata={
                "audio_duration": len(audio_content),
                "vad_segments": len(vad_timestamps) if vad_timestamps else 0,
            },
        )

    async def health_check(self) -> bool:
        """Check if audio models are loaded."""
        return self._fake_analyzer is not None and self._nlp_engine is not None


# Import asyncio at module level for parallel processing
import asyncio