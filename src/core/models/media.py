"""
Media file and perception result models.
Provides unified interface for multi-modal data.
"""
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class MediaType(str, Enum):
    """Supported media types."""
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"


class MediaFile(BaseModel):
    """
    Unified media file representation.
    Supports both local files and URLs.
    """
    type: MediaType = Field(..., description="Media type")
    url: str = Field(..., description="File path or URL")
    content: Optional[bytes] = Field(None, description="Cached binary content")
    filename: Optional[str] = Field(None, description="Original filename")
    mime_type: Optional[str] = Field(None, description="MIME type")

    class Config:
        arbitrary_types_allowed = True


class FakeAnalysis(BaseModel):
    """AI forgery detection results."""
    is_fake: bool = Field(False, description="Whether content is AI-generated")
    fake_probability: float = Field(0.0, ge=0.0, le=1.0, description="Forgery probability")
    model_used: str = Field("", description="Detection model used")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


class OCRResult(BaseModel):
    """OCR text extraction result."""
    text: str = Field("", description="Extracted text")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="OCR confidence")
    bbox: Optional[List[int]] = Field(None, description="Bounding box coordinates")


class PerceptionResult(BaseModel):
    """
    Standardized perception layer output.
    Contains extracted information from any media type.
    """
    # Core text content extracted from media
    text_content: str = Field("", description="Extracted/recognized text content")

    # AI forgery detection
    fake_analysis: Optional[FakeAnalysis] = Field(None, description="AI forgery analysis")

    # OCR results (for images/videos)
    ocr_results: List[OCRResult] = Field(default_factory=list, description="OCR results")

    # Media-specific metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Media-specific metadata")

    # Source reference
    source_media: Optional[MediaFile] = Field(None, description="Source media file")

    def to_prompt_text(self) -> str:
        """
        Convert perception result to text suitable for LLM prompts.

        Returns:
            Formatted text summary
        """
        parts = []

        # Add forgery warning if detected
        if self.fake_analysis and self.fake_analysis.is_fake:
            parts.append(
                f"【系统前置判定】：极大概率为 AI 伪造合成内容 "
                f"(置信度 {self.fake_analysis.fake_probability:.2f})。"
            )

        # Add extracted text content
        if self.text_content:
            parts.append(f"【内容识别】：{self.text_content}")

        # Add OCR results summary
        if self.ocr_results:
            ocr_texts = [r.text for r in self.ocr_results if r.confidence > 0.5]
            if ocr_texts:
                parts.append(f"【OCR识别】：{' '.join(ocr_texts)}")

        return "\n".join(parts)

    def get_risk_indicators(self) -> List[str]:
        """
        Extract potential risk indicators from the perception result.

        Returns:
            List of risk indicator strings
        """
        indicators = []

        # AI forgery is a strong risk indicator
        if self.fake_analysis and self.fake_analysis.is_fake:
            indicators.append(f"AI伪造内容 (置信度: {self.fake_analysis.fake_probability:.2f})")

        # Check OCR results for suspicious keywords
        fraud_keywords = ["转账", "验证码", "安全账户", "公安局", "洗钱", "专案组"]
        for ocr in self.ocr_results:
            for keyword in fraud_keywords:
                if keyword in ocr.text:
                    indicators.append(f"可疑关键词: {keyword}")

        return indicators
