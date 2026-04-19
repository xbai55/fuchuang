# AI 反诈助手 - Flutter 移动端

## 项目结构

```
lib/
├── main.dart                          # 应用入口
├── core/                              # 核心层
│   ├── constants/
│   │   └── api_constants.dart         # API 常量配置
│   ├── network/
│   │   ├── api_client.dart            # Dio 封装 + Token 刷新
│   │   └── api_exception.dart         # 异常定义
│   ├── storage/
│   │   └── local_storage.dart         # SharedPreferences 封装
│   └── utils/
│       └── media_compressor.dart      # 图片/视频压缩
├── data/                              # 数据层
│   ├── api/
│   │   └── fraud_api.dart             # 反诈检测 API
│   └── models/
│       └── detection_result.dart      # 检测数据模型
├── presentation/                      # 表现层
│   ├── blocs/
│   │   └── detection/                 # 检测 BLoC
│   │       ├── detection_bloc.dart
│   │       ├── detection_event.dart
│   │       └── detection_state.dart
│   ├── pages/
│   │   ├── home/
│   │   │   └── home_page.dart         # 首页（Gemini 风格）
│   │   ├── result/
│   │   │   └── result_page.dart       # 结果页（红色呼吸灯）
│   │   ├── agent/
│   │   │   └── agent_page.dart        # 反诈助手
│   │   ├── history/
│   │   │   └── history_page.dart      # 历史记录
│   │   └── main_shell.dart            # 底部导航壳
│   └── theme/
│       └── app_theme.dart             # Material 3 主题
```

## 快速开始

### 1. 安装依赖

```bash
cd anti_fraud_app
flutter pub get
```

### 2. 配置环境

复制 `.env.example` 为 `.env`，修改 API 地址：

```bash
# Android 模拟器
API_BASE_URL=http://10.0.2.2:8000

# iOS 模拟器
# API_BASE_URL=http://localhost:8000

# 真机测试（使用电脑 IP）
# API_BASE_URL=http://192.168.x.x:8000
```

### 3. 运行应用

```bash
# 调试模式
flutter run

# 或指定设备
flutter run -d emulator-5554
```

## 移动端部署详细指南

### 后端服务准备

1. **启动后端服务**
   ```powershell
   # 在项目根目录执行
   python backend/app.py
   ```
   默认监听 `http://localhost:8000`，确保端口未被占用。

2. **环境变量配置**
   确保后端 `.env` 文件已正确配置：
   ```env
   SECRET_KEY=your-secret-key
   LLM_API_KEY=your-llm-api-key
   LLM_BASE_URL=https://api.moonshot.cn/v1
   LLM_MODEL=moonshot-v1-8k
   MODEL_MODE=flash  # 或 pro
   ```

### 移动端网络配置

#### API基础URL配置
根据运行环境选择正确的API地址：

| 环境 | API_BASE_URL |
|------|-------------|
| Android模拟器 | `http://10.0.2.2:8000` |
| iOS模拟器 | `http://localhost:8000` |
| 真机调试 | `http://[开发机IP]:8000` |
| 生产环境 | `https://your-domain.com` |

> **注意**: Android模拟器使用 `10.0.2.2` 是因为这是指向宿主机的特殊IP地址。

#### 认证机制
移动端实现完整的JWT认证流程：

1. **登录获取Token**
   - 调用 `POST /api/auth/login`
   - 保存返回的 `access_token` 和 `refresh_token`

2. **请求认证**
   - 在所有API请求Header中添加：`Authorization: Bearer <access_token>`
   - 使用Dio拦截器自动处理Token刷新

3. **WebSocket认证**
   - WebSocket连接通过query参数传递token：`?token=<encoded_access_token>`

### API端点说明

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/auth/login` | POST | 用户登录 | 无需 |
| `/api/auth/register` | POST | 用户注册 | 无需 |
| `/api/auth/me` | GET | 获取用户信息 | 需要 |
| `/api/fraud/detect` | POST | 同步反诈检测 | 需要 |
| `/api/fraud/detect-async` | POST | 异步反诈检测 | 需要 |
| `/api/fraud/tasks/{id}` | GET | 查询任务状态 | 需要 |
| `/api/fraud/ws/tasks/{id}` | WS | WebSocket任务推送 | 需要 |
| `/api/agent/chat` | POST | Agent同步聊天 | 需要 |
| `/api/agent/chat-async` | POST | Agent异步聊天 | 需要 |
| `/api/contacts/` | GET/POST/PUT/DELETE | 联系人管理 | 需要 |
| `/api/fraud/history` | GET | 历史记录查询 | 需要 |

### 多模态文件上传

移动端支持以下文件类型上传：

- **文本**: 直接作为 `message` 参数
- **图片**: multipart/form-data，字段名 `image_file`
- **音频**: multipart/form-data，字段名 `audio_file`  
- **视频**: multipart/form-data，字段名 `video_file`

> **文件大小限制**: 大文件（>10MB）会自动使用异步检测模式

### 实时通信机制

#### 异步任务处理流程
1. 调用异步API（如 `/api/fraud/detect-async`）获取 `task_id`
2. 建立WebSocket连接：`ws://[API_BASE_URL]/api/fraud/ws/tasks/[task_id]?token=[token]`
3. 监听以下事件：
   - `task_update`: 任务进度更新
   - `fraud_chunk`: 风险分析流式输出
   - `task_completed`: 任务完成
   - `task_failed`: 任务失败

#### Agent聊天流式输出
- 同步模式：直接返回完整响应
- 异步模式：通过WebSocket接收 `agent_chunk` 事件，实现逐字输出效果

### 响应格式

统一响应格式：
```json
{
  "code": 200,
  "message": "success",
  "data": {...},
  "timestamp": 1711523456,
  "request_id": "req_abc123"
}
```

错误响应示例：
```json
{
  "code": 401,
  "message": "Unauthorized",
  "data": null,
  "timestamp": 1711523456,
  "request_id": "req_xyz789"
}
```

## 主要功能

### 1. 首页检测（Gemini 风格）
- 流式输入框设计
- 快捷操作 Chips
- 多模态文件选择
- 实时进度显示

### 2. 智能检测
- 文本分析
- 图片识别（OCR）
- 语音分析（ASR + 伪造检测）
- 视频检测（AI 换脸检测）

### 3. 结果展示
- 环形风险分数动画
- 呼吸灯背景效果（高风险）
- 详细分析报告

### 4. 异步处理
- 大文件自动使用异步模式
- 任务轮询查询
- 后台处理支持

## 常见问题排查

### 1. 连接失败
- **Android模拟器**: 确认使用 `10.0.2.2` 而非 `localhost`
- **防火墙**: 确保开发机防火墙允许8000端口访问
- **后端状态**: 确认后端服务正在运行且无错误

### 2. 认证错误
- **Token过期**: 实现自动刷新逻辑
- **Token格式**: 确保Header格式为 `Bearer <token>`
- **WebSocket Token**: 确保URL编码正确

### 3. 文件上传失败
- **文件大小**: 检查是否超过服务器限制
- **MIME类型**: 确保文件类型正确
- **网络超时**: 大文件建议使用异步模式

## 下一步开发

1. **完善 Agent 对话页面**
   - WebSocket 实时通信
   - 消息列表 + 输入框
   - 历史对话管理

2. **历史记录功能**
   - 列表展示
   - 下拉刷新
   - 上拉加载更多

3. **用户系统**
   - 登录/注册页面
   - 个人信息管理
   - 联系人管理

4. **推送通知**
   - Firebase Cloud Messaging
   - 高风险实时告警

5. **离线支持**
   - 本地缓存
   - 离线检测（简化版）