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

## 后端对接说明

### API 端点

| 端点 | 说明 |
|------|------|
| POST `/api/auth/login` | 登录 |
| POST `/api/auth/refresh` | 刷新 Token |
| POST `/api/fraud/detect` | 同步检测 |
| POST `/api/fraud/detect-async` | 异步检测 |
| GET `/api/fraud/tasks/{id}` | 查询任务状态 |
| GET `/api/fraud/history` | 历史记录（分页）|

### 响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": {...},
  "timestamp": 1711523456,
  "request_id": "req_abc123"
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
