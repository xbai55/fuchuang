"""
Data models for the perception layer.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ProcessorConfig(BaseModel):
    """Configuration for media processors."""

    # OCR settings
    ocr_use_angle_cls: bool = Field(True, description="Use angle classification for OCR")
    ocr_lang: str = Field("ch", description="OCR language")

    # Video settings
    video_snap_timestamp: float = Field(1.0, description="Timestamp for video frame capture")
    keyframe_interval: float = Field(2.0, description="Keyframe extraction interval in seconds")
    keyframe_scene_threshold: float = Field(0.35, description="Scene change detection threshold")
    keyframe_max_frames: int = Field(20, description="Maximum number of keyframes")

    # Audio settings
    audio_sample_rate: int = Field(16000, description="Audio sample rate")
    audio_max_duration: float = Field(5.0, description="Max audio duration for deepfake detection")

    # Model paths
    video_model_path: Optional[str] = Field(None, description="Video deepfake model path")
    audio_model_path: Optional[str] = Field(None, description="Audio deepfake model path")


class ProcessingContext(BaseModel):
    """Context passed during processing."""

    task_id: Optional[str] = Field(None, description="Task identifier")
    user_role: Optional[str] = Field(None, description="User role/persona")
    guardian_name: Optional[str] = Field(None, description="Guardian name for alerts")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
