from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, User, ChatHistory
from schemas import FraudDetectionRequest, FraudDetectionResponse
from auth import get_current_active_user
import sys
import os

# 获取 projects 目录并把 src 加到 Python 路径中，方便导入 graphs.graph
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
project_root = os.path.abspath(project_root)
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from graphs.graph import main_graph
from rag.local_rag import get_local_rag
from utils.file.file import File

router = APIRouter()


def _url_to_file(url: str | None, file_type: str) -> File | None:
    """Return File only for real URLs/paths; reject placeholders like 'string'."""
    if not url:
        return None
    if not (url.startswith("http://") or url.startswith("https://") or os.path.isabs(url)):
        return None
    try:
        return File(url=url, file_type=file_type)
    except Exception:
        return None


@router.post("/detect", response_model=FraudDetectionResponse)
async def detect_fraud(
    request: FraudDetectionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    反诈预警检测
    """
    try:
        # 构建工作流输入
        workflow_input = {
            "input_text": request.message,
            "input_audio": _url_to_file(request.audio_url, "audio"),
            "input_image": _url_to_file(request.image_url, "image"),
            "user_role": current_user.user_role,
            "guardian_name": current_user.guardian_name
        }
        
        # 调用工作流
        result = main_graph.invoke(workflow_input)
        
        # 保存聊天历史
        chat_history = ChatHistory(
            user_id=current_user.id,
            user_message=request.message,
            bot_response=result.get("warning_message", ""),
            risk_score=result.get("risk_score", 0),
            risk_level=result.get("risk_level", "low"),
            scam_type=result.get("scam_type", ""),
            guardian_alert=result.get("guardian_alert", False)
        )
        
        db.add(chat_history)
        db.commit()

        # 实时扩充本地 RAG：中/高风险案例写入内存索引，供后续检索即时利用
        if result.get("risk_level") in ("medium", "high") and request.message:
            try:
                get_local_rag().add_case(
                    cleaned_text=f"{request.message} {result.get('scam_type', '')} {result.get('risk_clues', '')}",
                    scam_type=result.get("scam_type", ""),
                    severity="high" if result.get("risk_level") == "high" else "medium",
                )
            except Exception:
                pass

        # 返回检测结果
        return FraudDetectionResponse(
            risk_score=result.get("risk_score", 0),
            risk_level=result.get("risk_level", "low"),
            scam_type=result.get("scam_type", ""),
            warning_message=result.get("warning_message", ""),
            final_report=result.get("final_report", ""),
            guardian_alert=result.get("guardian_alert", False)
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"反诈检测失败: {str(e)}"
        )

@router.get("/history")
async def get_chat_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取聊天历史"""
    history = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user.id
    ).order_by(ChatHistory.created_at.desc()).limit(50).all()
    
    return [
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
