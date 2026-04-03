"""
RAG 知识库自动构建
在应用启动或首次检索前，自动检查并构建索引。
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.brain.rag.config import RAGConfig, load_rag_config
from src.brain.rag.pipeline import KnowledgePipeline


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RAG_CONFIG_PATH = _PROJECT_ROOT / "config" / "rag.yaml"
_METADATA_FILENAME = "auto_build_meta.json"
_BUILD_LOCK = threading.Lock()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_rag_config_path(config_path: str | Path | None = None) -> Path:
    if config_path:
        path = Path(config_path).expanduser()
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path.resolve()

    from_env = os.getenv("RAG_CONFIG_PATH", "").strip()
    if from_env:
        env_path = Path(from_env).expanduser()
        if not env_path.is_absolute():
            env_path = _PROJECT_ROOT / env_path
        return env_path.resolve()

    return _DEFAULT_RAG_CONFIG_PATH


def _required_index_file(config: RAGConfig) -> Path:
    if config.index.backend == "sentence-transformer":
        return config.paths.index_dir / "dense.joblib"
    return config.paths.index_dir / "tfidf.joblib"


def _index_ready(config: RAGConfig) -> bool:
    index_dir = config.paths.index_dir
    if not index_dir.exists():
        return False

    required = [
        index_dir / "manifest.json",
        index_dir / "chunks.jsonl",
        _required_index_file(config),
    ]
    return all(path.exists() for path in required)


def _run_coro_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_holder: dict[str, Any] = {}
    error_holder: dict[str, BaseException] = {}

    def _worker() -> None:
        try:
            result_holder["result"] = asyncio.run(coro)
        except BaseException as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder.get("result")


def _write_metadata(config: RAGConfig, payload: dict[str, Any]) -> None:
    config.paths.index_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = config.paths.index_dir / _METADATA_FILENAME
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_knowledge_base(
    config_path: str | Path | None = None,
    *,
    force_rebuild: bool = False,
) -> dict[str, Any]:
    """
    检查并自动构建 RAG 知识库。

    Returns:
        包含状态与索引路径的字典。
    """
    resolved_config = get_rag_config_path(config_path)
    result: dict[str, Any] = {
        "config_path": str(resolved_config),
        "built": False,
        "status": "unknown",
    }

    if not resolved_config.exists():
        result["status"] = "config_not_found"
        result["message"] = "RAG 配置文件不存在，已跳过自动构建"
        return result

    auto_build_enabled = _is_truthy(os.getenv("RAG_AUTO_BUILD"), default=True)
    env_force_rebuild = _is_truthy(os.getenv("RAG_FORCE_REBUILD"), default=False)
    should_force = force_rebuild or env_force_rebuild

    config = load_rag_config(resolved_config)
    result["index_dir"] = str(config.paths.index_dir)

    if _index_ready(config) and not should_force:
        result["status"] = "ready"
        result["message"] = "检测到可用索引，跳过构建"
        return result

    if not auto_build_enabled and not should_force:
        result["status"] = "disabled"
        result["message"] = "RAG_AUTO_BUILD 已禁用，未执行自动构建"
        return result

    with _BUILD_LOCK:
        # 加锁后再次检查，避免并发重复构建。
        if _index_ready(config) and not should_force:
            result["status"] = "ready"
            result["message"] = "索引已由其他进程构建完成"
            return result

        pipeline = KnowledgePipeline(config)
        try:
            stats = _run_coro_sync(pipeline.build_all(backend=config.index.backend))
        except Exception as exc:
            if _index_ready(config):
                result["status"] = "stale_ready"
                result["message"] = f"自动构建失败，但已有历史索引可用: {exc}"
                result["error"] = str(exc)
                return result

            result["status"] = "failed"
            result["message"] = f"自动构建失败且无可用索引: {exc}"
            result["error"] = str(exc)
            return result

        metadata = {
            "updated_at": _iso_now(),
            "config_path": str(resolved_config),
            "backend": config.index.backend,
            "stats": stats,
        }
        _write_metadata(config, metadata)

        result["built"] = True
        result["status"] = "built"
        result["stats"] = stats
        result["message"] = "RAG 知识库自动构建完成"
        return result
