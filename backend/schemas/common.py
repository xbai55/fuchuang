from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ========== 用户相关 ==========
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    user_role: str = "general"
    guardian_name: str = ""
    # 设置字段
    theme: str = "dark"
    notify_enabled: bool = True
    notify_high_risk: bool = True
    notify_guardian_alert: bool = True
    language: str = "zh-CN"
    font_size: str = "medium"
    privacy_mode: bool = False

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# ========== 联系人相关 ==========
class ContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=11, max_length=20)
    relationship: str = "亲友"
    is_guardian: bool = False

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    relationship: Optional[str] = None
    is_guardian: Optional[bool] = None

class ContactResponse(ContactBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ========== 反诈预警相关 ==========
class FraudDetectionRequest(BaseModel):
    message: str
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None

class FraudDetectionResponse(BaseModel):
    detection_id: Optional[str] = None
    intent: Optional[str] = None
    short_term_memory_summary: Optional[str] = None
    risk_score: int
    risk_level: str
    scam_type: str
    warning_message: str
    final_report: str
    guardian_alert: bool
    alert_reason: Optional[str] = None
    action_items: List[str] = Field(default_factory=list)
    escalation_actions: List[Dict[str, str]] = Field(default_factory=list)
    guardian_notification: Optional[Dict[str, Any]] = None
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    detection_id: str
    feedback_type: str = Field(..., pattern="^(correct|false_positive|false_negative|useful|not_useful)$")
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    success: bool
    feedback_id: str
    timestamp: str
    ingestion: Optional[Dict[str, Any]] = None
    feedback_stats: Dict[str, Any] = Field(default_factory=dict)
