# PaddleOCR → RapidOCR 迁移指南

## 概述

已将项目中的 OCR 引擎从 PaddleOCR 迁移至 RapidOCR，以获得更快的推理速度。

## 关键改进

1. **性能提升**：RapidOCR 基于 ONNX Runtime，推理速度比 PaddleOCR 快 2-5 倍
2. **无 CUDA 依赖**：无需复杂的 CUDA/cuDNN 配置，CPU 即可高效运行
3. **统一接口**：通过 Adapter 模式保持 API 兼容，上层业务代码无需修改

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `ocr_adapter.py` | 新增：OCR Adapter 抽象层 |
| `ocr_async_processor.py` | 重写：使用 Adapter 替代直接 PaddleOCR 调用 |
| `requirements.txt` | 更新：替换 paddlepaddle-gpu/paddleocr 为 rapidocr_onnxruntime |

## 快速验证

```bash
# 1. 安装新依赖
pip uninstall paddlepaddle-gpu paddleocr -y
pip install rapidocr_onnxruntime>=1.4.0

# 2. 运行测试
python -c "from multimodal_input.ocr.ocr_adapter import RapidOCRAdapter; ocr = RapidOCRAdapter(); print('RapidOCR 初始化成功')"
```

## 使用方法

### 基本使用（与之前完全一致）

```python
from multimodal_input.ocr.ocr_async_processor import AsyncKeyframeOCRProcessor

# 初始化（默认使用 RapidOCR）
processor = AsyncKeyframeOCRProcessor()

# 处理关键帧（接口不变）
result = await processor.process_keyframes(["frame1.jpg", "frame2.jpg"])
```

### 切换回 PaddleOCR（如需要）

```python
# 在初始化时指定 backend
processor = AsyncKeyframeOCRProcessor(backend="paddleocr")
```

### 直接使用 Adapter

```python
from multimodal_input.ocr.ocr_adapter import create_ocr_adapter
import cv2

# 创建 RapidOCR 适配器
ocr = create_ocr_adapter(backend="rapidocr", lang="ch")

# 读取图片
img = cv2.imread("test.jpg")

# 执行 OCR
results = ocr.ocr(img)

# 输出结果
for item in results:
    print(f"文本: {item.text}, 置信度: {item.confidence}")
```

## 输出格式对比

### PaddleOCR 原格式
```python
[[[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], ("文本", 0.98)], ...]
```

### RapidOCR 新格式（已统一）
```python
[OCRResultItem(text="文本", confidence=0.98, bbox=[x1,y1,x2,y2,x3,y3,x4,y4]), ...]
```

通过 Adapter 层，两者输出已统一为 `List[OCRResultItem]`。

## 性能优化建议

### 1. 线程数配置

通过环境变量调整 ONNX Runtime 线程数：

```bash
# Windows
set OCR_INTER_OP_THREADS=4
set OCR_INTRA_OP_THREADS=2

# Linux/Mac
export OCR_INTER_OP_THREADS=4
export OCR_INTRA_OP_THREADS=2
```

### 2. 批处理优化

RapidOCR 适合批量处理，保持现有的 `process_keyframes` 批量调用方式。

### 3. 图片预处理

确保输入图片为 OpenCV 格式（numpy array, HWC, BGR），避免重复解码。

## 故障排查

### 问题：ImportError: rapidocr_onnxruntime 未安装
**解决**：`pip install rapidocr_onnxruntime>=1.4.0`

### 问题：模型下载慢
**解决**：RapidOCR 首次使用会自动下载模型，可设置镜像：
```bash
export HF_ENDPOINT=https://hf-mirror.com  # 国内镜像
```

### 问题：内存占用高
**解决**：减少线程数：
```bash
export OCR_INTER_OP_THREADS=2
export OCR_INTRA_OP_THREADS=1
```

## 性能对比参考

| 指标 | PaddleOCR (CPU) | RapidOCR (ONNX) |
|------|----------------|-----------------|
| 单图推理 | 200-500ms | 50-150ms |
| 内存占用 | 高（Paddle 框架） | 低（ONNX Runtime） |
| 首次加载 | 慢 | 快 |
| 依赖复杂度 | 高（CUDA 等） | 低 |

## 回滚方案

如需回滚到 PaddleOCR：

1. 修改 `requirements.txt`，取消注释 paddlepaddle-gpu/paddleocr
2. 修改初始化代码：
   ```python
   processor = AsyncKeyframeOCRProcessor(backend="paddleocr")
   ```
