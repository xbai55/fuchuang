from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from database import get_db, User
from schemas import UserCreate, UserResponse, Token
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被注册"
        )
    
    # 检查邮箱是否已存在
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 创建新用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 生成访问令牌
    access_token = create_access_token(
        data={"sub": str(new_user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return Token(
        access_token=access_token,
        user=UserResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            user_role=new_user.user_role,
            guardian_name=new_user.guardian_name
        )
    )

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录"""
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 生成访问令牌
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return Token(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            user_role=user.user_role,
            guardian_name=user.guardian_name
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        user_role=current_user.user_role,
        guardian_name=current_user.guardian_name
    )

@router.put("/me", response_model=UserResponse)
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
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        user_role=current_user.user_role,
        guardian_name=current_user.guardian_name
    )
