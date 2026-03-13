#!/bin/bash

# 反诈预警系统 - 一键启动脚本

echo "========================================"
echo "反诈预警系统 - 启动中..."
echo "========================================"

# 检查是否安装了必要的依赖
echo ""
echo "检查依赖..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 未安装，请先安装 Python 3.8+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js 18+"
    exit 1
fi

echo "✅ 依赖检查通过"

# 启动后端
echo ""
echo "========================================"
echo "启动后端服务..."
echo "========================================"
cd backend

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "安装后端依赖..."
pip install -r requirements.txt > /dev/null 2>&1

# 启动后端（后台运行）
echo "启动后端服务（端口 8000）..."
nohup python main.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "后端服务 PID: $BACKEND_PID"
cd ..

# 等待后端启动
echo "等待后端服务启动..."
sleep 5

# 启动前端
echo ""
echo "========================================"
echo "启动前端服务..."
echo "========================================"
cd frontend

# 安装依赖
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 启动前端（后台运行）
echo "启动前端服务（端口 3000）..."
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端服务 PID: $FRONTEND_PID"
cd ..

# 保存 PID
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

# 创建日志目录
mkdir -p logs

echo ""
echo "========================================"
echo "✅ 启动成功！"
echo "========================================"
echo ""
echo "📱 访问地址:"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "📝 日志文件:"
echo "   后端日志: logs/backend.log"
echo "   前端日志: logs/frontend.log"
echo ""
echo "🛑 停止服务:"
echo "   ./stop.sh"
echo ""
echo "========================================"
