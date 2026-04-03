# 反诈预警系统前端

前端基于 React + TypeScript + Vite + Ant Design，负责登录注册、风险识别对话、联系人管理和用户设置。

## 启动

在 `frontend` 目录执行：

```bash
npm install
npm run dev
```

默认地址：http://localhost:5173

生产构建：

```bash
npm run build
```

## 环境变量

创建 `frontend/.env`：

```env
VITE_API_URL=http://localhost:8000
```

## 当前功能

- 中英文切换（简体中文 / English）
- 深浅色主题与字号设置
- 隐私模式脱敏展示
- 文本 + 多模态文件上传（音频/图片/视频）
- 聊天输入区拖拽上传（支持页面级兜底 drop 监听）
- 异步任务 WebSocket 实时进度推送
- WS 异常时自动降级轮询

## 拖拽上传行为说明

- 可直接从本地文件管理器拖入音频/图片/视频文件。
- 一次可拖入多文件，但同类型仅保留首个文件。
- 从飞书等应用拖拽时，若浏览器未提供本地文件句柄：
  - 前端会尝试从拖拽载荷中解析链接并下载转换；
  - 若受跨域或登录态限制，会提示用户先下载到本地后再上传。

## 目录说明

```text
frontend/src/
  components/              # 通用组件（侧边栏等）
  pages/                   # 页面（登录、注册、聊天、联系人、设置）
  services/api.ts          # 后端 API 封装
  utils/                   # 存储、外观、隐私工具
  i18n.tsx                 # 语言上下文
  types/index.ts           # TS 类型定义
```

## 调试建议

- 前端 401：检查 localStorage 中 token 是否存在。
- 页面主题不生效：确认用户设置接口返回的 theme/font_size/privacy_mode 字段。
- 实时推送不更新：检查浏览器 Network 中 `/api/fraud/ws/tasks/{task_id}` 连接状态。
