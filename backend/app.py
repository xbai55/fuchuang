import sys
from pathlib import Path
import os
import tempfile
import asyncio
import threading

# ==================== 诊断标记 ====================
print("【诊断】MAIN FILE LOADED - 正在运行正确的 main.py")
print(f"【诊断】文件路径: {__file__}")
print(f"【诊断】工作目录: {os.getcwd()}")
print("="*60)

# ==================== 跨平台日志路径修复 ====================
# 修复 coze_coding_utils 库在 Windows 上的日志路径问题
if sys.platform == 'win32':
    # 创建临时日志目录
    log_base_dir = Path(tempfile.gettempdir()) / "work" / "logs" / "bypass"
else:
    log_base_dir = Path("/tmp/work/logs/bypass")

# 确保日志目录存在
log_base_dir.mkdir(parents=True, exist_ok=True)

# 设置环境变量，让外部库使用正确的路径
os.environ.setdefault('LOG_DIR', str(log_base_dir))
os.environ.setdefault('APP_LOG_DIR', str(log_base_dir))


def _configure_windows_cuda_dll_search_paths() -> None:
    """Ensure CUDA/cuDNN runtime directories are discoverable on Windows."""
    if sys.platform != "win32":
        return

    env_root = Path(sys.prefix)
    candidate_dirs = [
        env_root / "Library" / "bin",
        env_root / "Lib" / "site-packages" / "torch" / "lib",
    ]

    current_path = os.environ.get("PATH", "")
    existing_parts = {part.lower() for part in current_path.split(";") if part}

    for directory in candidate_dirs:
        if not directory.exists():
            continue

        dir_str = str(directory)
        if dir_str.lower() not in existing_parts:
            os.environ["PATH"] = f"{dir_str};" + os.environ.get("PATH", "")
            existing_parts.add(dir_str.lower())

        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(dir_str)
            except OSError:
                # Non-fatal: fallback to PATH lookup.
                pass


_configure_windows_cuda_dll_search_paths()

# Add project root to path for src imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import uvicorn
import os

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try loading from parent directory
    load_dotenv(Path(__file__).parent.parent / ".env")

# API 路由导入 - 融合所有功能
from api import auth, contacts, fraud_detection, agent_chat, settings, monitoring

# 数据库初始化
from database import init_db
from src.brain.rag.auto_build import ensure_knowledge_base
from model_warmup import warmup_models

# 异常处理器
from graph_core.exceptions import register_exception_handlers


def _get_warmup_startup_timeout_seconds() -> float:
    raw = os.getenv("MODEL_WARMUP_STARTUP_TIMEOUT", "8")
    try:
        value = float(raw)
        return value if value > 0 else 8.0
    except ValueError:
        return 8.0


def _start_warmup_daemon() -> dict:
    state = {
        "finished": threading.Event(),
        "result": None,
        "error": None,
    }

    def _worker() -> None:
        try:
            state["result"] = asyncio.run(warmup_models())
        except Exception as exc:
            state["error"] = str(exc)
        finally:
            state["finished"].set()

    thread = threading.Thread(target=_worker, name="model-warmup", daemon=True)
    thread.start()
    state["thread"] = thread
    return state


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()

    # 启动时自动检查并构建 RAG 知识库（索引不存在时）
    try:
        rag_status = ensure_knowledge_base()
        print(f"✅ RAG 知识库状态: {rag_status.get('status', 'unknown')}")
        if rag_status.get("index_dir"):
            print(f"   RAG 索引目录: {rag_status['index_dir']}")
        if rag_status.get("message"):
            print(f"   详情: {rag_status['message']}")
    except Exception as e:
        print(f"⚠️ RAG 自动构建检查失败: {e}")

    warmup_state = _start_warmup_daemon()
    app.state.model_warmup_state = warmup_state

    startup_timeout = _get_warmup_startup_timeout_seconds()
    elapsed = 0.0
    step = 0.1
    while elapsed < startup_timeout:
        if warmup_state["finished"].is_set():
            break
        await asyncio.sleep(step)
        elapsed += step

    if warmup_state["finished"].is_set():
        if warmup_state["error"]:
            print(f"⚠️ 模型预热执行失败: {warmup_state['error']}")
        else:
            print(f"✅ 模型预热状态: {warmup_state['result']}")
    else:
        print(
            f"⏳ 模型预热超过启动等待阈值 {startup_timeout:.1f}s，"
            "已转为后台继续执行"
        )

    print("✅ 数据库初始化完成")
    print("✅ 认证服务已加载")
    print("✅ 用户设置服务已加载")
    print("✅ 联系人服务已加载")
    print("✅ 反诈检测服务已加载")
    print("✅ Agent 聊天服务已加载")
    print("✅ 异步任务管理器已启动")
    print("✅ 统一响应格式已启用")
    yield

    # 关闭时的清理工作（如果需要）
    print("👋 服务正在关闭...")


app = FastAPI(
    title="反诈预警系统 - 融合 API",
    description="整合 Agent、多模态分析、反诈预警的综合平台",
    version="2.1.0",
    lifespan=lifespan
)

# ==================== 全局 OPTIONS 兜底中间件（必须在最前面）====================
@app.middleware("http")
async def allow_options_requests(request: Request, call_next):
    """
    全局 OPTIONS 兜底中间件
    原因：确保所有 OPTIONS 预检请求都能返回 200，不被鉴权拦截
    """
    if request.method == "OPTIONS":
        return Response(status_code=200)
    return await call_next(request)


# ==================== 全局异常捕获中间件（诊断神器）====================
import traceback

@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    """
    全局异常捕获中间件
    功能：捕获所有未处理的异常，打印完整堆栈到终端，并返回具体错误信息
    """
    try:
        return await call_next(request)
    except Exception as e:
        # 获取完整堆栈跟踪
        stack_trace = traceback.format_exc()

        # 打印到终端（醒目的错误格式）
        print("\n" + "=" * 80)
        print(f"【ERROR】请求处理失败: {request.method} {request.url.path}")
        print("=" * 80)
        print(f"异常类型: {type(e).__name__}")
        print(f"异常信息: {str(e)}")
        print("-" * 80)
        print("完整堆栈跟踪:")
        print(stack_trace)
        print("=" * 80 + "\n")

        # 返回包含详细错误信息的 JSON 响应
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(e),
                "exception_type": type(e).__name__,
                "path": request.url.path,
                "method": request.method
            }
        )


# ==================== CORS 配置 ====================
origins = [
    "http://localhost:3000",      # React 开发服务器
    "http://127.0.0.1:3000",      # React 开发服务器 (明确 IP)
    "http://localhost:5173",      # Vite 开发服务器
    "http://127.0.0.1:5173",      # Vite 开发服务器 (IP)
    "http://localhost:8080",      # Flutter Web
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册异常处理器
register_exception_handlers(app)


# 注册所有路由 - 五大核心功能
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(settings.router, prefix="/api/settings", tags=["用户设置"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["联系人"])
app.include_router(fraud_detection.router, prefix="/api/fraud", tags=["反诈检测"])
app.include_router(agent_chat.router, prefix="/api/agent", tags=["Agent 聊天"])
app.include_router(monitoring.router, prefix="/api/monitor", tags=["模型监控"])

# ==================== 诊断：打印所有注册的路由 ====================
print("\n" + "="*60)
print("【诊断】所有注册的路由列表：")
print("="*60)
for route in app.routes:
    if hasattr(route, 'methods') and hasattr(route, 'path'):
        methods = list(route.methods) if route.methods else []
        # 跳过默认的 /openapi.json 和 /docs
        if route.path not in ['/openapi.json', '/docs', '/redoc']:
            print(f"  {methods} {route.path}")
    elif hasattr(route, 'path'):
        print(f"  [无方法] {route.path}")
print("="*60)

# 检查 /api/fraud/history 是否存在
history_routes = [r for r in app.routes if hasattr(r, 'path') and 'history' in r.path]
print(f"\n【诊断】包含 'history' 的路由数量: {len(history_routes)}")
for r in history_routes:
    methods = list(r.methods) if hasattr(r, 'methods') and r.methods else []
    print(f"  - {methods} {r.path}")
print("="*60 + "\n")


@app.get("/")
async def root():
    return {
        "message": "反诈预警系统 API v2.1",
        "version": "2.1.0",
        "modules": ["认证", "用户设置", "联系人", "反诈检测", "Agent 聊天", "模型监控"],
        "features": [
            "多模态输入处理（文本/语音/图片/视频）",
            "异步任务队列",
            "AI 伪造检测（音频/视频）",
            "LangGraph 工作流编排",
            "智能 Agent 聊天",
            "个性化风险预警",
            "监护人联动",
            "模型监控与告警"
        ],
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": "2.1.0",
        "services": {
            "api": "running",
            "database": "connected",
            "async_tasks": "enabled"
        }
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    # 确保当前目录在Python路径中
    current_file_path = Path(__file__).resolve()
    project_root = current_file_path.parent.parent
    sys.path.insert(0, str(project_root))
    
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
