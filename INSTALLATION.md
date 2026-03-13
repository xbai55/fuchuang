# 反诈预警系统 - 完整安装指南

本指南将帮助您在本地完整部署反诈预警系统。

## 📋 系统要求

### 必需
- **Python**: 3.8 或更高版本
- **Node.js**: 18.0 或更高版本
- **npm**: 9.0 或更高版本（通常随 Node.js 一起安装）
- **内存**: 至少 4GB RAM
- **磁盘**: 至少 2GB 可用空间

### 可选
- Git（用于克隆代码）
- PostgreSQL（生产环境推荐，开发环境使用 SQLite）

## 🚀 快速安装（推荐）

### 方式一：使用启动脚本（Linux/Mac）

```bash
# 1. 克隆或下载项目代码
cd fraud-detection-system

# 2. 赋予启动脚本执行权限
chmod +x start.sh stop.sh

# 3. 一键启动
./start.sh
```

启动成功后，访问 `http://localhost:3000`

### 方式二：手动启动（所有平台）

#### 1. 安装后端

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python3 -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动后端服务
python main.py
```

后端将在 `http://localhost:8000` 启动

#### 2. 安装前端（新终端）

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 `http://localhost:3000` 启动

## 📝 详细安装步骤

### 步骤 1: 检查环境

```bash
# 检查 Python 版本
python3 --version
# 应输出: Python 3.8.x 或更高

# 检查 Node.js 版本
node --version
# 应输出: v18.x.x 或更高

# 检查 npm 版本
npm --version
# 应输出: 9.x.x 或更高
```

### 步骤 2: 安装后端依赖

```bash
cd backend

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

后端依赖包括：
- `fastapi` - Web 框架
- `uvicorn` - ASGI 服务器
- `pydantic` - 数据验证
- `sqlalchemy` - ORM
- `python-jose` - JWT 认证
- `passlib` - 密码加密

### 步骤 3: 配置后端

编辑 `backend/main.py` 中的配置（可选）：

```python
# 修改 SECRET_KEY（生产环境必须修改）
SECRET_KEY = "your-secret-key-change-this-in-production"

# 修改数据库连接（可选）
SQLALCHEMY_DATABASE_URL = "sqlite:///./fraud_detection.db"
```

### 步骤 4: 启动后端

```bash
# 开发模式（热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

验证后端启动成功：
- 访问 `http://localhost:8000` 应显示 API 信息
- 访问 `http://localhost:8000/docs` 应显示 Swagger 文档

### 步骤 5: 安装前端依赖

```bash
cd frontend

# 安装依赖
npm install
```

前端依赖包括：
- `react` - UI 框架
- `antd` - UI 组件库
- `axios` - HTTP 客户端
- `tailwindcss` - CSS 框架
- `react-router-dom` - 路由

### 步骤 6: 配置前端

创建 `.env` 文件（可选）：

```bash
# frontend/.env
VITE_API_URL=http://localhost:8000
```

### 步骤 7: 启动前端

```bash
# 开发模式
npm run dev

# 生产构建
npm run build
```

验证前端启动成功：
- 访问 `http://localhost:3000` 应显示登录页面

### 步骤 8: 首次使用

1. 注册账号
2. 登录系统
3. 设置个人信息（角色、监护人）
4. 添加联系人
5. 开始使用反诈预警功能

## 🔧 常见问题

### 1. Python 版本不兼容

**问题**: `SyntaxError` 或其他 Python 错误

**解决**:
```bash
# 更新 Python 到 3.8+
# 使用 pyenv 安装指定版本（推荐）
pyenv install 3.8.18
pyenv global 3.8.18
```

### 2. Node.js 版本过低

**问题**: `npm install` 失败

**解决**:
```bash
# 使用 nvm 安装指定版本（推荐）
nvm install 18
nvm use 18
```

### 3. 端口被占用

**问题**: `Address already in use`

**解决**:
```bash
# 查找占用端口的进程
# Linux/Mac:
lsof -i :8000
lsof -i :3000

# Windows:
netstat -ano | findstr :8000
netstat -ano | findstr :3000

# 杀死进程
# Linux/Mac:
kill -9 <PID>

# Windows:
taskkill /PID <PID> /F
```

### 4. 依赖安装失败

**问题**: `pip install` 或 `npm install` 失败

**解决**:
```bash
# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

npm install --registry=https://registry.npmmirror.com
```

### 5. 前端无法连接后端

**问题**: `Network Error` 或 `CORS` 错误

**解决**:
```bash
# 检查后端是否启动
curl http://localhost:8000

# 检查 CORS 配置
# backend/main.py 应包含 CORS 中间件
```

### 6. 数据库初始化失败

**问题**: `Table already exists` 或其他数据库错误

**解决**:
```bash
# 删除现有数据库文件
cd backend
rm fraud_detection.db

# 重新启动后端，数据库会自动初始化
python main.py
```

## 📦 生产部署

### 后端部署

使用 Gunicorn + Nginx：

```bash
# 1. 安装 Gunicorn
pip install gunicorn

# 2. 启动服务
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

# 3. 配置 Nginx 反向代理
# /etc/nginx/sites-available/fraud-detection
```

### 前端部署

```bash
# 1. 构建生产版本
cd frontend
npm run build

# 2. 部署 dist 目录到 Web 服务器
# 例如：cp -r dist/* /var/www/html/
```

## 🔒 安全配置

### 1. 修改 SECRET_KEY

```bash
# 生成随机密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 将生成的密钥配置到环境变量
export SECRET_KEY="your-random-key"
```

### 2. 使用 HTTPS

配置 Nginx SSL 证书

### 3. 数据库加密

生产环境建议使用 PostgreSQL 并启用 SSL 连接

## 📞 技术支持

如遇到问题，请：
1. 检查日志文件（`logs/backend.log`, `logs/frontend.log`）
2. 查看本文档的"常见问题"部分
3. 提交 Issue 到项目仓库

## ✅ 安装验证清单

- [ ] Python 3.8+ 已安装
- [ ] Node.js 18+ 已安装
- [ ] 后端依赖已安装
- [ ] 后端服务已启动（http://localhost:8000）
- [ ] 前端依赖已安装
- [ ] 前端服务已启动（http://localhost:3000）
- [ ] 可以访问 Swagger 文档（http://localhost:8000/docs）
- [ ] 可以成功注册和登录
- [ ] 聊天功能正常
- [ ] 联系人管理正常

恭喜！反诈预警系统已成功部署 🎉
