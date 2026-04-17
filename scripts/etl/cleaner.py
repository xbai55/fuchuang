"""
Fraud case text cleaning utilities.
Input: raw case text
Output: normalized text + SHA256 hash for dedup
"""

import hashlib
import re
import unicodedata


# PII patterns to mask before storage
_PII_PATTERNS = [
    (re.compile(r"1[3-9]\d{9}"), "[手机号]"),
    (re.compile(r"\d{15,18}X?"), "[身份证]"),
    (re.compile(r"\d{16,19}"), "[银行卡]"),
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[邮箱]"),
]


def clean(raw_text: str) -> str:
    """Return cleaned text or raise ValueError if text is unusable."""
    text = raw_text.strip()

    # Normalize unicode (full-width → half-width, etc.)
    text = unicodedata.normalize("NFKC", text)

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Mask PII
    for pattern, placeholder in _PII_PATTERNS:
        text = pattern.sub(placeholder, text)

    text = text.strip()

    if len(text) < 30:
        raise ValueError(f"Text too short after cleaning ({len(text)} chars)")

    if not _contains_chinese(text):
        raise ValueError("Text contains no Chinese characters")

    return text


def text_hash(cleaned_text: str) -> str:
    return hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)
