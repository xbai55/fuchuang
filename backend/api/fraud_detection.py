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

router = APIRouter()

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
            "input_audio": None,
            "input_image": None,
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
