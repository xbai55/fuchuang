from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup


def sha1_text(*parts: str) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def canonicalize_url(url: str) -> str:
    split = urlsplit(url.strip())
    path = split.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit(
        (
            split.scheme.lower() or "http",
            split.netloc.lower(),
            path,
            "",
            "",
        )
    )


def detect_source_site(url: str) -> str:
    netloc = urlsplit(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def strip_html(text: str) -> str:
    if "<" not in text and ">" not in text:
        return text
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
