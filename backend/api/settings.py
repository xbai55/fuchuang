from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db, User
from schemas.response import success_response, error_response, ResponseCode
from auth import get_current_active_user, verify_password, get_password_hash

router = APIRouter()


# ==================== 请求模型 ====================
class UserSettingsUpdate(BaseModel):
    """用户设置更新请求"""
    theme: Optional[str] = None
    notify_enabled: Optional[bool] = None
    notify_high_risk: Optional[bool] = None
    notify_guardian_alert: Optional[bool] = None
    language: Optional[str] = None
    font_size: Optional[str] = None
    privacy_mode: Optional[bool] = None


class UserProfileUpdate(BaseModel):
    """用户资料更新请求"""
    username: Optional[str] = None
    email: Optional[str] = None
    user_role: Optional[str] = None
    guardian_name: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    current_password: str
    new_password: str


# ==================== 响应模型 ====================
class UserSettingsResponse(BaseModel):
    """用户设置响应"""
    id: int
    username: str
    email: str
    user_role: str
    guardian_name: str
    theme: str
    notify_enabled: bool
    notify_high_risk: bool
    notify_guardian_alert: bool
    language: str
    font_size: str
    privacy_mode: bool

    class Config:
        from_attributes = True


# ==================== API 端点 ====================
@router.get("/")
async def get_user_settings(
    current_user: User = Depends(get_current_active_user)
):
    """获取用户完整设置"""
    return success_response(
        data={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "user_role": current_user.user_role,
            "guardian_name": current_user.guardian_name,
            "theme": current_user.theme,
            "notify_enabled": current_user.notify_enabled,
            "notify_high_risk": current_user.notify_high_risk,
            "notify_guardian_alert": current_user.notify_guardian_alert,
            "language": current_user.language,
            "font_size": current_user.font_size,
            "privacy_mode": current_user.privacy_mode,
        }
    )


@router.patch("/")
async def update_user_settings(
    settings: UserSettingsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新用户设置（部分更新）"""
    # 验证主题值
    if settings.theme is not None and settings.theme not in ["dark", "light", "system"]:
        return error_response(ResponseCode.PARAM_ERROR, "无效的主题值")

    # 验证语言值
    if settings.language is not None and settings.language not in ["zh-CN", "en-US"]:
        return error_response(ResponseCode.PARAM_ERROR, "无效的语言值")

    # 验证字体大小值
    if settings.font_size is not None and settings.font_size not in ["small", "medium", "large"]:
        return error_response(ResponseCode.PARAM_ERROR, "无效的字体大小值")

    # 更新字段
    update_data = settings.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return success_response(
        data={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "user_role": current_user.user_role,
            "guardian_name": current_user.guardian_name,
            "theme": current_user.theme,
            "notify_enabled": current_user.notify_enabled,
            "notify_high_risk": current_user.notify_high_risk,
            "notify_guardian_alert": current_user.notify_guardian_alert,
            "language": current_user.language,
            "font_size": current_user.font_size,
            "privacy_mode": current_user.privacy_mode,
        },
        message="设置更新成功"
    )


@router.put("/profile")
async def update_user_profile(
    profile: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新用户资料"""
    # 检查用户名是否已被占用
    if profile.username is not None and profile.username != current_user.username:
        existing_user = db.query(User).filter(User.username == profile.username).first()
        if existing_user:
            return error_response(ResponseCode.USER_EXISTS, "用户名已被使用")
        current_user.username = profile.username

    # 检查邮箱是否已被占用
    if profile.email is not None and profile.email != current_user.email:
        existing_email = db.query(User).filter(User.email == profile.email).first()
        if existing_email:
            return error_response(ResponseCode.USER_EXISTS, "邮箱已被使用")
        current_user.email = profile.email

    # 更新其他字段
    if profile.user_role is not None:
        current_user.user_role = profile.user_role
    if profile.guardian_name is not None:
        current_user.guardian_name = profile.guardian_name

    db.commit()
    db.refresh(current_user)

    return success_response(
        data={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "user_role": current_user.user_role,
            "guardian_name": current_user.guardian_name,
        },
        message="资料更新成功"
    )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    # 验证当前密码
    if not verify_password(password_data.current_password, current_user.hashed_password):
        return error_response(ResponseCode.PASSWORD_ERROR, "当前密码错误")

    # 验证新密码长度
    if len(password_data.new_password) < 6:
        return error_response(ResponseCode.PARAM_ERROR, "新密码至少6个字符")

    # 更新密码
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()

    return success_response(message="密码修改成功")


@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """注销账号（软删除）"""
    # 标记用户为非活跃状态（软删除）
    current_user.is_active = False
    db.commit()

    return success_response(message="账号已注销")
