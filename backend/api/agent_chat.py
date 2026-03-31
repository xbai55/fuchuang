from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from database import get_db, User
from schemas.agent import AgentChatRequest, AgentChatResponse
from auth import get_current_active_user
from schemas.response import success_response, error_response, ResponseCode
import sys
import os

# 添加 src 到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

try:
    from agents.coze_agent import CozeAgent
except ImportError as e:
    print(f"[警告] Agent 模块导入失败：{e}")
    CozeAgent = None

router = APIRouter()

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
        raise HTTPException(
            status_code=503,
            detail="Agent 服务暂时不可用"
        )
    
    try:
        # 初始化 Agent
        agent = CozeAgent(
            user_id=current_user.id,
            user_role=current_user.user_role
        )
        
        # 调用 Agent
        response = await agent.chat(
            message=request.message,
            conversation_id=request.conversation_id,
            context=request.context
        )

        return success_response(
            data={
                "message": response["message"],
                "suggestions": response.get("suggestions", []),
                "tool_calls": response.get("tool_calls", []),
                "conversation_id": response["conversation_id"]
            }
        )

    except Exception as e:
        return error_response(
            ResponseCode.INTERNAL_ERROR,
            f"Agent 聊天失败：{str(e)}"
        )

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
