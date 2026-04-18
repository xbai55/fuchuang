# 反诈预警系统后端

后端基于 FastAPI，负责认证、联系人管理、反诈检测、异步任务、WebSocket 推送、反馈学习、Agent 对话和监控告警接口。

## 启动

在仓库根目录执行：

```bash
pip install -r requirements.txt
python backend/app.py
```

访问地址：

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 目录说明

```text
backend/
  api/                 # 路由层
  graph_core/          # LangGraph 任务与异常封装
  app.py               # FastAPI 入口
  auth.py              # JWT 鉴权工具
  database.py          # SQLAlchemy 模型与 DB 初始化
  schemas/             # 请求与响应模型
```

## 主要接口

认证：

- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me

反诈检测：

- POST /api/fraud/detect
- POST /api/fraud/detect-async
- POST /api/fraud/feedback
- GET /api/fraud/tasks/{task_id}
- GET /api/fraud/ws/tasks/{task_id}?token=...
- GET /api/fraud/history

Agent 对话：

- POST /api/agent/chat
- GET /api/agent/conversation/{conversation_id}

联系人：

- GET /api/contacts/
- POST /api/contacts/
- PUT /api/contacts/{id}
- DELETE /api/contacts/{id}

监控与告警：

- GET /api/monitor/
- GET /api/monitor/health
- GET /api/monitor/metrics
- GET /api/monitor/alerts
- POST /api/monitor/alerts/test

## 环境变量

至少配置：

```env
SECRET_KEY=replace-with-random-secret
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
MODEL_MODE=flash
```

可选：

```env
DATABASE_URL=sqlite:///./fraud_detection.db
RAG_AUTO_BUILD=true
RAG_FORCE_REBUILD=false
RAG_CONFIG_PATH=config/rag.yaml
```

OCR 相关（可选）：

```env
# Windows 默认 false，Linux 默认 true
OCR_ENABLE_MKLDNN=false

# CPU 线程数（默认 4）
OCR_CPU_THREADS=4
```

## 媒体检测补充说明

- OCR 默认使用 CPU 版 Paddle（`paddlepaddle==2.6.2`）。
- 图片链路已接入 AI 率检测（复用视觉伪造模型）并参与前期预警。
- 在 AI 率优先模式下，若图片 AI 率达到高阈值，流程会优先返回风险判断并可跳过 OCR 以降低时延。

## 监护通知短信接口状态

- 已移除阿里云短信 API 相关脚本与供应商绑定逻辑。
- 当前仅保留统一接口：`src/action/sms_service.py` 的 `send_guardian_alert`。
- 监护通知编排仍由 `src/action/guardian_notifier.py` 调用该接口，默认返回 `provider_not_bound`，不会阻断主检测链路。

## 本轮功能落地说明（2026-04）

1. 监护人联动与一键升级动作
- 在检测入口中，联系人/监护人会注入图流程上下文。
- 干预层统一生成结构化 `escalation_actions`（110、96110、监护人、紧急联系人）。
- 返回 `guardian_notification`，用于前端展示通知状态与失败原因。

2. EvolutionRuntime 已接入主链路
- 主图通过 `MemorySaver` 作为 checkpointer，按 `user_id/thread_id` 管理会话。
- 每次检测会写入运行时快照，并在高风险场景自动触发 `CaseIngestor` 入库。
- `/api/fraud/feedback` 会调用 `FeedbackCollector` 完成反馈采集和统计。

3. 独立意图识别节点
- 图流程升级为 `perception -> intent_recognition -> knowledge_search -> ...`。
- 节点输出 `intent`、`short_term_memory_summary`，并写入 `profile_snapshot` 元数据。

4. CozeAgent 工具调用增强
- `tool_calls` 现在返回真实执行结果，不再为空数组。
- 当前内置工具可查询监护人/联系人、最近检测记录、反诈热线和行动方案。

5. 响应字段兼容
- 检测返回新增：`detection_id`、`intent`、`short_term_memory_summary`、`escalation_actions`、`guardian_notification`。
- 旧字段保持兼容，现有前端不改造也可继续消费基础字段。

## 开发建议

- 数据库与日志文件属于运行态产物，不建议提交。
- 新增 API 时优先复用现有统一响应结构。
- 任务状态推送建议同时保留轮询降级路径，避免前端因 WS 中断阻塞。
