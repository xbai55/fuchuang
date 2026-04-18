# 前端说明

前端基于 React 18 + TypeScript + Vite + Ant Design，负责登录注册、反诈检测对话、历史记录、联系人管理和用户设置。

## 启动方式

在 `frontend` 目录执行：

```bash
npm install
npm run dev
```

默认访问地址：

- `http://localhost:5173`

如需局域网访问：

```bash
npm run dev:host
```

生产构建：

```bash
npm run build
```

## 环境变量

创建 `frontend/.env`：

```env
VITE_API_URL=http://localhost:8000
```

说明：

- 该值应指向后端 FastAPI 服务地址
- WebSocket 地址会基于 `VITE_API_URL` 自动换算生成

## 当前功能

- 登录、注册、获取当前用户信息
- 反诈同步检测与异步检测
- WebSocket 实时任务进度更新
- 文本、音频、图片、视频上传
- 聊天输入区拖拽上传
- 检测历史记录查看与删除
- Agent 对话
- 中英双语切换
- 主题、字号、隐私模式设置
- 个人资料设置

## 当前资料字段

设置页当前支持这些资料项：

- 用户名
- 邮箱
- 年龄：`child / young_adult / elderly`
- 性别：`male / female`
- 职业：`student / enterprise_staff / self_employed / retired_group / public_officer / finance_practitioner / other`
- 监护人姓名

用户设置字段包括：

- `theme`
- `notify_enabled`
- `notify_high_risk`
- `notify_guardian_alert`
- `language`
- `font_size`
- `privacy_mode`

## 目录说明

```text
frontend/src/
  components/         通用组件
  pages/              页面
  services/api.ts     API 封装
  types/index.ts      类型定义
  i18n.tsx            语言上下文
  utils/              外观、存储、隐私相关工具
```

## 调试建议

### 页面 401

检查浏览器本地是否存在有效 `access_token`。

### 检测任务进度不更新

检查浏览器 Network 面板中 WebSocket 连接：

- `/api/fraud/ws/tasks/{task_id}`
- `/api/agent/ws/tasks/{task_id}`

### 前端请求地址错误

优先检查 `frontend/.env` 中的 `VITE_API_URL` 是否指向正确后端。
