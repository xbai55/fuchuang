"""
Parse HTML files or HTML strings into fraud case records.
Handles both list pages (multiple articles) and single-case detail pages.
"""

import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

_NOISE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"}

# CSS class/id keywords that suggest main content
_CONTENT_RE = re.compile(r"(content|article|case|news|main|detail|text|body)", re.I)
# CSS class/id keywords that suggest noise (ads, sidebars, etc.)
_NOISE_RE = re.compile(r"(ad|sidebar|banner|comment|recommend|related|pagination|breadcrumb)", re.I)


def parse_html_file(file_path: str) -> list[dict]:
    """Parse a local HTML file; returns list of {text, source_id}."""
    path = Path(file_path)
    html = path.read_text(encoding="utf-8", errors="replace")
    return parse_html(html, source_prefix=path.stem)


def parse_html(html: str, source_prefix: str = "html", url: str = "") -> list[dict]:
    """Parse HTML string into records. Returns list of {text, source_id}."""
    soup = BeautifulSoup(html, "lxml")

    _strip_noise(soup)

    records = []
    articles = _find_articles(soup)

    if len(articles) >= 2:
        for i, art in enumerate(articles, 1):
            text = _extract_text(art)
            if text:
                sid = f"{url}#{i}" if url else f"{source_prefix}_{i}"
                records.append({"text": text, "source_id": sid})
    else:
        main = _find_main_content(soup)
        text = _extract_text(main)
        if text:
            sid = url if url else source_prefix
            records.append({"text": text, "source_id": sid})

    return records


def _strip_noise(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    # Also remove elements whose class/id looks like noise
    for tag in soup.find_all(True):
        classes = " ".join(tag.get("class") or [])
        tag_id = tag.get("id") or ""
        if _NOISE_RE.search(classes) or _NOISE_RE.search(tag_id):
            tag.decompose()


def _find_articles(soup: BeautifulSoup) -> list:
    """Try to find a list of case articles on a listing page."""
    # Explicit <article> tags
    arts = soup.find_all("article")
    if len(arts) >= 2:
        return arts

    # <li> items inside a ul/ol that look like case listings
    for ul in soup.find_all(["ul", "ol"]):
        items = ul.find_all("li", recursive=False)
        if len(items) >= 3:
            texts = [_extract_text(li) for li in items]
            if all(len(t) >= 30 for t in texts):
                return items

    # Divs with content-like classes that repeat at the same level
    for cls_pattern in [r"item", r"case", r"news", r"entry", r"post"]:
        matches = soup.find_all(class_=re.compile(cls_pattern, re.I))
        if len(matches) >= 2:
            return matches

    return []


def _find_main_content(soup: BeautifulSoup):
    """Return the tag most likely to contain the main case text."""
    candidates = [
        soup.find("main"),
        soup.find("article"),
        soup.find(id=_CONTENT_RE),
        soup.find(class_=_CONTENT_RE),
        soup.find("div", class_=_CONTENT_RE),
        soup.find("body"),
        soup,
    ]
    for c in candidates:
        if c is not None:
            return c
    return soup


def _extract_text(tag) -> str:
    if tag is None:
        return ""
    text = tag.get_text(separator="\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
