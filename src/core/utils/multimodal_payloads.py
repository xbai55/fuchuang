"""
Helpers for building OpenAI-compatible multimodal user payloads.
"""
from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


LLMContentBlock = Dict[str, Any]
LLMUserContent = Union[str, List[LLMContentBlock]]

_URL_SCHEME_RE = re.compile(r"^(?:https?|ftp)://", re.IGNORECASE)


def build_text_and_video_user_content(
    text: str,
    video_url_or_path: Optional[str] = None,
) -> LLMUserContent:
    """
    Build an OpenAI-compatible user content payload containing text plus video.

    Returns plain text when no video is provided so existing text-only call
    sites can keep working unchanged.
    """
    normalized_text = str(text or "").strip()
    normalized_video = str(video_url_or_path or "").strip()
    if not normalized_video:
        return normalized_text

    return [
        {
            "type": "text",
            "text": normalized_text or "Analyze the attached video together with the provided context.",
        },
        {
            "type": "video_url",
            "video_url": {
                "url": _normalize_media_reference(normalized_video, default_mime="video/mp4"),
            },
        },
    ]


def flatten_multimodal_text_content(content: Any) -> str:
    """Extract text blocks from multimodal content for text-only backends."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

    parts: List[str] = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
            elif "text" in item:
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
        elif item:
            parts.append(str(item))

    return "\n\n".join(parts).strip()


def _normalize_media_reference(media_url_or_path: str, default_mime: str) -> str:
    if media_url_or_path.startswith("data:") or _URL_SCHEME_RE.match(media_url_or_path):
        return media_url_or_path

    media_path = Path(media_url_or_path)
    mime_type = mimetypes.guess_type(media_path.name)[0] or default_mime
    encoded = base64.b64encode(media_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
