from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# API 路由导入
from api import auth, contacts, fraud_detection

# 数据库初始化
from database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()
    yield
    # 关闭时的清理工作（如果需要）

app = FastAPI(
    title="反诈预警系统 API",
    description="提供用户认证、联系人管理、反诈预警等功能",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # 前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["联系人"])
app.include_router(fraud_detection.router, prefix="/api/fraud", tags=["反诈预警"])

@app.get("/")
async def root():
    return {
        "message": "反诈预警系统 API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
