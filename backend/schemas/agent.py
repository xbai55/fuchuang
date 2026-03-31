from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str = Field(..., description="用户消息")
    conversation_id: Optional[str] = Field(None, description="对话 ID（用于多轮对话）")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")

class AgentChatResponse(BaseModel):
    """Agent 聊天响应"""
    message: str = Field(..., description="Agent 回复")
    suggestions: List[str] = Field(default=[], description="建议问题列表")
    tool_calls: List[Dict[str, Any]] = Field(default=[], description="工具调用记录")
    conversation_id: str = Field(..., description="对话 ID")
