from __future__ import annotations

import json
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}


def _request(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> bytes:
    final_headers = dict(DEFAULT_HEADERS)
    if headers:
        final_headers.update(headers)
    request = Request(url, headers=final_headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> bytes:
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


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> str:
    payload = fetch_bytes(url, headers=headers, timeout=timeout, retries=retries)
    return payload.decode("utf-8", "ignore")


def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> dict[str, Any]:
    return json.loads(fetch_text(url, headers=headers, timeout=timeout, retries=retries))
