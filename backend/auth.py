from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db, User
import os

# ==================== JWT 配置 ====================
# 从环境变量读取密钥，提供默认值仅用于开发
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    print("[警告] 未设置 SECRET_KEY 环境变量，使用默认密钥（生产环境必须设置）")
    SECRET_KEY = "dev-secret-key-change-in-production-32chars-long"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# 密码加密
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)

# OAuth2 密码流
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ==================== Token 模型 ====================
class TokenData:
    """Token 数据"""
    def __init__(self, user_id: Optional[int] = None, token_type: str = "access"):
        self.user_id = user_id
        self.token_type = token_type


# ==================== 密码工具 ====================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    """加密密码"""
    return pwd_context.hash(password)


# ==================== Token 生成 ====================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌（短期）"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow()
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """创建刷新令牌（长期）"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow()
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_token_pair(user_id: int) -> Tuple[str, str]:
    """
    创建 Token 对
    返回: (access_token, refresh_token)
    """
    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)})
    return access_token, refresh_token


# ==================== Token 验证 ====================
def decode_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    解码并验证 Token
    :param token: JWT Token
    :param token_type: 期望的 token 类型 (access/refresh)
    :return: TokenData 或 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 验证 token 类型
        payload_type = payload.get("type", "access")
        if payload_type != token_type:
            return None

        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            return None

        return TokenData(user_id=int(user_id_str), token_type=payload_type)

    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户（验证 Access Token）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(token, token_type="access")
    if token_data is None or token_data.user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user


async def validate_refresh_token(refresh_token: str, db: Session) -> Optional[User]:
    """验证 Refresh Token 并返回用户"""
    token_data = decode_token(refresh_token, token_type="refresh")
    if token_data is None or token_data.user_id is None:
        return None

    user = db.query(User).filter(User.id == token_data.user_id).first()
    return user


# ==================== Token 刷新 ====================
async def refresh_access_token(refresh_token: str, db: Session) -> Optional[Tuple[str, str]]:
    """
    使用 Refresh Token 刷新 Token 对
    返回新的 (access_token, refresh_token) 或 None
    """
    user = await validate_refresh_token(refresh_token, db)
    if user is None:
        return None

    # 每次刷新都生成新的 Token 对（轮换机制增强安全性）
    return create_token_pair(user.id)
