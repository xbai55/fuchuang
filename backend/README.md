# 反诈预警系统 - 后端

基于 FastAPI 的后端服务，提供用户认证、联系人管理和反诈预警功能。

## 🚀 启动指南

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8000` 启动

### 3. 访问 API 文档

打开浏览器访问 `http://localhost:8000/docs`

## 📁 项目结构

```
backend/
├── api/                    # API 路由
│   ├── auth.py            # 认证相关
│   ├── contacts.py        # 联系人管理
│   └── fraud_detection.py # 反诈检测
├── config/                # 配置文件
│   ├── *.json            # 大模型配置
├── src/                   # 工作流代码
│   ├── graphs/           # LangGraph 工作流
│   ├── tools/            # 工具函数
│   └── utils/            # 工具类
├── database.py           # 数据库模型
├── schemas.py            # Pydantic schemas
├── auth.py               # 认证逻辑
└── main.py               # FastAPI 入口
```

## 🔑 API 端点

### 认证
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户
- `PUT /api/auth/me` - 更新用户信息

### 联系人
- `GET /api/contacts/` - 获取联系人列表
- `POST /api/contacts/` - 创建联系人
- `GET /api/contacts/{id}` - 获取单个联系人
- `PUT /api/contacts/{id}` - 更新联系人
- `DELETE /api/contacts/{id}` - 删除联系人

### 反诈检测
- `POST /api/fraud/detect` - 检测诈骗
- `GET /api/fraud/history` - 获取聊天历史

## 🔧 配置

### 环境变量

```bash
# JWT 密钥（生产环境必须修改）
export SECRET_KEY="your-secret-key-here"

# 数据库 URL
export DATABASE_URL="sqlite:///./fraud_detection.db"
```

### 数据库初始化

数据库会在首次启动时自动初始化，创建以下表：
- `users` - 用户表
- `contacts` - 联系人表
- `chat_history` - 聊天历史表

## 🔒 认证机制

系统使用 JWT (JSON Web Token) 进行身份验证：

1. 用户登录/注册后返回 access_token
2. 后续请求需要在 Header 中携带: `Authorization: Bearer {token}`
3. Token 默认有效期为 7 天

## 🤖 AI 工作流

反诈检测使用 LangGraph 工作流，包含以下节点：

1. **multimodal_input** - 多模态输入处理
2. **knowledge_search** - 知识库检索
3. **risk_assessment** - 风险评估
4. **risk_decision** - 分级决策
5. **intervention** - 干预措施
6. **report_generation** - 报告生成

详细配置见 `config/` 目录下的 JSON 文件。

## 🧪 测试

### 测试 API

使用 curl 或 Postman 测试：

```bash
# 注册用户
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"123456"}'

# 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test&password=123456"

# 反诈检测（需要先登录获取 token）
curl -X POST http://localhost:8000/api/fraud/detect \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"你好，我是淘宝客服"}'
```

## 📊 数据库模型

### User（用户）
- `id`: 主键
- `username`: 用户名（唯一）
- `email`: 邮箱（唯一）
- `hashed_password`: 加密密码
- `user_role`: 用户角色
- `guardian_name`: 监护人姓名
- `created_at`: 创建时间
- `is_active`: 是否激活

### Contact（联系人）
- `id`: 主键
- `user_id`: 用户 ID（外键）
- `name`: 姓名
- `phone`: 手机号
- `relationship`: 关系
- `is_guardian`: 是否为监护人
- `created_at`: 创建时间

### ChatHistory（聊天历史）
- `id`: 主键
- `user_id`: 用户 ID（外键）
- `user_message`: 用户消息
- `bot_response`: 机器人回复
- `risk_score`: 风险评分
- `risk_level`: 风险等级
- `scam_type`: 诈骗类型
- `guardian_alert`: 是否通知监护人
- `created_at`: 创建时间

## 🚨 错误处理

API 遵循标准的 HTTP 状态码：

- `200` - 成功
- `400` - 请求错误
- `401` - 未授权
- `404` - 资源不存在
- `500` - 服务器错误

错误响应格式：
```json
{
  "detail": "错误描述"
}
```

## 🔄 开发模式

使用热重载启动：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📝 注意事项

1. 生产环境必须修改 `SECRET_KEY`
2. 数据库文件会在 `backend/` 目录下生成
3. 确保 Python 版本 >= 3.8
4. 建议使用虚拟环境隔离依赖
