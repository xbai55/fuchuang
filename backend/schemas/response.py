"""
统一响应模型
提供标准化的 API 响应格式
"""
from typing import Any, Optional, TypeVar, Generic
from pydantic import BaseModel
from datetime import datetime
import time

T = TypeVar('T')


class ResponseCode:
    """响应状态码"""
    SUCCESS = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    TOO_MANY_REQUESTS = 429
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503

    # 业务状态码 4000-4999
    TOKEN_EXPIRED = 4001
    TOKEN_INVALID = 4002
    USER_EXISTS = 4003
    USER_NOT_FOUND = 4004
    PASSWORD_ERROR = 4005
    TASK_NOT_FOUND = 4006
    TASK_PROCESSING = 4007
    FILE_TOO_LARGE = 4008
    INVALID_FILE_TYPE = 4009
    PARAM_ERROR = 4010


class UnifiedResponse(BaseModel, Generic[T]):
    """统一响应模型"""
    code: int = ResponseCode.SUCCESS
    message: str = "success"
    data: Optional[T] = None
    timestamp: int = 0
    request_id: Optional[str] = None

    class Config:
        from_attributes = True


def success_response(data: Any = None, message: str = "success", request_id: str = None) -> dict:
    """成功响应"""
    return {
        "code": ResponseCode.SUCCESS,
        "message": message,
        "data": data,
        "timestamp": int(time.time()),
        "request_id": request_id
    }


def error_response(code: int, message: str, request_id: str = None) -> dict:
    """错误响应"""
    return {
        "code": code,
        "message": message,
        "data": None,
        "timestamp": int(time.time()),
        "request_id": request_id
    }


class PaginationData(BaseModel, Generic[T]):
    """分页数据模型"""
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


def paginate_response(items: list, total: int, page: int, size: int, request_id: str = None) -> dict:
    """分页响应"""
    pages = (total + size - 1) // size
    return {
        "code": ResponseCode.SUCCESS,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1
        },
        "timestamp": int(time.time()),
        "request_id": request_id
    }
