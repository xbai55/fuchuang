"""
JSON parsing and text extraction utilities.
Eliminates duplicate JSON parsing logic across nodes.
"""
import json
import re
from typing import Any, Optional


def extract_json_from_text(text: str) -> Optional[dict]:
    """
    Extract JSON object from text that may contain markdown code blocks.

    Args:
        text: Text potentially containing JSON

    Returns:
        Parsed dict or None if extraction fails

    Example:
        >>> extract_json_from_text('Some text ```json{"key": "value"}```')
        {'key': 'value'}
    """
    if not text:
        return None

    # Try to find JSON in markdown code blocks
    patterns = [
        r'```json\s*(.*?)\s*```',  # ```json ... ```
        r'```\s*(.*?)\s*```',      # ``` ... ```
        r'\{.*\}',                 # Raw JSON object
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    # Try to find JSON object boundaries
    json_start = text.find("{")
    json_end = text.rfind("}") + 1

    if json_start != -1 and json_end > json_start:
        try:
            json_str = text[json_start:json_end]
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return None


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with fallback default.

    Args:
        text: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    if not text:
        return default

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def get_text_content(response: Any) -> str:
    """
    Safely extract text content from various response formats.

    Handles:
    - String responses
    - List of message dicts (OpenAI format)
    - Dict with 'content' key
    - LangChain message objects

    Args:
        response: Response object of various types

    Returns:
        Extracted text content
    """
    if response is None:
        return ""

    # Direct string
    if isinstance(response, str):
        return response

    # List format (OpenAI messages)
    if isinstance(response, list) and len(response) > 0:
        first_item = response[0]
        if isinstance(first_item, dict):
            return first_item.get("content", "")
        return str(first_item)

    # Dict format
    if isinstance(response, dict):
        return response.get("content", "") or response.get("text", "") or str(response)

    # Object with content attribute (LangChain messages)
    if hasattr(response, "content"):
        return str(response.content)

    # Fallback to string conversion
    return str(response)


def safe_str(obj: Any) -> str:
    """
    Safe string sanitization for JSON serialization.
    Removes or replaces non-ASCII characters that could break JSON.

    Args:
        obj: Any object to convert to safe string

    Returns:
        Sanitized ASCII-safe string
    """
    try:
        text = str(obj)
        # Keep only printable ASCII characters
        return "".join([c if (31 < ord(c) < 128) else "?" for c in text])
    except Exception:
        return str(obj)
