"""
RAG 爬虫 HTTP 工具
提供带重试的文本/JSON 抓取能力。
"""
from __future__ import annotations

import json
import re
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

_CHARSET_PATTERN = re.compile(rb"charset\s*=\s*['\"]?\s*([A-Za-z0-9._-]+)", re.IGNORECASE)
_CHARSET_ALIASES = {
    "utf8": "utf-8",
    "gb2312": "gb18030",
    "gbk": "gb18030",
    "x-gbk": "gb18030",
    "gb_2312-80": "gb18030",
}

try:
    from charset_normalizer import from_bytes as _detect_charset_bytes
except Exception:
    _detect_charset_bytes = None


def _normalize_charset(charset: str | None) -> str | None:
    if not charset:
        return None

    normalized = charset.strip().strip('"\'').lower()
    if not normalized:
        return None
    return _CHARSET_ALIASES.get(normalized, normalized)


def _extract_charset_from_meta(payload: bytes) -> str | None:
    head = payload[:4096]
    match = _CHARSET_PATTERN.search(head)
    if not match:
        return None
    return _normalize_charset(match.group(1).decode("ascii", "ignore"))


def _guess_charset(payload: bytes, header_charset: str | None) -> str | None:
    for candidate in (header_charset, _extract_charset_from_meta(payload)):
        normalized = _normalize_charset(candidate)
        if normalized:
            return normalized

    if _detect_charset_bytes is not None:
        try:
            best = _detect_charset_bytes(payload).best()
            if best is not None and getattr(best, "encoding", None):
                normalized = _normalize_charset(best.encoding)
                if normalized:
                    return normalized
        except Exception:
            pass

    return None


def _decode_payload(payload: bytes, header_charset: str | None) -> str:
    candidates: list[str] = []
    preferred = _guess_charset(payload, header_charset)
    if preferred:
        candidates.append(preferred)
    candidates.extend(["utf-8", "gb18030", "big5"])

    seen: set[str] = set()
    for encoding in candidates:
        normalized = _normalize_charset(encoding)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        try:
            return payload.decode(normalized)
        except (UnicodeDecodeError, LookupError):
            continue

    return payload.decode("utf-8", "replace")


def _request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[bytes, str | None]:
    final_headers = dict(DEFAULT_HEADERS)
    if headers:
        final_headers.update(headers)
    request = Request(url, headers=final_headers)
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
        content_charset = None
        if hasattr(response.headers, "get_content_charset"):
            content_charset = response.headers.get_content_charset()
        return payload, _normalize_charset(content_charset)


def _fetch_payload(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> tuple[bytes, str | None]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return _request(url, headers=headers, timeout=timeout)
        except (HTTPError, URLError, socket.timeout) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(0.6 * (attempt + 1))

    assert last_error is not None
    raise last_error


def fetch_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> bytes:
    payload, _ = _fetch_payload(url, headers=headers, timeout=timeout, retries=retries)
    return payload


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> str:
    payload, header_charset = _fetch_payload(
        url,
        headers=headers,
        timeout=timeout,
        retries=retries,
    )
    return _decode_payload(payload, header_charset)


def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> dict[str, Any]:
    return json.loads(fetch_text(url, headers=headers, timeout=timeout, retries=retries))
