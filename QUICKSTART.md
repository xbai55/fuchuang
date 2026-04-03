# 快速启动指南

该文档用于本地快速拉起前后端联调环境。

## 1. 准备环境

- Python 3.10+
- Node.js 18+

## 2. 配置环境变量

在仓库根目录执行：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填写：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
SECRET_KEY=replace-with-random-secret
```

## 3. 安装后端依赖并启动

在仓库根目录执行：

```bash
pip install -r requirements.txt
python backend/app.py
```

后端地址：

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 4. 启动前端

新开终端执行：

```bash
cd frontend
npm install
npm run dev
```

前端地址：http://localhost:5173

## 5. 核验链路

1. 打开前端页面并登录/注册。
2. 进入风险识别页面发送一条测试消息。
3. 将一张本地图片直接拖入聊天输入区，确认页面出现已挂载文件名。
4. 在后端日志中确认检测任务已触发。

## 文件拖拽注意事项

- 建议优先从系统文件管理器拖拽本地文件。
- 从飞书拖拽到网页时，浏览器可能只提供链接文本：
	- 若链接可直接下载，前端会尝试自动转换为文件；
	- 若被跨域或登录态限制，请先在飞书下载到本地后再拖拽上传。

## 可选配置

RAG 自动构建（默认开启）：

```env
RAG_AUTO_BUILD=true
RAG_FORCE_REBUILD=false
RAG_CONFIG_PATH=config/rag.yaml
```

切换到 OpenAI 兼容模型示例：

```env
OPENAI_API_KEY=your_openai_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```
