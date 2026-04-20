# 多模态反诈智能助手

本项目是一个面向电信网络诈骗场景的多模态反诈系统，包含：

- FastAPI 后端
- React + Vite Web 端
- Flutter 移动端
- LangGraph 完整工作流模式
- 支持自动构建与官方源自动同步的 RAG 知识库

## 当前完成情况

### 已实现

- 文本、图片、音频、视频输入
- 两种运行模式：
  - `flash`：低延迟单轮模式
  - `pro`：LangGraph 多步骤完整工作流模式
- 前期预警链路：
  - 硬红线规则
  - 软规则打分
  - 快速本地 RAG 探测
  - 图片 AI 率前期预警
- 个性化风险校准：
  - 角色化 Prompt 引导
  - 动态阈值
  - 历史风险调整
  - 年龄 / 性别 / 职业复合画像
- 主 RAG 知识库：
  - 启动自动构建
  - 热更新
  - 官方来源自动同步
  - 支持通过环境变量切换主索引后端
- 结构化干预输出：
  - 预警文案
  - 处置建议
  - 可信联系人 / 重点联系人联动
  - 报告生成
- Web 与移动端产品界面：
  - 登录注册
  - 设置
  - 联系人
  - 历史记录
  - 助手对话
- 移动端一键呼叫：
  - 拨打 `96110`
  - 拨打 `110`
  - 联系重点联系人
- Web 端一键求助：
  - 跳转公安部官方网络违法犯罪举报页面

### 尚未完全闭环

- 短信升级通知仍是预留接口，工作流已在，但尚未绑定具体短信服务商。
- 比赛交付件不在本仓库内闭环维护：
  - 数据集整理包
  - F1 / 准确率评估报告
  - PPT / 演示视频 / 提交材料
- Web 端一键求助目前是跳转官方页面，不是直接对接公安业务系统 API。

## 系统架构

### 后端

- `backend/`：API、认证、设置、联系人、历史、监控
- `src/`：感知、RAG、风险判断、干预、图工作流、存储
- `multimodal_input/`：OCR、音频、视频模型适配层

### 前端

- `frontend/`：React + TypeScript + Vite
- `anti_fraud_app/`：Flutter 移动端

## 核心能力

### 1. 多模态感知

- 文本清洗与直接输入
- 图片 OCR
- 音频 ASR 与伪造音频检测
- 视频关键帧提取、OCR 与伪造视频检测

### 2. 双运行模式

- `MODEL_MODE=flash`
  - 延迟更低
  - 单轮输出
  - 更适合演示和日常联调
- `MODEL_MODE=pro`
  - LangGraph 完整工作流
  - 更适合完整链路展示和节点级调试

### 3. RAG 知识库

- 主配置文件：`config/rag.yaml`
- 启动自动构建：`RAG_AUTO_BUILD=true`
- 官方源自动同步：`EXTERNAL_CASE_SYNC_ENABLED=true`
- 主后端可通过环境变量选择：
  - `RAG_INDEX_BACKEND=tfidf`
  - `RAG_INDEX_BACKEND=hybrid`
  - `RAG_INDEX_BACKEND=sentence-transformer`

说明：

- `RAG_INDEX_BACKEND` 只控制主 RAG 后端。
- 前期预警用的快速 RAG 为了延迟稳定，仍然保持轻量策略，不要求和主 RAG 后端完全一致。

### 4. 预警与护栏

- 大型结构化规则文件，包含：
  - 硬红线
  - 软信号
  - 角色化规则组
- 快速规则预警回退
- 快速 RAG 预警回退
- 面向高危诈骗脚本的确定性分数下限护栏

### 5. 个性化反诈逻辑

- 角色化 Prompt 引导
- 输出语言本地化
- 复合用户画像校准
- 短期与长期历史风险调整

### 6. 干预层

- 结构化报告生成
- 重点联系人联动
- 联系人邮箱收件人解析
- 移动端快捷呼叫
- Web 端快捷求助跳转

## 快速开始

### 1. 准备 `.env`

```powershell
Copy-Item .env.example .env
```

至少填写：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-omni-flash
SECRET_KEY=replace-with-long-random-secret
MODEL_MODE=flash
```

### 2. 启动后端

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python backend/app.py
```

后端地址：

- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 3. 启动 Web 端

```powershell
cd frontend
npm install
npm run dev
```

默认地址：

- `http://localhost:5173`

如需显式指定后端地址，可创建 `frontend/.env`：

```env
VITE_API_URL=http://localhost:8000
```

### 4. 启动 Flutter 移动端

```powershell
cd anti_fraud_app
flutter pub get
flutter run
```

Android 模拟器常用后端地址：

```env
API_BASE_URL=http://10.0.2.2:8000
```

## 推荐环境变量

完整模板见 [`.env.example`](C:/Users/administrator1/Desktop/fuchuang/.env.example)。

最常用的运行参数如下：

```env
MODEL_MODE=flash
RAG_AUTO_BUILD=true
RAG_FORCE_REBUILD=false
RAG_CONFIG_PATH=config/rag.yaml
RAG_INDEX_BACKEND=hybrid
EXTERNAL_CASE_SYNC_ENABLED=true
EXTERNAL_CASE_SYNC_INTERVAL_SECONDS=900
MODEL_WARMUP_ENABLED=true
LLM_WARMUP_ENABLED=true
MODEL_WARMUP_STARTUP_TIMEOUT=3
```

## 项目结构

```text
.
|-- backend/
|-- frontend/
|-- anti_fraud_app/
|-- src/
|-- multimodal_input/
|-- config/
|-- data/
|-- rag/
|-- test/
|-- requirements.txt
|-- run_system.py
`-- .env.example
```

## 已知限制

1. `src/action/sms_service.py` 目前仍是占位接口，未接入短信服务商时会返回 `provider_not_bound`。
2. 本仓库重点维护的是系统本身与恢复后的能力，不直接承载比赛提交物料。
3. 底层仍保留少量历史 `guardian_*` 命名，但用户可见层面已经基本切到可信联系人 / 重点联系人口径。

## 当前验证情况

最近一轮恢复与修复已覆盖：

- Web 前端构建通过
- 快速预警规则测试通过
- 外部案例自动同步测试通过
- RAG 后端保持测试通过
- 角色化 Prompt 个性化测试通过
- 联系人邮箱收件人逻辑测试通过
- 启动阶段 fast RAG 预热回归测试通过

## 说明

- 官方源自动同步配置文件为 `config/external_case_sources.yaml`。
- 如果修改 `RAG_INDEX_BACKEND`，建议重启后端后再进行构建或检索。
- Web 端的一键求助会打开公安部官方网络违法犯罪举报页面；真实紧急情况仍应直接拨打 `110`。
