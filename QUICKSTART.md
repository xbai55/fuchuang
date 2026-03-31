# 快速启动指南

## 环境配置

### 1. 复制环境变量文件

```bash
cp .env.example .env
```

### 2. 编辑 .env 文件，填入你的 Kimi API Key

```bash
# 编辑 .env 文件
LLM_API_KEY=你的Kimi_API_Key
# 其他配置保持默认即可
```

获取 Kimi API Key:
1. 访问 https://platform.moonshot.cn/
2. 注册/登录账号
3. 在"API Key 管理"中创建新 key

### 3. 启动后端服务

```bash
cd backend
python main.py
```

服务将在 http://localhost:8000 启动

## 支持的模型

### Kimi (Moonshot) - 默认
- `moonshot-v1-8k` - 适合短文本处理
- `moonshot-v1-32k` - 中等长度上下文
- `moonshot-v1-128k` - 超长上下文

### OpenAI
- `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`

## 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_API_KEY` | LLM API 密钥 | 必填 |
| `LLM_BASE_URL` | API 基础 URL | Kimi: `https://api.moonshot.cn/v1` |
| `LLM_MODEL` | 模型名称 | `moonshot-v1-8k` |
| `SECRET_KEY` | 应用密钥 | 必填 |

## 切换不同 LLM

### 使用 OpenAI

```bash
# .env 文件
OPENAI_API_KEY=your_openai_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

### 使用其他兼容 OpenAI 的 API

```bash
# .env 文件
LLM_API_KEY=your_key
LLM_BASE_URL=https://your-api-endpoint.com/v1
LLM_MODEL=your-model-name
```
