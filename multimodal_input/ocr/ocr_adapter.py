"""
OCR Adapter Pattern - 统一 OCR 接口
支持 PaddleOCR 和 RapidOCR 两种后端
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np


class OCRResultItem:
    """统一的 OCR 结果项"""
    def __init__(self, text: str, confidence: float, bbox: Optional[List[float]] = None):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bbox": self.bbox
        }


class BaseOCRAdapter(ABC):
    """OCR 适配器基类"""

    @abstractmethod
    def __init__(self, use_angle_cls: bool = True, lang: str = 'ch', **kwargs):
        pass

    @abstractmethod
    def ocr(self, img: Union[str, np.ndarray]) -> List[OCRResultItem]:
        """
        执行 OCR 识别

        Args:
            img: 图片路径 (str) 或 numpy 数组 (OpenCV 格式)

        Returns:
            OCRResultItem 列表
        """
        pass


class RapidOCRAdapter(BaseOCRAdapter):
    """
    RapidOCR 适配器 - 高性能推理
    使用 rapidocr_onnxruntime 实现
    """

    def __init__(self, use_angle_cls: bool = True, lang: str = 'ch', **kwargs):
        """
        初始化 RapidOCR

        Args:
            use_angle_cls: 是否使用方向分类器（RapidOCR 内部自动处理）
            lang: 语言，支持 'ch', 'en', 'ch_sim' 等
            **kwargs: 额外参数传递给 RapidOCR
                - model_path: 模型路径
                - inter_op_num_threads: 线程数（默认 4）
                - intra_op_num_threads: 内部线程数（默认 2）
        """
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            raise ImportError(
                "rapidocr_onnxruntime 未安装。请运行：pip install rapidocr_onnxruntime"
            )

        self._use_angle_cls = use_angle_cls
        self._lang = lang

        # RapidOCR 配置参数
        config = {
            # ONNX Runtime 配置
            "inter_op_num_threads": kwargs.get("inter_op_num_threads", 4),
            "intra_op_num_threads": kwargs.get("intra_op_num_threads", 2),
        }

        # 如果需要指定模型路径
        if "model_path" in kwargs:
            config["model_path"] = kwargs["model_path"]

        # 初始化 RapidOCR
        self._ocr = RapidOCR(**config)

    def ocr(self, img: Union[str, np.ndarray]) -> List[OCRResultItem]:
        """
        执行 OCR 识别

        Args:
            img: 图片路径或 numpy 数组 (HWC, BGR格式，OpenCV默认)

        Returns:
            OCRResultItem 列表
        """
        # RapidOCR 返回格式：(result, elapse)
        # result: [[bbox, text, confidence], ...]
        # bbox: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        result, elapse = self._ocr(img)

        if not result:
            return []

        items = []
        for item in result:
            # RapidOCR 返回格式: [bbox, text, confidence]
            if len(item) >= 3:
                bbox = item[0]  # 4个点的坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text = item[1]  # 识别文本
                confidence = float(item[2])  # 置信度

                # 转换 bbox 为扁平列表 [x1, y1, x2, y2, x3, y3, x4, y4]
                flat_bbox = []
                for point in bbox:
                    flat_bbox.extend([float(point[0]), float(point[1])])

                items.append(OCRResultItem(
                    text=str(text),
                    confidence=confidence,
                    bbox=flat_bbox
                ))

        return items


class PaddleOCRAdapter(BaseOCRAdapter):
    """
    PaddleOCR 适配器 - 保持向后兼容
    """

    def __init__(self, use_angle_cls: bool = True, lang: str = 'ch', **kwargs):
        from paddleocr import PaddleOCR

        self._use_angle_cls = use_angle_cls
        self._lang = lang

        paddle_kwargs = {
            "lang": lang,
            "use_angle_cls": use_angle_cls,
        }

        # 添加其他配置
        if "enable_mkldnn" in kwargs:
            paddle_kwargs["enable_mkldnn"] = kwargs["enable_mkldnn"]
        if "cpu_threads" in kwargs:
            paddle_kwargs["cpu_threads"] = kwargs["cpu_threads"]

        self._ocr = PaddleOCR(**paddle_kwargs)

    def ocr(self, img: Union[str, np.ndarray]) -> List[OCRResultItem]:
        """执行 OCR 识别"""
        result = self._ocr.ocr(img, cls=self._use_angle_cls)

        if not result or not result[0]:
            return []

        items = []
        for line in result[0]:
            # PaddleOCR 格式: [bbox, (text, confidence)]
            bbox = line[0]  # 4个点的坐标
            text = line[1][0]  # 文本
            confidence = float(line[1][1])  # 置信度

            # 转换 bbox 为扁平列表
            flat_bbox = []
            for point in bbox:
                flat_bbox.extend([float(point[0]), float(point[1])])

            items.append(OCRResultItem(
                text=str(text),
                confidence=confidence,
                bbox=flat_bbox
            ))

        return items


def create_ocr_adapter(
    backend: str = "rapidocr",
    use_angle_cls: bool = True,
    lang: str = 'ch',
    **kwargs
) -> BaseOCRAdapter:
    """
    工厂函数：创建 OCR 适配器

    Args:
        backend: OCR 后端，可选 "rapidocr" 或 "paddleocr"
        use_angle_cls: 是否使用方向分类
        lang: 语言代码
        **kwargs: 额外配置参数

    Returns:
        BaseOCRAdapter 实例
    """
    if backend.lower() == "rapidocr":
        return RapidOCRAdapter(use_angle_cls=use_angle_cls, lang=lang, **kwargs)
    elif backend.lower() == "paddleocr":
        return PaddleOCRAdapter(use_angle_cls=use_angle_cls, lang=lang, **kwargs)
    else:
        raise ValueError(f"不支持的 OCR 后端: {backend}，可选: rapidocr, paddleocr")
