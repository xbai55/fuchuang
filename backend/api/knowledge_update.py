"""
知识库更新 API
支持：
  - 上传 HTML 文件并导入
  - 从 URL 抓取并导入
  - 查询知识库状态与统计
  - 触发完整重建
"""
from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from auth import get_current_user
from database import User
from src.brain.rag.external_case_sync import (
    get_external_case_sync_status,
    sync_external_case_sources,
)

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _get_rag_config_path() -> Path:
    from src.brain.rag.auto_build import get_rag_config_path
    return get_rag_config_path()


async def _html_to_documents(html: str, source_url: str = "", tags: list[str] | None = None):
    """在线程中解析 HTML，返回 KnowledgeDocument 列表。"""
    import sys
    sys.path.insert(0, str(_PROJECT_ROOT))
    from rag.src.fraud_rag.html_importer import parse_html_content

    return await asyncio.to_thread(
        parse_html_content,
        html,
        source_url=source_url,
        tags=tags,
    )


async def _fetch_url(url: str) -> str:
    """在线程中抓取 URL，返回 HTML 字符串。"""
    from src.brain.rag.auto_build import _PROJECT_ROOT as ROOT
    import sys
    sys.path.insert(0, str(_PROJECT_ROOT))
    from rag.src.fraud_rag.http_client import fetch_text

    return await asyncio.to_thread(fetch_text, url)


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.post("/import/html", summary="上传 HTML 文件批量导入知识库")
async def import_html_files(
    files: Annotated[List[UploadFile], File(description="一或多个 HTML 文件")],
    tags: Annotated[str, Form(description="逗号分隔的附加标签")] = "",
    current_user: User = Depends(get_current_user),
):
    """
    上传 HTML 文件，解析其中的诈骗案例内容并增量写入 RAG 知识库。
    """
    from src.brain.rag.hot_reload import ingest_documents_async

    extra_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    all_docs = []
    errors = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".html"):
            errors.append(f"{file.filename}: 仅支持 .html 文件")
            continue
        try:
            raw = await file.read()
            html = raw.decode("utf-8", errors="replace")
            docs = await _html_to_documents(html, source_url=file.filename, tags=extra_tags)
            all_docs.extend(docs)
        except Exception as exc:
            errors.append(f"{file.filename}: {exc}")

    if not all_docs and errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    stats = await ingest_documents_async(all_docs)
    return {
        "imported_documents": len(all_docs),
        "errors": errors,
        **stats,
    }


@router.post("/import/url", summary="从 URL 抓取 HTML 并导入知识库")
async def import_from_url(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """
    从指定 URL 抓取网页，解析诈骗案例内容并增量写入 RAG 知识库。

    Request body:
        url (str): 目标 URL
        tags (list[str], optional): 附加标签
    """
    from src.brain.rag.hot_reload import ingest_documents_async

    url: str = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="url 不能为空")

    extra_tags: list[str] = body.get("tags", [])

    try:
        html = await _fetch_url(url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"抓取失败: {exc}")

    docs = await _html_to_documents(html, source_url=url, tags=extra_tags)
    if not docs:
        raise HTTPException(status_code=422, detail="未能从页面提取有效内容")

    stats = await ingest_documents_async(docs)
    return {
        "url": url,
        "imported_documents": len(docs),
        **stats,
    }


@router.get("/status", summary="查询知识库就绪状态")
async def get_knowledge_status(
    current_user: User = Depends(get_current_user),
):
    """返回 RAG 索引是否就绪及基本统计。"""
    from src.brain.rag.auto_build import _index_ready, get_rag_config_path
    from src.brain.rag.config import load_rag_config
    from src.brain.rag.pipeline import read_jsonl

    config_path = get_rag_config_path()
    if not config_path.exists():
        return {"ready": False, "reason": "config_not_found"}

    config = load_rag_config(config_path)
    ready = _index_ready(config)

    result: dict = {
        "ready": ready,
        "index_dir": str(config.paths.index_dir),
        "backend": config.index.backend,
    }

    if ready:
        result["chunk_count"] = len(read_jsonl(config.paths.chunks))
        result["document_count"] = len(read_jsonl(config.paths.raw_documents))

        meta_path = config.paths.index_dir / "auto_build_meta.json"
        if meta_path.exists():
            import json
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            result["last_built"] = meta.get("updated_at")

        hot_meta = config.paths.index_dir / "manifest.json"
        if hot_meta.exists():
            import json
            m = json.loads(hot_meta.read_text(encoding="utf-8"))
            result["last_hot_reload"] = m.get("last_hot_reload")

    return result


@router.post("/rebuild", summary="触发知识库完整重建")
async def rebuild_knowledge_base(
    body: dict = {},
    current_user: User = Depends(get_current_user),
):
    """
    触发完整的 RAG 知识库重建（爬取 + 分块 + 建索引）。
    耗时较长，以后台任务执行，立即返回 task_id。

    Request body:
        force (bool): 即使索引已存在也强制重建，默认 false
    """
    force: bool = bool(body.get("force", False))

    async def _run_rebuild():
        from src.brain.rag.auto_build import ensure_knowledge_base
        return ensure_knowledge_base(force_rebuild=force)

    task = asyncio.create_task(_run_rebuild())
    # 给一点启动时间，返回已接受状态
    await asyncio.sleep(0)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"message": "重建任务已启动，后台执行中", "force": force},
    )


@router.get("/stats", summary="知识库详细统计")
async def get_knowledge_stats(
    current_user: User = Depends(get_current_user),
):
    """返回 chunks 数量、文档数量、索引类型等详细信息。"""
    from src.brain.rag.auto_build import get_rag_config_path
    from src.brain.rag.config import load_rag_config
    from src.brain.rag.pipeline import read_jsonl

    config_path = get_rag_config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="RAG 配置文件不存在")

    config = load_rag_config(config_path)
    docs = read_jsonl(config.paths.raw_documents)
    chunks = read_jsonl(config.paths.chunks)

    # 分类统计
    cat_counts: dict[str, int] = {}
    for c in chunks:
        cat = c.get("category", "unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    return {
        "document_count": len(docs),
        "chunk_count": len(chunks),
        "category_breakdown": cat_counts,
        "backend": config.index.backend,
        "chunk_size": config.index.chunk_size,
        "chunk_overlap": config.index.chunk_overlap,
        "index_dir": str(config.paths.index_dir),
    }


@router.post("/sync/external/once", summary="触发一次外部诈骗案例自动采集并增量入库")
async def sync_external_cases_once(
    body: dict | None = None,
    current_user: User = Depends(get_current_user),
):
    """
    手动触发一次外部案例同步流程。

    Request body:
        source_names (list[str], optional): 仅同步指定来源
        dry_run (bool, optional): 仅采集+清洗+去重，不写入向量库
    """
    payload = body or {}
    requested_sources = payload.get("source_names") or payload.get("sources")
    if requested_sources is not None and not isinstance(requested_sources, list):
        raise HTTPException(status_code=422, detail="source_names 必须是字符串数组")

    dry_run = bool(payload.get("dry_run", False))
    result = await sync_external_case_sources(
        source_names=requested_sources,
        dry_run=dry_run,
    )

    if result.get("status") == "config_not_found":
        raise HTTPException(status_code=404, detail="外部采集配置文件不存在")

    if result.get("status") == "disabled":
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=result,
        )

    if result.get("status") == "no_sources":
        raise HTTPException(status_code=422, detail="外部采集配置中未定义 sources")

    return result


@router.get("/sync/external/status", summary="查看外部诈骗案例自动同步状态")
async def get_external_sync_status(
    current_user: User = Depends(get_current_user),
):
    """返回自动同步开关、周期、数据源与最近执行状态。"""
    status_payload = get_external_case_sync_status()
    if status_payload.get("status") == "config_not_found":
        raise HTTPException(status_code=404, detail="外部采集配置文件不存在")
    return status_payload
