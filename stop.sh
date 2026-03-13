#!/bin/bash

# 反诈预警系统 - 停止脚本

echo "========================================"
echo "反诈预警系统 - 停止中..."
echo "========================================"

# 读取 PID
if [ -f ".backend.pid" ]; then
    BACKEND_PID=$(cat .backend.pid)
    echo "停止后端服务 (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || echo "后端服务未运行"
    rm .backend.pid
else
    echo "后端服务 PID 文件不存在"
fi

if [ -f ".frontend.pid" ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    echo "停止前端服务 (PID: $FRONTEND_PID)..."
    kill $FRONTEND_PID 2>/dev/null || echo "前端服务未运行"
    rm .frontend.pid
else
    echo "前端服务 PID 文件不存在"
fi

# 清理可能的僵尸进程
pkill -f "uvicorn main:app"
pkill -f "vite"

echo ""
echo "✅ 所有服务已停止"
echo "========================================"
