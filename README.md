# 反诈预警系统

一个基于 AI 的智能反诈预警系统，支持多模态输入（文本、语音、图片）、实时风险评估、个性化预警和监护人联动。

## 🌟 核心功能

### 1. 多模态感知
- **文本分析**: 直接分析聊天记录、短信等文本内容
- **语音转文字**: 使用 ASR 技术将语音转换为文本
- **图片识别**: 利用多模态模型分析截图、二维码等图片内容

### 2. 智能风险评估
- 综合评分（0-100分）
- 识别高危词汇和诈骗剧本
- 匹配典型诈骗类型（刷单、理财、公检法、AI换脸等）

### 3. 知识库检索 (RAG)
- 关联最新法律法规与典型案例
- 消除模型幻觉，提供准确的法律依据

### 4. 个性化预警
- 根据用户角色（老人/学生/财会人员/通用）动态调整预警策略
- 分级预警（低/中/高风险）

### 5. 监护人联动
- 高风险自动通知监护人
- 可设置多个联系人并指定监护人

## 📋 技术栈

### 后端
- **框架**: FastAPI
- **数据库**: SQLite
- **认证**: JWT
- **AI 引擎**: LangGraph + 豆包大模型
- **语音识别**: ASRClient
- **知识库**: KnowledgeClient (RAG)

### 前端
- **框架**: React 18 + TypeScript
- **UI 组件**: Ant Design
- **样式**: Tailwind CSS
- **路由**: React Router
- **HTTP 客户端**: Axios

## 🚀 快速开始

### 前置要求

- Python 3.8+
- Node.js 18+
- npm 或 yarn

### 1. 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

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

后端服务将在 `http://localhost:8000` 启动

API 文档: `http://localhost:8000/docs`

### 2. 前端启动

```bash
# 打开新终端，进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 `http://localhost:3000` 启动

### 3. 使用系统

1. 访问 `http://localhost:3000`
2. 点击"立即注册"创建账号
3. 登录后即可使用反诈预警功能
4. 在"联系人设置"中添加联系人和监护人
5. 在"对话预警"中输入聊天内容进行实时风险分析

## 📁 项目结构

```
.
├── backend/                 # 后端代码
│   ├── api/                # API 路由
│   │   ├── auth.py        # 认证 API
│   │   ├── contacts.py    # 联系人 API
│   │   └── fraud_detection.py  # 反诈检测 API
│   ├── config/            # 大模型配置
│   ├── src/               # 工作流代码
│   │   ├── graphs/        # LangGraph 工作流
│   │   ├── tools/         # 工具函数
│   │   └── utils/         # 工具类
│   ├── database.py        # 数据库模型
│   ├── schemas.py         # Pydantic schemas
│   ├── auth.py            # 认证逻辑
│   └── main.py            # FastAPI 入口
│
├── frontend/              # 前端代码
│   ├── src/
│   │   ├── components/    # 组件
│   │   │   └── Sidebar.tsx  # 侧边栏
│   │   ├── pages/         # 页面
│   │   │   ├── Login.tsx     # 登录页
│   │   │   ├── Register.tsx  # 注册页
│   │   │   ├── ChatPage.tsx  # 聊天页面
│   │   │   └── ContactsPage.tsx  # 联系人页面
│   │   ├── services/      # API 服务
│   │   │   └── api.ts        # API 客户端
│   │   ├── utils/         # 工具函数
│   │   │   └── storage.ts    # 本地存储
│   │   ├── types/         # TypeScript 类型
│   │   │   └── index.ts
│   │   ├── App.tsx        # 应用根组件
│   │   ├── main.tsx       # 入口文件
│   │   └── index.css      # 全局样式
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
└── README.md              # 项目说明
```

## 🎨 界面设计

系统采用 Coze 风格的深色主题设计：
- **主色调**: 渐变紫蓝色 (#6366f1 → #8b5cf6)
- **背景色**: 深色系 (#1a1a2e, #16162a)
- **圆角**: 现代 UI 风格
- **响应式**: 适配不同屏幕尺寸

## 🔒 安全特性

- JWT Token 认证
- 密码 BCrypt 加密
- API 路由权限保护
- CORS 跨域保护
- SQL 注入防护

## 📊 API 端点

### 认证 API
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息
- `PUT /api/auth/me` - 更新用户信息

### 联系人 API
- `GET /api/contacts/` - 获取联系人列表
- `POST /api/contacts/` - 创建联系人
- `PUT /api/contacts/{id}` - 更新联系人
- `DELETE /api/contacts/{id}` - 删除联系人

### 反诈检测 API
- `POST /api/fraud/detect` - 检测诈骗
- `GET /api/fraud/history` - 获取聊天历史

详细 API 文档: `http://localhost:8000/docs`

## 🧪 测试

### 测试用例

**输入**:
```
"你好，我是淘宝客服，你的订单因为系统故障需要退款，请点击链接并提供银行卡号和验证码"
```

**输出**:
- 风险评分: 90/100（高风险）
- 诈骗类型: 身份冒充（冒充淘宝客服）
- 警告文案: 详细的反诈提示
- 监护人通知: 自动触发

## 📝 开发指南

### 添加新的诈骗类型

1. 编辑 `backend/config/risk_assessment_cfg.json`
2. 在系统提示词中添加新的诈骗类型描述
3. 更新工作流逻辑（如需要）

### 自定义 UI 主题

编辑 `frontend/tailwind.config.js`:
```javascript
theme: {
  extend: {
    colors: {
      primary: '#your-color',
      secondary: '#your-color',
      // ...
    }
  }
}
```

## 🔧 配置说明

### 后端环境变量

- `SECRET_KEY`: JWT 密钥（生产环境请修改）
- `DATABASE_URL`: 数据库连接字符串

### 前端环境变量

- `VITE_API_URL`: 后端 API 地址

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请通过以下方式联系：
- 提交 Issue
- 发送邮件

---

**⚠️ 重要提示**: 本系统仅作为技术演示，实际使用时请结合专业的反诈措施。
