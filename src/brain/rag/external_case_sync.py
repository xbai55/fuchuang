"""Automated external fraud-case sync into the RAG knowledge base."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from src.brain.rag.hot_reload import ingest_documents_async
from src.brain.rag.crawler import load_local_case_directory
from src.brain.rag.http_client import fetch_json, fetch_text
from src.brain.rag.models import KnowledgeDocument


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config" / "external_case_sources.yaml"
_DEFAULT_STATE_PATH = _PROJECT_ROOT / "data" / "knowledge" / "import_reports" / "external_case_sync_state.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _sha1(*parts: str) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update((part or "").encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def _clean_text(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines).strip()


def _build_summary(value: str, limit: int = 160) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _resolve_path(path_value: str | Path | None, *, default_path: Path) -> Path:
    if path_value is None or str(path_value).strip() == "":
        path = default_path
    else:
        path = Path(path_value)

    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path.resolve()


def get_external_case_sync_config_path(config_path: str | Path | None = None) -> Path:
    if config_path:
        return _resolve_path(config_path, default_path=_DEFAULT_CONFIG_PATH)

    env_path = os.getenv("EXTERNAL_CASE_SYNC_CONFIG", "").strip()
    if env_path:
        return _resolve_path(env_path, default_path=_DEFAULT_CONFIG_PATH)

    return _DEFAULT_CONFIG_PATH


def _load_sync_config(config_path: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    resolved = get_external_case_sync_config_path(config_path)
    if not resolved.exists():
        return {}, resolved

    payload = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {}, resolved
    return payload, resolved


def _state_path_from_config(config: dict[str, Any]) -> Path:
    configured = config.get("state_file")
    return _resolve_path(configured, default_path=_DEFAULT_STATE_PATH)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "last_run_at": None,
            "seen_fingerprints": [],
            "sources": {},
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    payload.setdefault("version", 1)
    payload.setdefault("last_run_at", None)
    payload.setdefault("seen_fingerprints", [])
    payload.setdefault("sources", {})
    if not isinstance(payload["sources"], dict):
        payload["sources"] = {}
    if not isinstance(payload["seen_fingerprints"], list):
        payload["seen_fingerprints"] = []
    return payload


def _save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _canonical_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""

    split = urlsplit(value)
    scheme = (split.scheme or "https").lower()
    netloc = split.netloc.lower()
    path = split.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return f"{scheme}://{netloc}{path}"


def _merge_tags(base: list[str], extra: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in [*(base or []), *(extra or [])]:
        tag = str(value or "").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        merged.append(tag)
    return merged


def _to_core_document(raw_doc: Any) -> KnowledgeDocument:
    if isinstance(raw_doc, KnowledgeDocument):
        return raw_doc

    if hasattr(raw_doc, "to_dict"):
        return KnowledgeDocument.from_dict(raw_doc.to_dict())

    if isinstance(raw_doc, dict):
        return KnowledgeDocument.from_dict(raw_doc)

    raise TypeError(f"Unsupported document type: {type(raw_doc)}")


def _normalize_document(
    doc: KnowledgeDocument,
    *,
    source_name: str,
    category: str,
    subtype: str | None,
    tags: list[str],
    min_content_length: int,
) -> KnowledgeDocument | None:
    cleaned_title = _clean_text(doc.title or "")
    cleaned_content = _clean_text(doc.content or "")
    if len(cleaned_content) < min_content_length:
        return None

    effective_title = cleaned_title or cleaned_content[:32] or "External fraud case"
    canonical_url = _canonical_url(doc.canonical_url or doc.url)
    if not canonical_url:
        canonical_url = f"external://{source_name}/{_sha1(effective_title, cleaned_content[:160])}"

    source_url = _canonical_url(doc.url) or canonical_url
    netloc = urlsplit(source_url).netloc or urlsplit(canonical_url).netloc or source_name

    effective_category = category or doc.category or "case"
    effective_subtype = subtype if subtype is not None else doc.subtype
    merged_tags = _merge_tags(list(doc.tags), tags)

    return KnowledgeDocument(
        doc_id=_sha1(canonical_url, effective_category, effective_title),
        url=source_url,
        canonical_url=canonical_url,
        source_site=netloc,
        category=effective_category,
        title=effective_title,
        content=cleaned_content,
        summary=_build_summary(cleaned_content),
        published_at=doc.published_at,
        source_name=doc.source_name or source_name,
        subtype=effective_subtype,
        tags=merged_tags,
        images=list(doc.images),
        metadata={
            **dict(doc.metadata or {}),
            "external_source": source_name,
            "import_source": "external_case_sync",
        },
    )


def _resolve_records_path(payload: Any, path: str | None) -> Any:
    if not path:
        return payload

    current = payload
    for token in [part.strip() for part in path.split(".") if part.strip()]:
        if isinstance(current, dict):
            current = current.get(token)
            continue

        if isinstance(current, list) and token.isdigit():
            index = int(token)
            if 0 <= index < len(current):
                current = current[index]
                continue
        return None
    return current


def _find_record_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("records", "items", "list", "data", "results", "source_data"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = [item for item in value if isinstance(item, dict)]
                if rows:
                    return rows

        for value in payload.values():
            rows = _find_record_list(value)
            if rows:
                return rows

    return []


def _json_rows_to_documents(source: dict[str, Any], rows: list[dict[str, Any]]) -> list[KnowledgeDocument]:
    name = str(source.get("name") or "external_source")
    category = str(source.get("category") or "case")
    subtype = source.get("subtype")
    tags = [str(tag).strip() for tag in source.get("tags", []) if str(tag).strip()]
    title_field = str(source.get("title_field") or "title")
    content_field = str(source.get("content_field") or "content")
    url_field = str(source.get("url_field") or "url")
    published_field = str(source.get("published_at_field") or "published_at")

    documents: list[KnowledgeDocument] = []
    for row in rows:
        title = _clean_text(str(row.get(title_field, "")))
        content = _clean_text(str(row.get(content_field, "")))
        if not title and not content:
            continue

        url = _canonical_url(str(row.get(url_field, "")))
        if not url:
            url = f"external://{name}/{_sha1(title, content[:160])}"

        netloc = urlsplit(url).netloc or name
        documents.append(
            KnowledgeDocument(
                doc_id=_sha1(url, category, title or content[:32]),
                url=url,
                canonical_url=url,
                source_site=netloc,
                category=category,
                title=title or content[:32] or "External fraud case",
                content=content,
                summary=_build_summary(content),
                published_at=str(row.get(published_field, "")).strip() or None,
                source_name=name,
                subtype=subtype,
                tags=list(tags),
                images=[],
                metadata={
                    "external_source": name,
                    "import_source": "external_case_sync",
                },
            )
        )

    return documents


async def _collect_from_url(source: dict[str, Any]) -> list[KnowledgeDocument]:
    # Late import avoids loading optional parser dependencies on unrelated paths.
    from rag.src.fraud_rag.html_importer import parse_html_content

    url = str(source.get("url") or "").strip()
    if not url:
        raise ValueError("source.url is required for type=url")

    html = await asyncio.to_thread(fetch_text, url)
    parsed_docs = await asyncio.to_thread(
        parse_html_content,
        html,
        source_url=url,
        category=source.get("category"),
        tags=source.get("tags") or [],
    )
    return [_to_core_document(item) for item in parsed_docs]


async def _collect_from_json_url(source: dict[str, Any]) -> list[KnowledgeDocument]:
    url = str(source.get("url") or "").strip()
    if not url:
        raise ValueError("source.url is required for type=json_url")

    payload = await asyncio.to_thread(fetch_json, url)
    resolved = _resolve_records_path(payload, source.get("records_path"))
    rows = _find_record_list(resolved)
    return _json_rows_to_documents(source, rows)


async def _collect_from_json_file(source: dict[str, Any]) -> list[KnowledgeDocument]:
    raw_path = source.get("path") or source.get("file")
    if not raw_path:
        raise ValueError("source.path is required for type=json_file")

    file_path = _resolve_path(raw_path, default_path=_PROJECT_ROOT / str(raw_path))
    if not file_path.exists():
        raise FileNotFoundError(f"json file not found: {file_path}")

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    resolved = _resolve_records_path(payload, source.get("records_path"))
    rows = _find_record_list(resolved)
    return _json_rows_to_documents(source, rows)


async def _collect_from_local_case_directory(source: dict[str, Any]) -> list[KnowledgeDocument]:
    raw_path = source.get("path") or source.get("directory")
    if not raw_path:
        raise ValueError("source.path is required for type=local_case_directory")

    directory_path = _resolve_path(raw_path, default_path=_PROJECT_ROOT / str(raw_path))
    if not directory_path.exists():
        raise FileNotFoundError(f"local case directory not found: {directory_path}")
    if not directory_path.is_dir():
        raise NotADirectoryError(f"local case directory is not a directory: {directory_path}")

    return await asyncio.to_thread(load_local_case_directory, directory_path)


async def _collect_source_documents(source: dict[str, Any]) -> list[KnowledgeDocument]:
    source_type = str(source.get("type") or "url").strip().lower()
    if source_type == "url":
        return await _collect_from_url(source)
    if source_type == "json_url":
        return await _collect_from_json_url(source)
    if source_type == "json_file":
        return await _collect_from_json_file(source)
    if source_type == "local_case_directory":
        return await _collect_from_local_case_directory(source)
    raise ValueError(f"Unsupported source type: {source_type}")


def _fingerprint(doc: KnowledgeDocument) -> str:
    return _sha1(doc.canonical_url, doc.title, doc.content[:260])


def is_external_case_sync_enabled(config_path: str | Path | None = None) -> bool:
    env_override = os.getenv("EXTERNAL_CASE_SYNC_ENABLED")
    if env_override is not None:
        return _truthy(env_override, default=False)

    config, _ = _load_sync_config(config_path)
    return bool(config.get("enabled", False))


def get_external_case_sync_interval_seconds(config_path: str | Path | None = None) -> int:
    env_override = os.getenv("EXTERNAL_CASE_SYNC_INTERVAL_SECONDS")
    if env_override:
        try:
            value = int(env_override)
            if value > 0:
                return value
        except ValueError:
            pass

    config, _ = _load_sync_config(config_path)
    value = int(config.get("interval_seconds", 900) or 900)
    return value if value > 0 else 900


def get_external_case_sync_status(config_path: str | Path | None = None) -> dict[str, Any]:
    config, resolved = _load_sync_config(config_path)
    state_path = _state_path_from_config(config)
    state = _load_state(state_path)

    return {
        "status": "ok" if resolved.exists() else "config_not_found",
        "enabled": is_external_case_sync_enabled(config_path),
        "config_path": str(resolved),
        "state_path": str(state_path),
        "interval_seconds": get_external_case_sync_interval_seconds(config_path),
        "min_content_length": int(config.get("min_content_length", 80) or 80),
        "sources": [
            {
                "name": str(item.get("name") or "unnamed_source"),
                "type": str(item.get("type") or "url"),
                "enabled": bool(item.get("enabled", True)),
            }
            for item in config.get("sources", [])
            if isinstance(item, dict)
        ],
        "last_run_at": state.get("last_run_at"),
        "source_state": state.get("sources", {}),
        "seen_fingerprint_count": len(state.get("seen_fingerprints", [])),
    }


async def sync_external_case_sources(
    config_path: str | Path | None = None,
    *,
    source_names: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    config, resolved = _load_sync_config(config_path)
    if not resolved.exists():
        return {
            "status": "config_not_found",
            "config_path": str(resolved),
        }

    if not config.get("sources"):
        return {
            "status": "no_sources",
            "config_path": str(resolved),
        }

    if not is_external_case_sync_enabled(config_path):
        return {
            "status": "disabled",
            "config_path": str(resolved),
        }

    state_path = _state_path_from_config(config)
    state = _load_state(state_path)
    seen = set(str(item) for item in state.get("seen_fingerprints", []))

    requested = set(source_names or [])
    min_content_length = int(config.get("min_content_length", 80) or 80)

    source_reports: list[dict[str, Any]] = []
    total_collected = 0
    total_cleaned = 0
    total_new = 0
    pending_ingest_reports: list[tuple[str, dict[str, Any], list[KnowledgeDocument]]] = []

    for item in config.get("sources", []):
        if not isinstance(item, dict):
            continue

        source_name = str(item.get("name") or "unnamed_source")
        if requested and source_name not in requested:
            continue
        if not bool(item.get("enabled", True)):
            continue

        source_type = str(item.get("type") or "url")
        source_tags = [str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()]
        source_category = str(item.get("category") or "case")
        source_subtype = item.get("subtype")

        report = {
            "name": source_name,
            "type": source_type,
            "status": "ok",
            "collected_documents": 0,
            "cleaned_documents": 0,
            "new_documents": 0,
            "skipped_duplicates": 0,
        }

        try:
            docs = await _collect_source_documents(item)
            report["collected_documents"] = len(docs)
            total_collected += len(docs)

            normalized_docs: list[KnowledgeDocument] = []
            for doc in docs:
                normalized = _normalize_document(
                    doc,
                    source_name=source_name,
                    category=source_category,
                    subtype=source_subtype,
                    tags=source_tags,
                    min_content_length=min_content_length,
                )
                if normalized is None:
                    continue
                normalized_docs.append(normalized)

            report["cleaned_documents"] = len(normalized_docs)
            total_cleaned += len(normalized_docs)

            new_docs: list[KnowledgeDocument] = []
            for doc in normalized_docs:
                marker = _fingerprint(doc)
                if marker in seen:
                    report["skipped_duplicates"] += 1
                    continue
                seen.add(marker)
                new_docs.append(doc)

            report["new_documents"] = len(new_docs)
            total_new += len(new_docs)

            if dry_run:
                report["ingest"] = {
                    "status": "dry_run",
                    "added_chunks": 0,
                    "skipped_chunks": 0,
                    "total_chunks": 0,
                }
                state["sources"][source_name] = {
                    "last_run_at": _iso_now(),
                    "last_status": report["status"],
                    "last_new_documents": report["new_documents"],
                    "last_ingest_status": report["ingest"].get("status"),
                }
            elif new_docs:
                pending_ingest_reports.append((source_name, report, new_docs))
            else:
                report["ingest"] = {
                    "status": "no_new_documents",
                    "added_chunks": 0,
                    "skipped_chunks": 0,
                    "total_chunks": 0,
                }
                state["sources"][source_name] = {
                    "last_run_at": _iso_now(),
                    "last_status": report["status"],
                    "last_new_documents": report["new_documents"],
                    "last_ingest_status": report["ingest"].get("status"),
                }

        except Exception as exc:
            report["status"] = "failed"
            report["error"] = str(exc)
            state["sources"][source_name] = {
                "last_run_at": _iso_now(),
                "last_status": "failed",
                "last_error": str(exc),
            }

        source_reports.append(report)

    batch_ingest_report: dict[str, Any] | None = None
    if pending_ingest_reports and not dry_run:
        all_new_docs = [doc for _, _, docs in pending_ingest_reports for doc in docs]
        total_batch_docs = len(all_new_docs)
        try:
            batch_ingest_report = await ingest_documents_async(all_new_docs)
            remaining_added_chunks = int(batch_ingest_report.get("added_chunks", 0) or 0)
            remaining_skipped_chunks = int(batch_ingest_report.get("skipped_chunks", 0) or 0)
            assigned_docs = 0

            for index, (source_name, report, docs) in enumerate(pending_ingest_reports):
                source_doc_count = len(docs)
                assigned_docs += source_doc_count
                is_last = index == len(pending_ingest_reports) - 1

                if is_last or total_batch_docs <= 0:
                    added_chunks = remaining_added_chunks
                    skipped_chunks = remaining_skipped_chunks
                else:
                    ratio = source_doc_count / total_batch_docs
                    added_chunks = int(round(int(batch_ingest_report.get("added_chunks", 0) or 0) * ratio))
                    skipped_chunks = int(round(int(batch_ingest_report.get("skipped_chunks", 0) or 0) * ratio))
                    added_chunks = min(added_chunks, remaining_added_chunks)
                    skipped_chunks = min(skipped_chunks, remaining_skipped_chunks)
                    remaining_added_chunks -= added_chunks
                    remaining_skipped_chunks -= skipped_chunks

                report["ingest"] = {
                    **batch_ingest_report,
                    "batched": True,
                    "batch_document_count": total_batch_docs,
                    "source_document_count": source_doc_count,
                    "added_chunks": added_chunks,
                    "skipped_chunks": skipped_chunks,
                }
                state["sources"][source_name] = {
                    "last_run_at": _iso_now(),
                    "last_status": report["status"],
                    "last_new_documents": report["new_documents"],
                    "last_ingest_status": report["ingest"].get("status"),
                }
        except Exception as exc:
            for source_name, report, _docs in pending_ingest_reports:
                report["status"] = "failed"
                report["error"] = str(exc)
                report["ingest"] = {
                    "status": "failed",
                    "added_chunks": 0,
                    "skipped_chunks": 0,
                    "total_chunks": 0,
                    "error": str(exc),
                    "batched": True,
                }
                state["sources"][source_name] = {
                    "last_run_at": _iso_now(),
                    "last_status": "failed",
                    "last_error": str(exc),
                }

    # Cap state size so the state file does not grow without bound.
    max_fingerprints = int(config.get("max_seen_fingerprints", 50000) or 50000)
    ordered_seen = list(seen)
    if len(ordered_seen) > max_fingerprints:
        ordered_seen = ordered_seen[-max_fingerprints:]

    state["seen_fingerprints"] = ordered_seen
    state["last_run_at"] = _iso_now()

    if not dry_run:
        _save_state(state_path, state)

    return {
        "status": "ok",
        "config_path": str(resolved),
        "state_path": str(state_path),
        "dry_run": dry_run,
        "processed_sources": len(source_reports),
        "total_collected_documents": total_collected,
        "total_cleaned_documents": total_cleaned,
        "total_new_documents": total_new,
        "batch_ingest": batch_ingest_report,
        "sources": source_reports,
    }


async def run_external_case_sync_loop(
    stop_event: asyncio.Event,
    *,
    config_path: str | Path | None = None,
) -> None:
    """Run periodic external-case sync until stop_event is set."""
    while not stop_event.is_set():
        try:
            result = await sync_external_case_sources(config_path)
            print(
                "[ExternalCaseSync] run status="
                f"{result.get('status')} new_docs={result.get('total_new_documents', 0)}"
            )
        except Exception as exc:
            print(f"[ExternalCaseSync] run failed: {exc}")

        interval_seconds = get_external_case_sync_interval_seconds(config_path)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
