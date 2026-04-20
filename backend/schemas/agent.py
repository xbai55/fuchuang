from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Agent chat request."""

    message: str = Field(..., description="User message")
    language: str = Field("zh-CN", description="UI language")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class AgentChatResponse(BaseModel):
    """Agent chat response."""

    message: str = Field(..., description="Agent response")
    suggestions: List[str] = Field(default_factory=list, description="Suggested follow-up prompts")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tool call records")
    conversation_id: str = Field(..., description="Conversation ID")
