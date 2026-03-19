# 多模态输入模块

多模态输入模块负责处理音频、视频和图像输入，利用AI模型分析内容并识别潜在的诈骗活动。

## 功能特点

- **音频分析**：支持语音转文字、声纹鉴定，识别AI合成语音
- **视频分析**：检测视频伪造，提取关键帧进行OCR识别
- **图像OCR**：识别图像中的文本内容
- **统一接口**：提供统一的多模态处理接口

## 服务架构

- [audio_module](./audio_module) - 音频分析服务
  - 语音识别 (ASR)
  - 声纹伪造检测
  - 语音端点检测 (VAD)

- [video_module](./video_module) - 视频分析服务
  - 深度伪造检测
  - 关键帧提取
  - 人脸识别标注

- [ocr](./ocr) - OCR处理服务
  - 图像文本识别
  - 关键帧批量处理

## 快速开始

### 1. 安装依赖

```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装音频模块依赖
cd audio_module && pip install -r requirements.txt && cd ..

# 安装视频模块依赖
cd video_module && pip install -r requirements.txt && cd ..

# 安装OCR模块依赖
cd ocr && pip install -r requirements.txt && cd ..
```

### 2. 下载模型权重

```bash
# 创建权重目录
mkdir -p ./audio_module/weights
mkdir -p ./video_module/weights

# 从模型仓库下载权重文件
# - ./audio_module/weights/latest_best_audio_model.pth
# - ./video_module/weights/final_model.pth
```

### 3. 启动服务

#### 使用启动脚本（推荐）

```bash
# 启动统一多模态服务 (默认)
python run_multimodal.py unified

# 启动音频服务
python run_multimodal.py audio

# 启动视频服务
python run_multimodal.py video

# 启动OCR服务
python run_multimodal.py ocr

# 启动所有服务
python run_multimodal.py all

# 检查模型权重
python run_multimodal.py check
```

#### 手动启动服务

```bash
# 启动音频服务 (端口 8000)
cd audio_module && python main.py

# 启动视频服务 (端口 8001)
cd video_module && python main.py

# 启动OCR服务 (端口 8002)
cd ocr && python main.py
```

## API 接口

### 音频分析接口

```
POST /api/v1/analyze_audio_for_mllm
Content-Type: multipart/form-data

file: [音频文件]
```

### 视频分析接口

```
POST /api/v1/analyze_video_for_mllm
Content-Type: multipart/form-data

file: [视频文件]
```

### OCR分析接口

```
POST /api/v1/ocr_analyze_keyframes
Content-Type: multipart/form-data

frame_files: [图像文件列表]
```

### 统一多模态接口

```
POST /api/v1/analyze_multimodal
Content-Type: multipart/form-data

input_type: ["audio", "video", "image"]
file: [媒体文件]
```

## LangGraph 集成

多模态服务可以轻松集成到LangGraph工作流中：

```python
from langgraph_integration import create_multimodal_nodes

nodes = create_multimodal_nodes()

# 在你的LangGraph中使用这些节点
# nodes["audio_processing"]
# nodes["video_processing"]
# nodes["image_processing"]
```

## 配置

服务配置可以通过 [config.py](./config.py) 文件管理，支持环境变量覆盖：

```bash
export AUDIO_SERVICE_PORT=8005
export VIDEO_SERVICE_PORT=8006
export OCR_SERVICE_PORT=8007
```

## 服务状态检查

启动服务后，可以访问以下健康检查端点：

- 音频服务: `http://localhost:8000/health`
- 视频服务: `http://localhost:8001/health`
- OCR服务: `http://localhost:8002/health`

## 错误处理

常见错误及解决方案：

1. **模型权重文件缺失**：
   - 确保权重文件存在于正确的路径
   - 运行 `python run_multimodal.py check` 检查模型文件

2. **FFmpeg 未安装**：
   - 安装FFmpeg并将其添加到PATH环境变量

3. **CUDA 不可用**：
   - 修改配置使用CPU模式
   - 检查CUDA和PyTorch版本兼容性
```