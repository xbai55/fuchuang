from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from sqlalchemy.orm import Session
from database import get_db, User, ChatHistory
from schemas import FraudDetectionRequest, FraudDetectionResponse
from auth import get_current_active_user
from typing import Optional

from graph_core.graph_client import graph_client
from graph_core.task_manager import task_manager, TaskStatus
from schemas.response import (
    success_response, error_response, paginate_response,
    ResponseCode
)
import asyncio
import tempfile
import uuid
import os
from pathlib import Path

router = APIRouter()

# ==================== 诊断标记 ====================
print("【诊断】fraud_detection.py 已加载")
print("【诊断】fraud_detection router 路径列表：")
print("  - /detect (POST)")
print("  - /detect-async (POST)")
print("  - /tasks/{task_id} (GET)")
print("  - /tasks (GET)")
print("  - /history (OPTIONS, GET)")
print("="*60)

# 响应头装饰器 - 确保所有响应都包含 CORS 头
def add_cors_headers(func):
    """为路由处理函数添加 CORS 响应头的装饰器"""
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        # 注意：实际的 CORS 头由中间件处理，这里只是备用
        return result
    return wrapper


def _save_temp_file(upload_file: UploadFile) -> str:
    """Helper to save uploaded file to temp location."""
    temp_dir = tempfile.gettempdir()
    suffix = Path(upload_file.filename).suffix if upload_file.filename else ""
    temp_filename = f"{uuid.uuid4().hex}{suffix}"
    temp_path = os.path.join(temp_dir, temp_filename)

    with open(temp_path, "wb") as f:
        f.write(upload_file.file.read())

    # 重置文件指针，以便后续可能需要的读取操作
    upload_file.file.seek(0)

    return temp_path


@router.post("/detect")
async def detect_fraud(
    message: str = Form(...),
    audio_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    反诈预警检测 - 支持多模态输入（文本/语音/图片/视频）
    同步接口，适合小文件快速检测
    """
    temp_files = []

    try:
        # Save uploaded files to temp locations
        audio_path = _save_temp_file(audio_file) if audio_file else None
        image_path = _save_temp_file(image_file) if image_file else None
        video_path = _save_temp_file(video_file) if video_file else None

        temp_files = [p for p in [audio_path, image_path, video_path] if p]

        # Run fraud detection using graph client
        result = await graph_client.detect_fraud(
            text=message,
            audio_path=audio_path,
            image_path=image_path,
            video_path=video_path,
            user_role=current_user.user_role,
            guardian_name=current_user.guardian_name,
            user_id=str(current_user.id),
        )

        # Save chat history
        chat_history = ChatHistory(
            user_id=current_user.id,
            user_message=message,
            bot_response=result.get("warning_message", ""),
            risk_score=result.get("risk_score", 0),
            risk_level=result.get("risk_level", "low"),
            scam_type=result.get("scam_type", ""),
            guardian_alert=result.get("guardian_alert", False)
        )

        db.add(chat_history)
        db.commit()

        # Return detection result with unified response format
        return success_response(
            data={
                "risk_score": result.get("risk_score", 0),
                "risk_level": result.get("risk_level", "low"),
                "scam_type": result.get("scam_type", ""),
                "warning_message": result.get("warning_message", ""),
                "final_report": result.get("final_report", ""),
                "guardian_alert": result.get("guardian_alert", False)
            },
            message="检测完成"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"反诈检测失败：{str(e)}"
        )

    finally:
        # Clean up temp files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"[警告] 清理临时文件失败: {e}")


@router.post("/detect-async")
async def detect_fraud_async(
    message: str = Form(...),
    audio_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    异步反诈检测接口
    适合大文件或复杂分析，返回 task_id 用于轮询状态
    """
    temp_files = []

    try:
        # Create async task
        input_summary = message[:50] if message else "文件分析"
        if audio_file:
            input_summary += f" [音频:{audio_file.filename}]"
        if image_file:
            input_summary += f" [图片:{image_file.filename}]"
        if video_file:
            input_summary += f" [视频:{video_file.filename}]"

        task = task_manager.create_task(
            user_id=current_user.id,
            input_summary=input_summary
        )

        # Save uploaded files
        audio_path = _save_temp_file(audio_file) if audio_file else None
        image_path = _save_temp_file(image_file) if image_file else None
        video_path = _save_temp_file(video_file) if video_file else None

        temp_files = [p for p in [audio_path, image_path, video_path] if p]

        # Define async task
        async def process_and_cleanup():
            try:
                # Execute fraud detection
                result = await graph_client.detect_fraud(
                    text=message,
                    audio_path=audio_path,
                    image_path=image_path,
                    video_path=video_path,
                    user_role=current_user.user_role,
                    guardian_name=current_user.guardian_name,
                    user_id=str(current_user.id),
                )

                # Update task with result
                task_manager.complete_task(task.task_id, result)

                # Save to database
                chat_history = ChatHistory(
                    user_id=current_user.id,
                    user_message=message,
                    bot_response=result.get("warning_message", ""),
                    risk_score=result.get("risk_score", 0),
                    risk_level=result.get("risk_level", "low"),
                    scam_type=result.get("scam_type", ""),
                    guardian_alert=result.get("guardian_alert", False)
                )
                db.add(chat_history)
                db.commit()

            except Exception as e:
                task_manager.fail_task(task.task_id, str(e))
                raise

            finally:
                # Clean up temp files
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception as e:
                        print(f"[警告] 清理临时文件失败: {e}")

        # Start async task
        asyncio.create_task(process_and_cleanup())

        # Return task info immediately
        return success_response(
            data={
                "task_id": task.task_id,
                "status": task.status.value,
                "estimated_time": 5 if not video_file else 15,
                "poll_url": f"/api/v1/tasks/{task.task_id}"
            },
            message="任务已创建，请使用 task_id 轮询查询结果"
        )

    except Exception as e:
        # Clean up on failure
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

        return error_response(
            ResponseCode.INTERNAL_ERROR,
            f"创建异步任务失败：{str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    查询异步任务状态
    """
    task = task_manager.get_task(task_id)

    if not task:
        return error_response(ResponseCode.TASK_NOT_FOUND, "任务不存在")

    # 验证任务归属
    if task.user_id != current_user.id:
        return error_response(ResponseCode.FORBIDDEN, "无权访问此任务")

    return success_response(data=task.to_dict())


@router.get("/tasks")
async def get_user_tasks(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前用户的任务列表
    """
    tasks = task_manager.get_user_tasks(current_user.id, limit)
    return success_response(data=tasks)


@router.options("/history")
async def options_history():
    """
    OPTIONS 预检请求处理
    原因：浏览器发送 CORS 预检请求时需要返回 200
    """
    return {"ok": True}


@router.get("/history")
async def get_chat_history(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    test: bool = Query(False, description="测试模式（返回简单响应）"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取聊天历史 - 支持分页
    """
    # 任务 4：测试模式 - 临时返回简单 JSON 用于验证 CORS
    if test:
        return success_response(
            data={"ok": True, "cors_test": "success"},
            message="CORS 测试响应"
        )

    # 计算偏移量
    offset = (page - 1) * size

    # 查询总数
    total = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user.id
    ).count()

    # 查询分页数据
    history = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user.id
    ).order_by(ChatHistory.created_at.desc()).offset(offset).limit(size).all()

    items = [
        {
            "id": h.id,
            "user_message": h.user_message,
            "bot_response": h.bot_response,
            "risk_score": h.risk_score,
            "risk_level": h.risk_level,
            "scam_type": h.scam_type,
            "guardian_alert": h.guardian_alert,
            "created_at": h.created_at.isoformat()
        }
        for h in history
    ]

    return paginate_response(items, total, page, size)
