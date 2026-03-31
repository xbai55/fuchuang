# 多模态输入模块 - 反诈智能助手

基于 AI 深度学习的多模态反诈检测系统，支持音频、视频和图像的并行处理与实时分析，可识别 AI 合成语音、视频换脸等诈骗手段。

## 目录

- [功能特点](#功能特点)
- [系统架构](#系统架构)
- [模块职责](#模块职责)
- [安装指南](#安装指南)
- [服务启动](#服务启动)
- [API 接口文档](#api 接口文档)
- [多模态协同流程](#多模态协同流程)
- [配置说明](#配置说明)
- [故障排查](#故障排查)

---

## 功能特点

### 核心能力
- **AI 伪造检测**：识别 AI 合成语音和视频换脸
- **语音识别 (ASR)**：16kHz 中文语音转文字，支持热词增强
- **语音端点检测 (VAD)**：精准定位语音片段
- **关键帧提取**：均匀采样 + 场景切换检测 + 人脸优先策略
- **OCR 文本识别**：基于 PaddleOCR 的多语言文本检测与识别
- **并发处理**：异步并行执行多项分析任务，秒级响应

### 技术亮点
- 🚀 **纯内存流处理**：音频文件无需落盘，内存中完成格式转换
- ⚡ **毫秒级预警**：检测到高危伪造时立即触发终端告警
- 🔀 **并行流水线**：视频分析与关键帧提取同时执行
- 📦 **模块化设计**：各服务独立部署，支持水平扩展

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 应用层                            │
├─────────────────┬─────────────────┬─────────────────────────┤
│   audio_module  │  video_module   │        ocr              │
│   (端口 8000)    │   (端口 8001)    │     (端口 8002)         │
├─────────────────┼─────────────────┼─────────────────────────┤
│ • 声纹鉴伪引擎   │ • 视频伪造检测   │ • PaddleOCR 识别引擎     │
│ • FunASR 语音识别│ • 关键帧提取器   │ • 多线程异步处理        │
│ • VAD 端点检测   │ • 人脸检测标注   │ • 批量帧处理            │
└─────────────────┴─────────────────┴─────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ 统一多模态服务   │
                    │   (端口 8000)    │
                    └─────────────────┘
```

### 服务端口分配

| 服务名称 | 端口 | API 端点 | 描述 |
|---------|------|---------|------|
| 音频服务 | 8000 | `/api/v1/analyze_audio_for_mllm` | 独立音频分析服务 |
| 视频服务 | 8001 | `/api/v1/analyze_video_for_mllm` | 独立视频分析服务 |
| OCR 服务 | 8002 | `/api/v1/ocr_analyze_keyframes` | 独立 OCR 识别服务 |
| 统一服务 | 8000 | `/api/v1/analyze_multimodal` | 多模态统一入口 |

> **注意**：音频服务和统一服务默认共用 8000 端口，可通过环境变量或配置文件修改。

---

## 模块职责

### 1. audio_module - 音频处理模块

**核心文件**：
- [`audio_inference.py`](./audio_module/audio_inference.py) - AI 伪造检测模型推理
- [`VAD.py`](./audio_module/VAD.py) - 语音识别与端点检测
- [`main.py`](./audio_module/main.py) - FastAPI 服务入口

**技术栈**：
- PyTorch + MobileNetV3-Small - 二分类伪造检测模型
- ModelScope FunASR - Paraformer-large 语音识别
- FFmpeg - 音频格式转换（内存管道）

**处理流程**：
```
音频上传 → FFmpeg 内存转码 (16kHz) → 并发生成:
  ├─ 声纹鉴伪 (5 秒截断加速) → 伪造概率
  └─ FunASR 识别 → 文本 + VAD 时间戳
→ 组装 MLLM Prompt → JSON 响应
```

**模型权重**：
- `./audio_module/weights/latest_best_audio_model.pth`

---

### 2. video_module - 视频处理模块

**核心文件**：
- [`video_inference.py`](./video_module/video_inference.py) - 视频伪造检测
- [`keyframe_extractor.py`](./video_module/keyframe_extractor.py) - 关键帧提取器
- [`main.py`](./video_module/main.py) - FastAPI 服务入口

**技术栈**：
- PyTorch + EfficientNet-B0 - 视频伪造分类模型
- OpenCV + Haar Cascade - 人脸检测
- FFmpeg - 视频抽帧（均匀采样 + 场景切换）

**处理流程**：
```
视频上传 → 保存临时文件 → 并发生成:
  ├─ 视频鉴伪 (第 1 秒帧) → 伪造概率
  └─ 关键帧提取 → 人脸标注 → 帧路径列表
→ 组装 MLLM Prompt → JSON 响应
```

**关键帧策略**：
- 均匀采样：每 2 秒 1 帧
- 场景切换：阈值 0.35
- 人脸优先：含人脸帧优先返回
- 最大帧数：20 帧

**模型权重**：
- `./video_module/weights/final_model.pth`

---

### 3. ocr - OCR处理模块

**核心文件**：
- [`ocr_async_processor.py`](./ocr/ocr_async_processor.py) - 异步 OCR处理器
- [`main.py`](./ocr/main.py) - FastAPI 服务入口（含视频 OCR 并行处理）
- [`config.py`](./ocr/config.py) - OCR 配置

**技术栈**：
- PaddleOCR (PaddlePaddle) - 文本检测 + 方向分类 + 文本识别
- ThreadPoolExecutor - 多线程并行处理
- asyncio.gather - 异步任务编排

**处理流程**：
```
关键帧路径列表 → ThreadPoolExecutor 并行识别:
  ├─ 文本检测 (DB)
  ├─ 方向分类
  └─ 文本识别 (SVTR)
→ 汇总结果 → 生成 Agent Prompt → JSON 响应
```

**支持模式**：
- 单帧 OCR：`/api/v1/ocr_analyze_keyframes`
- 批量 OCR：接收图像文件列表
- JSON 路径输入：`/api/v1/ocr_analyze_from_json`
- 视频 OCR 并行：`/api/v1/analyze_video_ocr_parallel`

---

## 安装指南

### 前置要求

- **Python**: 3.10+
- **FFmpeg**: 必须安装并加入 PATH（用于音视频处理）
- **CUDA**: 可选，推荐 11.7+（GPU 加速）

### 步骤 1：克隆项目

```bash
cd c:\Users\xbai55\Desktop\fc\multimodal_input
```

### 步骤 2：安装依赖

```bash
# 安装主依赖
pip install -r requirements.txt

# Windows 用户如需 GPU 支持，先安装 PyTorch CUDA 版本
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 步骤 3：下载模型权重

```bash
# 创建权重目录
mkdir -p ./audio_module/weights
mkdir -p ./video_module/weights

# 将预训练权重放入对应目录：
# - ./audio_module/weights/latest_best_audio_model.pth
# - ./video_module/weights/final_model.pth
```

### 步骤 4：验证安装

```bash
# 检查模型权重
python run_multimodal.py check

# 健康检查（启动服务后）
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## 服务启动

### 方式一：使用启动脚本（推荐）

[`run_multimodal.py`](./run_multimodal.py) 提供统一的服务管理：

```bash
# 启动统一多模态服务（默认，端口 8000）
python run_multimodal.py unified

# 启动独立音频服务（端口 8000）
python run_multimodal.py audio

# 启动独立视频服务（端口 8001）
python run_multimodal.py video

# 启动独立 OCR 服务（端口 8002）
python run_multimodal.py ocr

# 启动所有服务（多进程）
python run_multimodal.py all

# 检查模型权重文件
python run_multimodal.py check
```

### 方式二：手动启动

```bash
# 音频服务
cd audio_module && python main.py

# 视频服务
cd video_module && python main.py

# OCR 服务
cd ocr && python main.py

# 统一服务（根目录）
python main.py
```

### 方式三：指定端口

```bash
# 通过环境变量修改端口
export AUDIO_SERVICE_PORT=8005
export VIDEO_SERVICE_PORT=8006
export OCR_SERVICE_PORT=8007

python run_multimodal.py all
```

---

## API 接口文档

### 1. 音频分析接口

**端点**: `POST /api/v1/analyze_audio_for_mllm`  
**服务**: 音频服务 (端口 8000)

**请求**:
```http
POST http://localhost:8000/api/v1/analyze_audio_for_mllm
Content-Type: multipart/form-data

file: <音频文件> (.wav, .mp3, .m4a 等)
```

**响应示例**:
```json
{
  "status": "success",
  "cost_time": "1.23s",
  "data": {
    "mllm_prompt": "以下是一段监控截获的音频分析数据...\n【系统前置判定】：极大概率为 AI 伪造合成语音 (置信度 0.95)。\n【语音识别文本】："你好，我是公安局专案组..."\n请结合上述前置判定与文本内容...",
    "raw_text": "你好，我是公安局专案组...",
    "is_fake_alert": true
  }
}
```

---

### 2. 视频分析接口

**端点**: `POST /api/v1/analyze_video_for_mllm`  
**服务**: 视频服务 (端口 8001)

**请求**:
```http
POST http://localhost:8001/api/v1/analyze_video_for_mllm
Content-Type: multipart/form-data

file: <视频文件> (.mp4, .avi, .mov 等)
```

**响应示例**:
```json
{
  "status": "success",
  "task_id": "abc123-def456",
  "cost_time": "3.45s",
  "data": {
    "mllm_prompt": "以下是一段监控截获的视频分析数据...\n【系统前置判定】：未检测到明显 AI 伪造痕迹。\n【关键帧信息】：共提取 10 帧...",
    "is_fake_alert": false,
    "fake_probability": 0.23,
    "keyframe_dir": "/tmp/keyframes/abc123"
  }
}
```

---

### 3. OCR 分析接口

**端点**: `POST /api/v1/ocr_analyze_keyframes`  
**服务**: OCR 服务 (端口 8002)

**请求**:
```http
POST http://localhost:8002/api/v1/ocr_analyze_keyframes
Content-Type: multipart/form-data

frame_files: <图像文件列表> (.jpg, .png 等)
```

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "total_frames_processed": 5,
    "summary_texts": [
      {"text": "公安局", "confidence": 0.98, "frame_path": "..."},
      {"text": "安全账户", "confidence": 0.95, "frame_path": "..."}
    ],
    "agent_prompt": "【视频 OCR 文本分析】：已处理 5 个关键帧..."
  }
}
```

---

### 4. 统一多模态接口

**端点**: `POST /api/v1/analyze_multimodal`  
**服务**: 统一服务 (端口 8000)

**请求**:
```http
POST http://localhost:8000/api/v1/analyze_multimodal
Content-Type: multipart/form-data

input_type: "video"|"audio"|"image"
file: <媒体文件>
```

**响应示例** (视频输入):
```json
{
  "status": "success",
  "task_id": "xyz789",
  "cost_time": "4.56s",
  "data": {
    "mllm_prompt": "以下是一段监控截获的视频分析数据...\n【系统前置判定】：极大概率为 AI 伪造合成视频 (置信度 0.87)。\n【视频 OCR 文本分析】：已处理 10 个关键帧...",
    "is_fake_alert": true,
    "fake_probability": 0.87,
    "keyframe_dir": "/tmp/keyframes/xyz789",
    "ocr_results": {...}
  }
}
```

---

### 5. 健康检查接口

**端点**: `GET /health`

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## 多模态协同流程

### 视频完整处理流程

```
用户上传视频
     │
     ▼
┌─────────────────────────────────────┐
│  统一服务 /api/v1/analyze_multimodal │
└─────────────────────────────────────┘
     │
     ├──────────────────┐
     ▼                  ▼
┌─────────────┐   ┌──────────────┐
│ 视频伪造检测 │   │ 关键帧提取器  │  ← 并行执行 (asyncio.gather)
│ (1.0s 帧)    │   │ (均匀 + 场景)  │
└─────────────┘   └──────────────┘
     │                  │
     │                  ▼
     │          ┌──────────────┐
     │          │ 人脸检测标注  │
     │          └──────────────┘
     │                  │
     └──────────────────┘
                │
                ▼
       ┌────────────────┐
       │  等待两者完成   │
       └────────────────┘
                │
                ▼
       ┌─────────────────┐
       │ OCR 异步处理器   │
       │ (多线程并行识别) │
       └─────────────────┘
                │
                ▼
       ┌─────────────────┐
       │ 合并结果        │
       │ - 伪造概率       │
       │ - 关键帧路径     │
       │ - OCR 文本       │
       │ - Agent Prompt  │
       └─────────────────┘
                │
                ▼
         返回 JSON 响应
```

### 音频处理流程

```
用户上传音频
     │
     ▼
┌─────────────────────────────────┐
│ /api/v1/analyze_audio_for_mllm  │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────┐
│ FFmpeg 内存转码  │ (16kHz, 单声道)
└─────────────────┘
     │
     ├──────────────────┐
     ▼                  ▼
┌─────────────┐   ┌──────────────┐
│ 声纹鉴伪引擎 │   │ FunASR 识别  │  ← 并行执行 (asyncio.gather)
│ (5 秒截断)    │   │ + VAD 时间戳 │
└─────────────┘   └──────────────┘
     │                  │
     ▼                  ▼
┌─────────────────────────────────┐
│  伪造概率 > 0.8 ? 触发预警      │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────┐
│ 组装 MLLM Prompt│
└─────────────────┘
     │
     ▼
  返回 JSON 响应
```

---

## 配置说明

### 环境变量

| 变量名 | 描述 | 默认值 |
|-------|------|--------|
| `AUDIO_SERVICE_PORT` | 音频服务端口 | 8000 |
| `VIDEO_SERVICE_PORT` | 视频服务端口 | 8001 |
| `OCR_SERVICE_PORT` | OCR 服务端口 | 8002 |
| `UNIFIED_SERVICE_PORT` | 统一服务端口 | 8000 |
| `AUDIO_MODEL_PATH` | 音频模型路径 | `./audio_module/weights/latest_best_audio_model.pth` |
| `VIDEO_MODEL_PATH` | 视频模型路径 | `./video_module/weights/final_model.pth` |
| `OCR_USE_ANGLE_CLS` | 启用角度分类器 | true |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` | 禁用 PaddleOCR 源检查 | True |

### 配置文件

[`config.py`](./config.py) 提供完整的配置管理：

```python
from config import get_config

config = get_config()

# 获取音频服务配置
audio_config = config.get_service_config('audio')
print(f"Audio endpoint: http://localhost:{audio_config.port}{audio_config.endpoint}")

# 获取 LangGraph 集成配置
langgraph_config = config.get_langgraph_node_config()
```

---

## 故障排查

### 常见问题

#### 1. 模型权重文件缺失

```
⚠️  警告：以下模型权重文件缺失：
   - 音频深度伪造检测模型：./audio_module/weights/latest_best_audio_model.pth
   - 视频深度伪造检测模型：./video_module/weights/final_model.pth
```

**解决方案**:
```bash
python run_multimodal.py check
# 确认权重文件存在于上述路径
```

---

#### 2. FFmpeg 未安装

```
RuntimeError: FFmpeg 未安装或不在系统 PATH 中
```

**解决方案**:

**Windows**:
```powershell
# 使用 winget 安装
winget install ffmpeg

# 或手动下载安装包：https://ffmpeg.org/download.html
# 解压后将 bin 目录加入 PATH（如 C:\ffmpeg\bin）
```

**Linux**:
```bash
sudo apt-get install ffmpeg  # Debian/Ubuntu
sudo yum install ffmpeg      # CentOS/RHEL
```

**macOS**:
```bash
brew install ffmpeg
```

---

#### 3. CUDA 不可用

```
UserWarning: CUDA is not available, using CPU mode
```

**解决方案**:
- 检查 NVIDIA 驱动：`nvidia-smi`
- 重新安装 PyTorch CUDA 版本：
```bash
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

---

#### 4. PaddleOCR 首次加载慢

**原因**: 首次运行会自动下载模型

**解决方案**:
```bash
# 预下载模型
python -c "from paddleocr import PaddleOCR; PaddleOCR()"
```

---

#### 5. 音频识别失败

```
ASR 推理发生错误：Input sample rate mismatch...
```

**解决方案**:
- 确保音频为 16kHz（FFmpeg 会自动转换）
- 检查音频是否过短（<100ms）

---

### 日志调试

启动时添加 `--reload` 参数启用热重载：
```bash
uvicorn audio_module.main:app --host 0.0.0.0 --port 8000 --reload
```

查看实时日志：
```bash
# Linux/macOS
tail -f nohup.out

# Windows PowerShell
Get-Content nohup.out -Wait
```

---

## 性能基准

| 任务类型 | 平均耗时 | 备注 |
|---------|---------|------|
| 音频分析 (5 秒) | 0.2-0.5s | GPU 加速 |
| 视频伪造检测 | 0.1-0.3s | 单帧推理 |
| 关键帧提取 (10 秒视频) | 2-4s | 含人脸检测 |
| OCR 识别 (10 帧) | 1-3s | 多线程并行 |
| 完整视频流程 | 3-6s | 并行优化后 |

---

## 许可证

本项目仅供学习和研究使用。

---

## 联系方式

如有问题请提交 Issue 或联系开发团队。
