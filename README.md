# 反诈预警专家系统 v2.1

> 基于 **PDIE (Perception-Decision-Intervention-Evolution)** 架构的电信网络诈骗预警系统，支持文本、语音、图片、视频多模态输入分析，提供实时风险监测、个性化预警及监护人联动服务。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org)

---

## 核心特性

- **多模态分析**：支持文本、语音、图片、视频输入
- **AI 伪造检测**：识别 AI 合成语音和视频换脸
- **RAG 知识库**：基于 ChromaDB 的相似案例检索
- **混合检索引擎**：TF-IDF 字符级检索 + ChromaDB 语义检索双重保障
- **精细化风险检测**：8种诈骗子类型精准识别（投资诈骗、培训诈骗、客服退款、公检法诈骗、AI拟声、转账伪造、二维码诈骗、两卡犯罪）
- **双重评估机制**：LLM 大模型 + RAG 规则引擎融合评估
- **自动知识库构建**：从官方源（人大网、最高法、政府网）自动爬取更新
- **风险评估引擎**：0-100 分评分体系，三级风险分级
- **个性化预警**：根据用户角色（老人/学生/财会/通用）生成定制化警告
- **监护人联动**：高风险自动通知监护人
- **智能对话模式**：低风险时自然对话，高风险时专业警告

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端层 (React)                        │
│  - 用户认证界面                                           │
│  - 多模态输入界面 (文本/语音/图片/视频)                   │
│  - 实时预警展示                                           │
│  - 聊天历史记录                                           │
└─────────────────────────────────────────────────────────┘
                            ↓ HTTP
┌─────────────────────────────────────────────────────────┐
│              API 网关层 (FastAPI)                         │
│  - 统一入口路由                                           │
│  - 认证授权中间件                                         │
│  - CORS 跨域支持                                          │
│  - 全局异常捕获                                           │
│  - 请求分发                                               │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              PDIE 架构工作流编排层                         │
├─────────────────────────────────────────────────────────┤
│  Perception (感知层)                                     │
│  ├── 文本处理器                                          │
│  ├── 音频处理器 (ASR + AI 伪造检测)                       │
│  ├── 图像处理器 (OCR)                                    │
│  └── 视频处理器 (关键帧 + AI 换脸检测 + OCR)              │
├─────────────────────────────────────────────────────────┤
│  Decision (决策层)                                       │
│  ├── RAG 知识检索 (ChromaDB + TF-IDF 混合检索)           │
│  ├── 精细化风险检测器 (8种诈骗子类型)                    │
│  ├── 风险评估引擎 (LLM + RAG 双重评估)                   │
│  └── 风险分级决策                                        │
├─────────────────────────────────────────────────────────┤
│  Intervention (干预层)                                   │
│  ├── 个性化预警生成                                      │
│  ├── 智能对话回复                                        │
│  ├── 监护人通知系统                                      │
│  └── 安全报告生成                                        │
├─────────────────────────────────────────────────────────┤
│  Evolution (进化层)                                      │
│  ├── 案例自动入库                                        │
│  ├── 反馈收集                                            │
│  └── 模型监控                                            │
└─────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
├── backend/                    # FastAPI 后端
│   ├── api/                   # API 路由
│   │   ├── auth.py           # 认证接口 (注册/登录)
│   │   ├── contacts.py       # 联系人接口
│   │   ├── settings.py       # 用户设置接口
│   │   ├── agent_chat.py     # AI 对话接口
│   │   └── fraud_detection.py # 反诈检测接口
│   ├── graph_core/           # 图核心客户端
│   │   ├── graph_client.py   # LangGraph 客户端
│   │   ├── task_manager.py   # 异步任务管理
│   │   └── exceptions.py     # 全局异常处理
│   ├── app.py                # FastAPI 入口 (主文件)
│   ├── database.py           # 数据库模型
│   ├── auth.py               # 认证工具
│   └── requirements.txt
│
├── src/                      # LangGraph 核心工作流
│   ├── core/                 # 核心抽象层
│   │   ├── utils/            # 公共工具 (JSON/配置/文件/异步)
│   │   ├── models/           # 数据模型 (Media/State)
│   │   └── interfaces/       # 接口定义 (LLM/BaseNode/LLMClient)
│   │
│   ├── perception/           # 感知层 (PDIE-P)
│   │   ├── processors/       # 各类处理器
│   │   └── manager.py        # 统一入口
│   │
│   ├── brain/                # 决策层 (PDIE-D)
│   │   ├── rag/              # RAG 检索增强生成
│   │   │   ├── detector.py   # 风险检测器
│   │   │   ├── retriever.py  # 混合检索器
│   │   │   └── cli.py        # CLI 工具
│   │   └── risk/             # 风险评估引擎
│   │
│   ├── action/               # 干预层 (PDIE-I)
│   │   ├── alert_generator.py    # 智能回复生成
│   │   ├── intervention_service.py
│   │   └── report_generator.py
│   │
│   ├── evolution/            # 进化层 (PDIE-E)
│   │
│   └── graphs/               # 工作流节点
│       ├── nodes/            # 节点实现
│       └── graph.py          # 工作流编排
│
├── multimodal_input/         # 多模态 AI 模块
│   ├── audio_module/         # 音频处理
│   ├── video_module/         # 视频处理
│   └── ocr/                  # OCR 识别
│
├── frontend/                 # React + TypeScript 前端
│   └── src/
│       ├── components/       # UI 组件 (Sidebar)
│       ├── pages/            # 页面
│       │   ├── ChatPage.tsx      # 聊天界面
│       │   ├── Login.tsx         # 登录
│       │   ├── Register.tsx      # 注册
│       │   └── SettingsPage.tsx  # 设置
│       └── services/         # API 服务 (api.ts)
│
├── config/                   # 配置文件
│   ├── rag.yaml              # RAG 主配置
│   └── *.seed.yaml           # 种子数据
│
├── .env                      # 环境变量配置
├── .env.example              # 环境变量示例
└── requirements.txt          # Python 依赖
```

---

## 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+
- FFmpeg (音频/视频处理，可选)

### 1. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
# LLM API 配置 (支持 Kimi/OpenAI)
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k

# 或 OpenAI 配置
# OPENAI_API_KEY=your_key_here

# 安全密钥 (生产环境必须修改)
SECRET_KEY=your-secret-key-here

# 环境
ENV=development
```

### 2. 启动后端

```bash
# 进入后端目录
cd backend

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

后端服务将在 `http://localhost:8000` 启动，自动访问：`http://localhost:8000/docs`

### 3. 启动前端

```bash
# 新终端，进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 `http://localhost:5173` 启动

### 4. 访问应用

打开浏览器访问 `http://localhost:5173`

---

## 配置说明

### LLM 模型配置

系统支持多种 LLM 提供商：

| 提供商 | 模型示例 | 配置项 |
|--------|---------|--------|
| **Kimi (Moonshot)** | `moonshot-v1-8k`, `moonshot-v1-32k` | `LLM_API_KEY` + `LLM_BASE_URL` |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| **自定义** | 任意 OpenAI 兼容 API | `LLM_BASE_URL` |

**注意**：Kimi k2.5 模型只支持 `temperature=1`，系统会自动适配。

### 数据库

默认使用 SQLite (`fraud_detection.db`)，无需额外配置。

如需更换数据库，修改 `.env`：
```bash
DATABASE_URL=postgresql://user:pass@localhost/fraud_detection
```

---

## 工作流流程

```
1. multimodal_input (多模态输入处理)
   - 处理文本、语音、图片、视频输入
   - AI 伪造检测
   - OCR 识别
   ↓
2. knowledge_search (知识库检索)
   - RAG 混合检索 (ChromaDB + TF-IDF)
   - 检索相似案例、法律依据
   - 8种诈骗子类型匹配
   ↓
3. risk_assessment (风险评估)
   - LLM + RAG 双重评估
   - 多维度风险分析
   - 风险评分 (0-100)
   - 风险等级判定
   ↓
4. intervention (干预层)
   ├─→ 低风险 (<40)  → 自然对话回复
   ├─→ 中风险 (40-75) → 友好风险提示
   └─→ 高风险 (>75)   → 立即警告，通知监护人
   ↓
5. report_generation (报告生成)
   - 生成完整的安全分析报告
   ↓
6. END
```

---

## API 接口

### 认证相关

```bash
POST /api/auth/register          # 用户注册
POST /api/auth/login             # 用户登录 (Form 格式)
GET  /api/auth/me                # 获取当前用户
PUT  /api/auth/me                # 更新用户信息
POST /api/auth/refresh           # 刷新 Token
```

### 联系人管理

```bash
GET    /api/contacts/            # 获取联系人列表
POST   /api/contacts/            # 创建联系人
PUT    /api/contacts/{id}        # 更新联系人
DELETE /api/contacts/{id}        # 删除联系人
```

### 用户设置

```bash
GET    /api/settings/            # 获取用户设置
PATCH  /api/settings/            # 更新设置 (主题/通知等)
PUT    /api/settings/profile     # 更新个人资料
POST   /api/settings/change-password  # 修改密码
```

### 反诈检测

```bash
POST /api/fraud/detect           # 多模态检测 (同步)
POST /api/fraud/detect-async     # 异步检测
GET  /api/fraud/history          # 历史记录
GET  /api/fraud/tasks/{task_id}  # 查询异步任务
```

**请求示例：**

```bash
# 纯文本检测
curl -X POST http://localhost:8000/api/fraud/detect \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "message=你好，请帮我分析一下"

# 带文件上传
curl -X POST http://localhost:8000/api/fraud/detect \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "message=请分析这段语音" \
  -F "audio_file=@recording.wav"
```

**响应示例：**

```json
{
  "code": 200,
  "message": "检测完成",
  "data": {
    "risk_score": 0,
    "risk_level": "low",
    "scam_type": "",
    "warning_message": "你好！我是你的反诈助手，有什么可以帮助你的吗？",
    "final_report": "...",
    "guardian_alert": false
  }
}
```

---

## 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.121+ | 高性能 Web 框架 |
| LangGraph | 0.2+ | AI 工作流编排 |
| LangChain | 0.3+ | LLM 应用框架 |
| SQLAlchemy | 2.0+ | ORM 数据库操作 |
| Pydantic | 2.12+ | 数据验证 |
| Python-Jose | 3.3+ | JWT 令牌处理 |
| Passlib | 1.7+ | 密码哈希 |
| python-multipart | 0.0.6+ | 文件上传支持 |

### AI 能力

| 技术 | 用途 |
|------|------|
| PaddleOCR | OCR 文字识别 |
| FunASR | 语音识别 (ASR) |
| ChromaDB | 向量存储 / RAG 检索 |
| scikit-learn | TF-IDF 字符级向量化 |
| sentence-transformers | 语义嵌入 (可选) |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18+ | UI 框架 |
| TypeScript | 5.0+ | 类型安全 |
| Vite | 5.0+ | 构建工具 |
| Ant Design | 5.20+ | UI 组件库 |
| React Router | 6+ | 路由管理 |
| Axios | 1.6+ | HTTP 客户端 |
| Tailwind CSS | 3.4+ | 原子化 CSS |

---

## 风险等级说明

| 等级 | 分数范围 | 处理方式 |
|------|---------|---------|
| 低风险 | < 40 | 自然对话回复，提供一般性建议 |
| 中风险 | 40-75 | 疑似诈骗，触发风险提示 |
| 高风险 | > 75 | 立即干预，强硬警告，自动通知监护人 |

---

## 用户角色针对性

- **老人 (elderly)**：语气温和、通俗易懂，强调与子女沟通
- **学生 (student)**：语气友好、直接，警惕诱导消费与虚假兼职
- **财会人员 (finance)**：语气专业、严肃，强调专业流程与法律责任
- **通用用户 (general)**：语气中性、客观，提供明确安全建议

---

## 故障排查

### 后端启动失败

**问题**: `ModuleNotFoundError` 或导入错误

**解决**:
```bash
# 确保在项目根目录运行
cd C:\Users\xbai55\Desktop\fc\claude_fc
python backend/app.py
```

### 数据库错误

**问题**: `no such column` 或表结构错误

**解决**:
```bash
# 删除旧数据库，让系统自动重建
rm backend/fraud_detection.db  # Windows: del backend\fraud_detection.db
python backend/app.py
```

### LLM 400 错误 (temperature)

**问题**: `invalid temperature: only 1 is allowed`

**解决**: 系统已自动适配 Kimi k2.5 模型，无需手动修改。或使用其他模型：
```bash
# .env 中修改
LLM_MODEL=moonshot-v1-8k
```

### CORS 跨域错误

**问题**: 浏览器提示 CORS policy 错误

**解决**: 系统已配置全局 CORS 中间件，确保前端访问 `http://localhost:5173` 或 `http://localhost:3000`

### 前端 message 警告

**问题**: `[antd: message] Static function can not consume context`

**解决**: 已修复，确保使用 `App.useApp()` 获取 message 实例。

### 端口被占用

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# 或使用自动脚本
python run_system.py --stop
python run_system.py
```

---

## 生产部署

1. **修改 `.env`：**
   ```bash
   ENV=production
   SECRET_KEY=<32位以上随机字符串>
   # 配置你的域名
   ```

2. **后端部署：**
   ```bash
   cd backend
   pip install -r requirements.txt
   python app.py
   # 或使用 gunicorn
   # gunicorn app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

3. **前端构建：**
   ```bash
   cd frontend
   npm install
   npm run build
   # 使用 nginx 托管 dist/ 目录
   ```

---

## 最近更新

### v2.1 (2026-03-31)

- ✅ 修复全局异常捕获，显示详细错误信息
- ✅ 修复 CORS 跨域问题，支持 OPTIONS 预检
- ✅ 修复 LangGraph 异步调用 (`ainvoke`)
- ✅ 修复 Ant Design message 警告
- ✅ 修复 Card 组件 `bordered` 弃用警告
- ✅ 支持多种 LLM 模型自动适配 (Kimi/OpenAI)
- ✅ 智能对话模式：低风险自然对话，高风险专业警告
- ✅ 优化数据库错误处理

---

## 开发计划

- [ ] RAG 知识库自动构建
- [ ] WebSocket 实时推送
- [ ] 模型监控与告警
- [ ] 多语言支持
- [ ] Flutter 移动端完善

---

## 许可证

本项目仅供学习和研究使用。

---

**版本**: v2.1  
**更新时间**: 2026-03-31
