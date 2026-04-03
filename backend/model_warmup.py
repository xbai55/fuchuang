"""Startup warmup for LLM and multimodal models."""
import asyncio
import os
from time import perf_counter
from typing import Any, Dict, Optional


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
        if parsed <= 0:
            return default
        return parsed
    except ValueError:
        return default


async def _warmup_llm_client(client: Any, timeout_seconds: float) -> Dict[str, str]:
    if client is None or not hasattr(client, "warmup"):
        return {"status": "skipped", "reason": "unavailable"}

    try:
        ok = await asyncio.wait_for(client.warmup(), timeout=timeout_seconds)
        return {"status": "ok" if ok else "failed"}
    except asyncio.TimeoutError:
        return {"status": "timeout", "reason": f">{timeout_seconds:.1f}s"}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}


async def warmup_models() -> Dict[str, Any]:
    """Warm up graph, multimodal processors, and LLM clients."""
    if not _env_bool("MODEL_WARMUP_ENABLED", True):
        return {
            "enabled": False,
            "steps": {"warmup": {"status": "skipped", "reason": "MODEL_WARMUP_ENABLED=false"}},
            "elapsed_ms": 0,
        }

    started_at = perf_counter()
    llm_timeout_seconds = _env_float("MODEL_WARMUP_LLM_TIMEOUT", 15.0)
    status: Dict[str, Any] = {"enabled": True, "steps": {}}
    graph_components: Dict[str, Any] = {}

    try:
        from src.graphs.graph import get_graph_components, get_main_graph

        get_main_graph()
        graph_components = get_graph_components()
        status["steps"]["graph_compile"] = {"status": "ok"}
    except Exception as exc:
        status["steps"]["graph_compile"] = {"status": "failed", "reason": str(exc)}

    try:
        from src.perception.manager import get_perception_manager

        manager = get_perception_manager()
        await manager.initialize()
        multimodal_detail = await manager.warmup()
        status["steps"]["multimodal"] = {"status": "ok", "detail": multimodal_detail}
    except Exception as exc:
        status["steps"]["multimodal"] = {"status": "failed", "reason": str(exc)}

    if _env_bool("LLM_WARMUP_ENABLED", True):
        risk_node = graph_components.get("risk_assessment")
        intervention_node = graph_components.get("intervention")
        report_node = graph_components.get("report_generation")

        llm_targets = {
            "risk_assessment": getattr(getattr(risk_node, "engine", None), "llm", None),
            "intervention": getattr(getattr(getattr(intervention_node, "service", None), "alert_generator", None), "llm", None),
            "report_generation": getattr(getattr(report_node, "generator", None), "llm", None),
        }

        llm_results = await asyncio.gather(
            *[_warmup_llm_client(client, llm_timeout_seconds) for client in llm_targets.values()],
            return_exceptions=False,
        )

        status["steps"]["workflow_llm"] = {
            "status": "ok",
            "detail": {
                name: result for name, result in zip(llm_targets.keys(), llm_results)
            },
        }

        try:
            from src.agents.coze_agent import warmup_coze_agent_llm

            coze_status = await asyncio.wait_for(
                warmup_coze_agent_llm(),
                timeout=llm_timeout_seconds,
            )
            status["steps"]["agent_llm"] = coze_status
        except asyncio.TimeoutError:
            status["steps"]["agent_llm"] = {
                "status": "timeout",
                "reason": f">{llm_timeout_seconds:.1f}s",
            }
        except Exception as exc:
            status["steps"]["agent_llm"] = {"status": "failed", "reason": str(exc)}
    else:
        status["steps"]["workflow_llm"] = {
            "status": "skipped",
            "reason": "LLM_WARMUP_ENABLED=false",
        }
        status["steps"]["agent_llm"] = {
            "status": "skipped",
            "reason": "LLM_WARMUP_ENABLED=false",
        }

    status["elapsed_ms"] = int((perf_counter() - started_at) * 1000)
    return status
