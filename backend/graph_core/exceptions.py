"""
全局异常处理
统一处理所有 API 异常并返回标准格式
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import time
import uuid

from schemas.response import error_response, ResponseCode


def generate_request_id() -> str:
    """生成请求 ID"""
    return str(uuid.uuid4())[:12]


async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 HTTP 异常"""
    request_id = generate_request_id()

    # 映射 HTTP 状态码到业务码
    code_mapping = {
        400: ResponseCode.BAD_REQUEST,
        401: ResponseCode.UNAUTHORIZED,
        403: ResponseCode.FORBIDDEN,
        404: ResponseCode.NOT_FOUND,
        429: ResponseCode.TOO_MANY_REQUESTS,
        500: ResponseCode.INTERNAL_ERROR,
        503: ResponseCode.SERVICE_UNAVAILABLE
    }

    code = code_mapping.get(exc.status_code, ResponseCode.INTERNAL_ERROR)

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code, exc.detail, request_id)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数验证异常"""
    request_id = generate_request_id()

    # 提取第一个错误信息
    error_msg = "请求参数错误"
    if exc.errors():
        first_error = exc.errors()[0]
        error_msg = f"{first_error.get('loc', [''])[-1]}: {first_error.get('msg', '参数错误')}"

    return JSONResponse(
        status_code=400,
        content=error_response(ResponseCode.BAD_REQUEST, error_msg, request_id)
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """处理数据库完整性错误（如重复键）"""
    request_id = generate_request_id()

    error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)

    # 判断具体错误类型
    if "UNIQUE constraint failed" in error_msg or "Duplicate entry" in error_msg:
        if "username" in error_msg:
            message = "用户名已被注册"
        elif "email" in error_msg:
            message = "邮箱已被注册"
        else:
            message = "数据已存在"
        code = ResponseCode.USER_EXISTS
    else:
        message = "数据库操作失败"
        code = ResponseCode.INTERNAL_ERROR

    return JSONResponse(
        status_code=400,
        content=error_response(code, message, request_id)
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """处理数据库异常"""
    request_id = generate_request_id()

    # 打印详细错误到终端（诊断用）
    import traceback
    print(f"\n[DB ERROR][{request_id}] SQLAlchemy Error:")
    print(f"  Error Type: {type(exc).__name__}")
    print(f"  Error Message: {str(exc)}")
    print(f"  Traceback:\n{traceback.format_exc()}")
    print("=" * 60)

    return JSONResponse(
        status_code=500,
        content=error_response(
            ResponseCode.INTERNAL_ERROR,
            f"数据库错误: {str(exc)}",  # 返回具体错误信息给前端
            request_id
        )
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """处理通用异常"""
    request_id = generate_request_id()

    # 打印详细错误到终端（诊断用）
    import traceback
    print(f"\n[GENERAL ERROR][{request_id}] Unhandled Exception:")
    print(f"  Request: {request.method} {request.url.path}")
    print(f"  Error Type: {type(exc).__name__}")
    print(f"  Error Message: {str(exc)}")
    print(f"  Traceback:\n{traceback.format_exc()}")
    print("=" * 60)

    return JSONResponse(
        status_code=500,
        content=error_response(
            ResponseCode.INTERNAL_ERROR,
            f"服务器错误: {type(exc).__name__}: {str(exc)}",
            request_id
        )
    )


def register_exception_handlers(app):
    """注册所有异常处理器"""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
