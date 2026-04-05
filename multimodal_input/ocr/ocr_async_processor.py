import os
from typing import List, Dict, Any, Optional
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import cv2

# 使用新的 OCR Adapter 替代直接导入 PaddleOCR
from .ocr_adapter import create_ocr_adapter, BaseOCRAdapter, OCRResultItem


class AsyncKeyframeOCRProcessor:
    """
    异步处理关键帧OCR的类，使用 RapidOCR 实现高性能推理。
    通过 OCR Adapter 模式支持灵活切换后端。
    """

    def __init__(
        self,
        det_model_dir: str = None,
        rec_model_dir: str = None,
        cls_model_dir: str = None,
        use_angle_cls: bool = True,
        lang: str = 'ch',
        backend: str = "rapidocr"
    ):
        """
        初始化OCR处理器

        Args:
            det_model_dir: 检测模型路径（保留参数，RapidOCR 使用内置模型）
            rec_model_dir: 识别模型路径（保留参数，RapidOCR 使用内置模型）
            cls_model_dir: 分类模型路径（保留参数，RapidOCR 使用内置模型）
            use_angle_cls: 是否使用方向分类器
            lang: 识别语言，默认中文
            backend: OCR 后端，可选 "rapidocr" 或 "paddleocr"
        """
        # 创建线程池执行器
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._ocr_adapter: Optional[BaseOCRAdapter] = None
        self._backend = backend
        self._use_angle_cls = use_angle_cls
        self._lang = lang
        self._pipeline_lock = threading.Lock()

        # RapidOCR 性能优化配置
        self._inter_op_threads = self._get_int_env("OCR_INTER_OP_THREADS", 4)
        self._intra_op_threads = self._get_int_env("OCR_INTRA_OP_THREADS", 2)

        self._init_pipeline()

    def _get_int_env(self, key: str, default: int) -> int:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except ValueError:
            return default

    def _init_pipeline(self) -> None:
        """初始化 OCR 后端。"""
        try:
            self._ocr_adapter = create_ocr_adapter(
                backend=self._backend,
                use_angle_cls=self._use_angle_cls,
                lang=self._lang,
                inter_op_num_threads=self._inter_op_threads,
                intra_op_num_threads=self._intra_op_threads,
            )
            print(f"[OCR] 使用后端: {self._backend}")
        except Exception as e:
            raise RuntimeError(f"OCR 初始化失败: {e}")

    async def process_keyframes(self, keyframe_paths: List[str]) -> Dict[str, Any]:
        """
        异步处理多个关键帧，提取其中的文字信息

        Args:
            keyframe_paths: 关键帧路径列表

        Returns:
            包含OCR结果的字典
        """
        loop = asyncio.get_event_loop()

        # 并行处理所有关键帧
        tasks = [
            loop.run_in_executor(self.executor, self._process_single_frame, frame_path)
            for frame_path in keyframe_paths if os.path.exists(frame_path)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 组织结果
        ocr_results = {}
        for i, frame_path in enumerate([p for p in keyframe_paths if os.path.exists(p)]):
            if isinstance(results[i], Exception):
                print(f"Error processing {frame_path}: {results[i]}")
                continue
            ocr_results[frame_path] = results[i]

        # 整理最终结果
        final_result = {
            "status": "success",
            "total_frames_processed": len(ocr_results),
            "frames_results": ocr_results,
            "summary_texts": self._aggregate_texts(ocr_results)
        }

        return final_result

    def _process_single_frame(self, frame_path: str) -> Dict[str, Any]:
        """
        处理单个关键帧

        Args:
            frame_path: 帧路径

        Returns:
            单帧OCR结果
        """
        # 读取图片（支持路径或 numpy 数组）
        if isinstance(frame_path, str):
            img = cv2.imread(frame_path)
            if img is None:
                raise ValueError(f"无法读取图片: {frame_path}")
        else:
            img = frame_path

        # 使用 Adapter 执行 OCR
        result_items = self._ocr_adapter.ocr(img)
        texts_with_positions = self._convert_to_legacy_format(result_items)

        return {
            "frame_path": frame_path,
            "texts": texts_with_positions,
            "total_text_count": len(texts_with_positions),
            "average_confidence": sum([t['confidence'] for t in texts_with_positions]) /
            len(texts_with_positions) if texts_with_positions else 0,
        }

    def _convert_to_legacy_format(self, items: List[OCRResultItem]) -> List[Dict[str, Any]]:
        """
        将 OCRResultItem 转换为旧的输出格式，保持兼容性
        """
        return [
            {
                "text": item.text,
                "confidence": item.confidence,
                "bbox": item.bbox
            }
            for item in items
        ]

    def _aggregate_texts(self, ocr_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        汇总所有帧的文本结果

        Args:
            ocr_results: OCR结果字典

        Returns:
            汇总的文本列表
        """
        all_texts = []
        for frame_data in ocr_results.values():
            for text_item in frame_data['texts']:
                all_texts.append({
                    "frame_path": frame_data['frame_path'],
                    "text": text_item['text'],
                    "confidence": text_item['confidence']
                })

        # 按置信度降序排列
        all_texts.sort(key=lambda x: x['confidence'], reverse=True)
        return all_texts

    async def process_video_analysis(self, keyframe_result_obj) -> Dict[str, Any]:
        """
        异步处理KeyframeResult对象，适配video_module的输出

        Args:
            keyframe_result_obj: video_module.keyframe_extractor.KeyframeResult对象

        Returns:
            包含OCR分析结果的字典
        """
        # 获取关键帧路径
        frame_paths = [frame.path for frame in keyframe_result_obj.frames]
        print(f"这个是ocr_async_processor用于检测路径传输成功：{frame_paths}")
        # 异步处理这些帧
        ocr_results = await self.process_keyframes(frame_paths)

        # 添加额外的帧元数据
        for frame_meta in keyframe_result_obj.frames:
            frame_path = frame_meta.path
            if frame_path in ocr_results['frames_results']:
                ocr_results['frames_results'][frame_path]['metadata'] = {
                    'frame_index': frame_meta.frame_index,
                    'timestamp_sec': frame_meta.timestamp_sec,
                    'source': frame_meta.source,
                    'has_face': frame_meta.has_face,
                    'face_count': frame_meta.face_count
                }

        # 生成给agent的提示信息
        agent_prompt = self._generate_agent_prompt(ocr_results)
        ocr_results['agent_prompt'] = agent_prompt

        return ocr_results

    def _generate_agent_prompt(self, ocr_results: Dict[str, Any]) -> str:
        """
        生成给AI agent的提示信息

        Args:
            ocr_results: OCR结果

        Returns:
            适合AI agent理解的文本描述
        """
        total_frames = ocr_results['total_frames_processed']
        high_conf_texts = [t for t in ocr_results['summary_texts'] if t['confidence'] > 0.8]

        prompt_parts = [
            f"【视频OCR文本分析】：已处理 {total_frames} 个关键帧。",
            f"共检测到 {len(high_conf_texts)} 个高置信度文本片段。"
        ]

        if high_conf_texts:
            prompt_parts.append("\n高置信度文本内容（按置信度排序）:")
            for i, text_item in enumerate(high_conf_texts[:10]):  # 最多显示10个
                prompt_parts.append(f"  {i+1}. \"{text_item['text']}\" (置信度: {text_item['confidence']:.2f}, 来自: {os.path.basename(text_item['frame_path'])})")

        if len(high_conf_texts) > 10:
            prompt_parts.append(f"\n... 还有 {len(high_conf_texts) - 10} 个较低置信度的文本片段")

        prompt_parts.append("\n请结合OCR文本内容分析视频中可能存在的诈骗风险。")

        return "\n".join(prompt_parts)

    async def health_check(self) -> bool:
        """检查 OCR 模型是否加载。"""
        return self._ocr_adapter is not None
