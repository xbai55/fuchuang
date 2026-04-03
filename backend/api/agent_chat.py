import asyncio
import json
import sys
import os
from time import perf_counter
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from auth import decode_token, get_current_active_user
from database import ChatHistory, SessionLocal, get_db, User
from graph_core.task_manager import TaskStatus, task_manager
from schemas.agent import AgentChatRequest
from schemas.response import success_response, error_response, ResponseCode

from src.evolution.monitoring_service import monitoring_service

# 添加 src 到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

try:
    from agents.coze_agent import CozeAgent
except ImportError as e:
    print(f"[警告] Agent 模块导入失败：{e}")
    CozeAgent = None

router = APIRouter()
AGENT_HISTORY_SCAM_TYPE = "agent_chat"


def _normalize_agent_payload(
    payload: Optional[dict[str, Any]],
    fallback_conversation_id: Optional[str],
    user_id: int,
) -> dict[str, Any]:
    data = payload or {}

    message = str(data.get("message") or "").strip()
    suggestions_raw = data.get("suggestions")
    tool_calls_raw = data.get("tool_calls")
    conversation_id_raw = data.get("conversation_id")

    suggestions = suggestions_raw if isinstance(suggestions_raw, list) else []
    tool_calls = tool_calls_raw if isinstance(tool_calls_raw, list) else []
    conversation_id = str(conversation_id_raw or fallback_conversation_id or f"conv_{user_id}")

    return {
        "message": message,
        "suggestions": suggestions,
        "tool_calls": tool_calls,
        "conversation_id": conversation_id,
    }


def _chunk_agent_message(message: str, chunk_size: int = 90) -> list[str]:
    normalized = (message or "").replace("\r\n", "\n")
    if not normalized:
        return []

    return [normalized[index:index + chunk_size] for index in range(0, len(normalized), chunk_size)]


def _get_ws_user(token: Optional[str]) -> Optional[User]:
    if not token:
        return None

    token_data = decode_token(token, token_type="access")
    if token_data is None or token_data.user_id is None:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == token_data.user_id).first()
        if not user or not user.is_active:
            return None
        return user
    finally:
        db.close()

@router.post("/chat")
async def agent_chat(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Agent 聊天接口
    支持多轮对话、工具调用、上下文记忆
    """
    if CozeAgent is None:
        try:
            await monitoring_service.record_request(
                model_name="agent_chat",
                latency_ms=0.0,
                success=False,
                error="Agent module unavailable",
                context={"endpoint": "/api/agent/chat"},
            )
        except Exception as monitor_error:
            print(f"[监控警告] 记录 Agent 指标失败: {monitor_error}")

        raise HTTPException(
            status_code=503,
            detail="Agent 服务暂时不可用"
        )

    started_at = perf_counter()
    request_success = False
    error_message = None

    try:
        agent = CozeAgent(
            user_id=current_user.id,
            user_role=current_user.user_role
        )

        response = await agent.chat(
            message=request.message,
            conversation_id=request.conversation_id,
            context=request.context
        )

        response_payload = _normalize_agent_payload(
            response,
            request.conversation_id,
            current_user.id,
        )

        db.add(
            ChatHistory(
                user_id=current_user.id,
                user_message=request.message,
                bot_response=response_payload.get("message", ""),
                risk_score=0,
                risk_level="low",
                scam_type=AGENT_HISTORY_SCAM_TYPE,
                guardian_alert=False,
            )
        )
        db.commit()

        request_success = True

        return success_response(
            data=response_payload
        )

    except Exception as e:
        error_message = str(e)
        return error_response(
            ResponseCode.INTERNAL_ERROR,
            f"Agent 聊天失败：{str(e)}"
        )

    finally:
        latency_ms = (perf_counter() - started_at) * 1000
        try:
            await monitoring_service.record_request(
                model_name="agent_chat",
                latency_ms=latency_ms,
                success=request_success,
                error=error_message,
                context={"endpoint": "/api/agent/chat"},
            )
        except Exception as monitor_error:
            print(f"[监控警告] 记录 Agent 指标失败: {monitor_error}")


@router.post("/chat-async")
async def agent_chat_async(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Agent 异步聊天接口。
    返回 task_id，由前端通过 WebSocket 流式获取回复。
    """
    if CozeAgent is None:
        return error_response(ResponseCode.SERVICE_UNAVAILABLE, "Agent 服务暂时不可用")

    task = None
    try:
        input_summary = (request.message or "").strip()[:80] or "agent-chat"
        task = task_manager.create_task(user_id=current_user.id, input_summary=input_summary)
        task_manager.update_task_progress(task.task_id, 5)

        user_id = current_user.id
        user_role = current_user.user_role
        request_message = request.message
        request_context = request.context
        request_conversation_id = request.conversation_id

        async def process_agent_chat() -> None:
            db_session = SessionLocal()
            started_at = perf_counter()
            request_success = False
            error_message = None

            try:
                task_manager.update_task_progress(task.task_id, 20)
                agent = CozeAgent(user_id=user_id, user_role=user_role)
                task_manager.publish_task_event(task.task_id, {"event": "agent_stream_started"})
                task_manager.update_task_progress(task.task_id, 35)

                streamed_chunks = 0
                final_payload: Optional[dict[str, Any]] = None

                async for event in agent.stream_chat(
                    message=request_message,
                    conversation_id=request_conversation_id,
                    context=request_context,
                ):
                    event_name = str(event.get("event") or "")

                    if event_name == "agent_chunk":
                        chunk = str(event.get("chunk") or "")
                        if not chunk:
                            continue

                        streamed_chunks += 1
                        task_manager.publish_task_event(
                            task.task_id,
                            {
                                "event": "agent_chunk",
                                "chunk": chunk,
                                "chunk_index": streamed_chunks,
                            },
                        )
                        task_manager.update_task_progress(task.task_id, min(92, 35 + streamed_chunks))
                        continue

                    if event_name == "agent_completed":
                        completed_data = event.get("data")
                        if isinstance(completed_data, dict):
                            final_payload = _normalize_agent_payload(
                                completed_data,
                                request_conversation_id,
                                user_id,
                            )

                if final_payload is None:
                    raise RuntimeError("Agent 异步流未返回有效结果")

                if streamed_chunks == 0:
                    fallback_chunks = _chunk_agent_message(final_payload.get("message", ""))
                    for index, chunk in enumerate(fallback_chunks, start=1):
                        task_manager.publish_task_event(
                            task.task_id,
                            {
                                "event": "agent_chunk",
                                "chunk": chunk,
                                "chunk_index": index,
                            },
                        )
                        task_manager.update_task_progress(task.task_id, min(92, 35 + index))
                        if index < len(fallback_chunks):
                            await asyncio.sleep(0.015)
                    streamed_chunks = len(fallback_chunks)

                task_manager.publish_task_event(
                    task.task_id,
                    {
                        "event": "agent_stream_finished",
                        "total_chunks": streamed_chunks,
                    },
                )
                task_manager.update_task_progress(task.task_id, 97)
                task_manager.complete_task(task.task_id, final_payload)

                db_session.add(
                    ChatHistory(
                        user_id=user_id,
                        user_message=request_message,
                        bot_response=final_payload.get("message", ""),
                        risk_score=0,
                        risk_level="low",
                        scam_type=AGENT_HISTORY_SCAM_TYPE,
                        guardian_alert=False,
                    )
                )
                db_session.commit()

                request_success = True

            except Exception as exc:
                error_message = str(exc)
                db_session.rollback()
                task_manager.fail_task(task.task_id, error_message)

            finally:
                db_session.close()
                latency_ms = (perf_counter() - started_at) * 1000
                try:
                    await monitoring_service.record_request(
                        model_name="agent_chat",
                        latency_ms=latency_ms,
                        success=request_success,
                        error=error_message,
                        context={"endpoint": "/api/agent/chat-async", "mode": "async"},
                    )
                except Exception as monitor_error:
                    print(f"[监控警告] 记录 Agent 指标失败: {monitor_error}")

        asyncio.create_task(process_agent_chat())

        return success_response(
            data={
                "task_id": task.task_id,
                "status": task.status.value,
                "estimated_time": 4,
                "poll_url": f"/api/agent/tasks/{task.task_id}",
                "ws_url": f"/api/agent/ws/tasks/{task.task_id}",
            },
            message="Agent 异步聊天已开始",
        )
    except Exception as exc:
        if task is not None:
            task_manager.fail_task(task.task_id, str(exc))
        return error_response(ResponseCode.INTERNAL_ERROR, f"Agent 异步聊天启动失败：{exc}")


@router.get("/tasks/{task_id}")
async def get_agent_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
):
    task = task_manager.get_task(task_id)
    if not task:
        return error_response(ResponseCode.TASK_NOT_FOUND, "任务不存在")
    if task.user_id != current_user.id:
        return error_response(ResponseCode.FORBIDDEN, "无权查看该任务")
    return success_response(data=task.to_dict())


@router.get("/tasks")
async def get_agent_user_tasks(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    return success_response(data=task_manager.get_user_tasks(current_user.id, limit))


@router.websocket("/ws/tasks/{task_id}")
async def agent_task_updates_ws(websocket: WebSocket, task_id: str):
    token = websocket.query_params.get("token")
    user = _get_ws_user(token)
    if user is None:
        await websocket.close(code=1008, reason="invalid token")
        return

    await websocket.accept()
    task = task_manager.get_task(task_id)
    if task is None:
        await websocket.send_json({"event": "error", "task_id": task_id, "message": "任务不存在"})
        await websocket.close(code=1008)
        return
    if task.user_id != user.id:
        await websocket.send_json({"event": "error", "task_id": task_id, "message": "无权查看该任务"})
        await websocket.close(code=1008)
        return

    terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT}
    last_snapshot = ""
    last_event_seq = 0
    try:
        await websocket.send_json({"event": "connected", "task_id": task_id, "task": task.to_dict()})
        while True:
            current_task = task_manager.get_task(task_id)
            if current_task is None:
                await websocket.send_json({"event": "error", "task_id": task_id, "message": "任务已失效"})
                await websocket.close(code=1000)
                break

            snapshot = current_task.to_dict()
            snapshot_key = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
            if snapshot_key != last_snapshot:
                await websocket.send_json({"event": "task_update", "task_id": task_id, "task": snapshot})
                last_snapshot = snapshot_key

            pending_events = task_manager.get_task_events(task_id, after_seq=last_event_seq)
            for item in pending_events:
                last_event_seq = max(last_event_seq, int(item.get("seq", 0)))
                event_name = item.get("event", "task_event")
                event_payload = {k: v for k, v in item.items() if k != "event"}
                await websocket.send_json({"event": event_name, "task_id": task_id, **event_payload})

            if current_task.status in terminal_statuses:
                event_name = "task_completed" if current_task.status == TaskStatus.COMPLETED else "task_failed"
                await websocket.send_json(
                    {
                        "event": event_name,
                        "task_id": task_id,
                        "task": snapshot,
                        "result": current_task.result,
                        "error": current_task.error,
                    }
                )
                await websocket.close(code=1000)
                break

            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return

@router.get("/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取指定对话的历史记录"""
    # TODO: 实现从数据库加载对话历史
    return {
        "conversation_id": conversation_id,
        "messages": [],
        "user_id": current_user.id
    }
