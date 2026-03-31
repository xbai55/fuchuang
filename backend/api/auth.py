from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from database import get_db, User
from schemas import UserCreate, UserResponse
from schemas.response import success_response, error_response, ResponseCode
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_active_user,
    create_token_pair,
    refresh_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter()


@router.post("/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        return error_response(ResponseCode.USER_EXISTS, "用户名已被注册")

    # 检查邮箱是否已存在
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        return error_response(ResponseCode.USER_EXISTS, "邮箱已被注册")

    # 创建新用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 生成 Token 对
    access_token, refresh_token = create_token_pair(new_user.id)

    return success_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": UserResponse(
                id=new_user.id,
                username=new_user.username,
                email=new_user.email,
                user_role=new_user.user_role,
                guardian_name=new_user.guardian_name,
                theme=new_user.theme,
                notify_enabled=new_user.notify_enabled,
                notify_high_risk=new_user.notify_high_risk,
                notify_guardian_alert=new_user.notify_guardian_alert,
                language=new_user.language,
                font_size=new_user.font_size,
                privacy_mode=new_user.privacy_mode,
            )
        },
        message="注册成功"
    )


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录"""
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        return error_response(ResponseCode.PASSWORD_ERROR, "用户名或密码错误")

    # 生成 Token 对
    access_token, refresh_token = create_token_pair(user.id)

    return success_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_expires_in": REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "user": UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                user_role=user.user_role,
                guardian_name=user.guardian_name,
                theme=user.theme,
                notify_enabled=user.notify_enabled,
                notify_high_risk=user.notify_high_risk,
                notify_guardian_alert=user.notify_guardian_alert,
                language=user.language,
                font_size=user.font_size,
                privacy_mode=user.privacy_mode,
            )
        },
        message="登录成功"
    )


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    刷新 Token
    使用 refresh_token 获取新的 access_token 和 refresh_token
    """
    result = await refresh_access_token(refresh_token, db)

    if result is None:
        return error_response(ResponseCode.TOKEN_INVALID, "刷新令牌无效或已过期")

    new_access_token, new_refresh_token = result

    return success_response(
        data={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_expires_in": REFRESH_TOKEN_EXPIRE_DAYS * 86400
        },
        message="Token 刷新成功"
    )


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return success_response(
        data=UserResponse(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            user_role=current_user.user_role,
            guardian_name=current_user.guardian_name,
            theme=current_user.theme,
            notify_enabled=current_user.notify_enabled,
            notify_high_risk=current_user.notify_high_risk,
            notify_guardian_alert=current_user.notify_guardian_alert,
            language=current_user.language,
            font_size=current_user.font_size,
            privacy_mode=current_user.privacy_mode,
        )
    )


@router.put("/me")
async def update_user_profile(
    user_role: str = None,
    guardian_name: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新用户信息"""
    if user_role is not None:
        current_user.user_role = user_role
    if guardian_name is not None:
        current_user.guardian_name = guardian_name

    db.commit()
    db.refresh(current_user)

    return success_response(
        data=UserResponse(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            user_role=current_user.user_role,
            guardian_name=current_user.guardian_name,
            theme=current_user.theme,
            notify_enabled=current_user.notify_enabled,
            notify_high_risk=current_user.notify_high_risk,
            notify_guardian_alert=current_user.notify_guardian_alert,
            language=current_user.language,
            font_size=current_user.font_size,
            privacy_mode=current_user.privacy_mode,
        ),
        message="更新成功"
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """
    用户登出
    客户端需要清除本地存储的 token
    服务端可在此实现 Token 黑名单（如果需要）
    """
    # TODO: 如果需要实现服务端登出，可以将 token 加入黑名单
    return success_response(message="登出成功")
