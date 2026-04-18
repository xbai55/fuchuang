# 反诈预警专家系统 v2.2

基于 PDIE（Perception-Decision-Intervention-Evolution）架构的多模态反诈系统，支持文本、音频、图片、视频输入分析，并提供风险评估、详细报告、监护联动和历史记录能力。

## 当前技术栈

- 后端：FastAPI + LangGraph + SQLAlchemy
- 前端：React 18 + TypeScript + Vite + Ant Design
- 多模态：OCR、音频识别、视频分析
- 风险分析：LLM + RAG 混合评估

## 当前主要能力

- 多模态诈骗检测：文本、音频、图片、视频统一入口
- 异步检测任务：支持 WebSocket 实时进度推送
- 风险报告生成：输出风险分数、风险等级、诈骗类型、详细分析报告
- RAG 检索增强：结合相似案例与法律依据
- 用户资料定制：支持年龄、性别、职业、监护人姓名
- 中英双语界面：前端设置中可切换 `zh-CN / en-US`
- 历史记录与反馈：支持检测历史查看与反馈提交

## 项目结构

```text
backend/                  FastAPI 后端
  api/                    认证、设置、联系人、检测、监控等接口
  graph_core/             LangGraph 客户端与任务管理
  app.py                  后端启动入口
  database.py             数据库初始化

src/                      核心工作流
  perception/             多模态输入处理
  brain/                  RAG、风险评估、意图识别
  action/                 预警、报告、监护通知
  evolution/              反馈与持续演化
  graphs/                 工作流编排

multimodal_input/         音频、视频、OCR 模块
frontend/                 React 前端
config/                   RAG 与种子配置
.env.example              环境变量示例
requirements.txt          后端依赖
```

## 环境要求

- Python 3.10+
- Node.js 18+
- npm 9+
- FFmpeg
  说明：音频/视频链路建议安装，纯文本场景可先不装

## 环境变量

先复制根目录的 `.env.example` 为 `.env`，再按实际环境填写。

当前示例中的关键变量如下：

```env
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-vl-32b-thinking

SECRET_KEY=replace_with_your_secret_key
ENV=development
```

可选变量：

```env
# DATABASE_URL=sqlite:///./fraud_detection.db
# ALLOWED_ORIGINS=https://your-domain.com,https://app.your-domain.com
# GUARDIAN_NOTIFY_PROVIDER=pending_provider
```

说明：

- 当前后端走 OpenAI 兼容接口配置，默认示例为 DashScope 兼容地址
- `SECRET_KEY` 在生产环境务必替换为高强度随机值
- 未配置 `DATABASE_URL` 时默认使用 SQLite
- 监护通知 provider 当前保留统一接口，后续再绑定具体渠道

## 快速开始

### 1. 安装后端依赖

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS / Linux:

```bash
source venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

### 2. 启动后端

在项目根目录执行：

```bash
python backend/app.py
```

默认地址：

- API：`http://localhost:8000`
- Swagger 文档：`http://localhost:8000/docs`

启动时会自动执行这些动作：

- 初始化数据库
- 检查并按需构建 RAG 知识库
- 后台执行模型预热

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认地址：

- 前端：`http://localhost:5173`

如果需要局域网访问，可使用：

```bash
npm run dev:host
```

## 前端接口配置

前端通过 `frontend/.env` 中的 `VITE_API_URL` 指向后端，默认配置如下：

```env
VITE_API_URL=http://localhost:8000
```

如果后端不在本机，请改成实际 API 地址。

## 当前用户资料配置

当前设置页已接入以下资料字段：

- 用户名
- 邮箱
- 年龄：`child / young_adult / elderly`
- 性别：`male / female`
- 职业：`student / enterprise_staff / self_employed / retired_group / public_officer / finance_practitioner / other`
- 监护人姓名

这些资料会参与前端展示与后端风险画像逻辑。

## 主要接口

认证：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `PUT /api/auth/me`

设置：

- `GET /api/settings/`
- `PATCH /api/settings/`
- `PUT /api/settings/profile`
- `POST /api/settings/change-password`

检测：

- `POST /api/fraud/detect`
- `POST /api/fraud/detect-async`
- `POST /api/fraud/feedback`
- `GET /api/fraud/history`
- `GET /api/fraud/tasks/{task_id}`

Agent：

- `POST /api/agent/chat`
- `POST /api/agent/chat-async`

监控：

- `GET /api/monitor/`
- `GET /api/monitor/health`
- `GET /api/monitor/metrics`
- `GET /api/monitor/alerts`

## 常见问题

### 后端启动失败

确认在项目根目录执行：

```bash
python backend/app.py
```

### 前端连不上后端

检查：

- 后端是否运行在 `http://localhost:8000`
- `frontend/.env` 中的 `VITE_API_URL` 是否正确
- 浏览器是否因为跨域或端口错误拦截请求

### 数据库字段不一致

如果是本地开发环境且允许重建，可删除旧的 SQLite 数据库后重新启动后端。

### 构建时报 `esbuild spawn EPERM`

这通常是本机环境权限问题，不是业务代码配置本身导致。可优先用 `npm run dev` 本地开发，再单独排查构建权限。

## 版本说明

- 当前文档基于仓库现有配置整理
- 默认前后端启动方式分别为 `python backend/app.py` 和 `npm run dev`
