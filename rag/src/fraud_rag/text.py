from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = normalize_whitespace(text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def build_summary(text: str, limit: int = 160) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _split_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    if len(paragraph) <= chunk_size:
        return [paragraph]
    parts = re.split(r"(?<=[。！？；])", paragraph)
    parts = [part.strip() for part in parts if part.strip()]
    output: list[str] = []
    current = ""
    for part in parts:
        if not current:
            current = part
            continue
        if len(current) + len(part) <= chunk_size:
            current += part
            continue
        output.append(current)
        current = part
    if current:
        output.append(current)
    return output or [paragraph]


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    text = clean_text(text)
    if not text:
        return []

    paragraphs: list[str] = []
    for paragraph in text.split("\n"):
        paragraphs.extend(_split_long_paragraph(paragraph.strip(), chunk_size))

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue
        candidate = current + "\n" + paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.append(current.strip())
        overlap = current[-chunk_overlap:].strip() if chunk_overlap > 0 else ""
        current = f"{overlap}\n{paragraph}".strip() if overlap else paragraph
    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]
