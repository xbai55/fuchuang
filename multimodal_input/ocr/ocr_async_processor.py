import os
from typing import List, Dict, Any, Optional
import asyncio
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor

from paddleocr import PaddleOCR


class AsyncKeyframeOCRProcessor:
    """
    异步处理关键帧OCR的类，优先使用稳定的 PaddleOCR，
    在配置允许时可尝试 PaddleOCRVL。
    """
    
    def __init__(self, det_model_dir: str = None, rec_model_dir: str = None, cls_model_dir: str = None, 
                 use_angle_cls: bool = True, lang: str = 'ch'):
        """
        初始化OCR处理器
        
        Args:
            det_model_dir: 文本检测模型路径
            rec_model_dir: 文字识别模型路径
            cls_model_dir: 方向分类模型路径
            use_angle_cls: 是否使用角度分类器
            lang: 识别语言，默认中文
        """
        # 检查模型权重文件是否存在
        if det_model_dir and not os.path.exists(det_model_dir):
            raise FileNotFoundError(f"检测模型权重文件不存在: {det_model_dir}")
        if rec_model_dir and not os.path.exists(rec_model_dir):
            raise FileNotFoundError(f"识别模型权重文件不存在: {rec_model_dir}")
        if cls_model_dir and not os.path.exists(cls_model_dir):
            raise FileNotFoundError(f"分类模型权重文件不存在: {cls_model_dir}")

        # 创建线程池执行器
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.pipeline = None
        self._backend = ""
        self._use_angle_cls = use_angle_cls
        self._lang = lang
        self._pipeline_lock = threading.Lock()
        mkldnn_default = False if os.name == "nt" else True
        self._classic_enable_mkldnn = self._get_bool_env("OCR_ENABLE_MKLDNN", mkldnn_default)
        self._classic_cpu_threads = self._get_int_env("OCR_CPU_THREADS", 4)
        self._mkldnn_fallback_applied = not self._classic_enable_mkldnn

        # 避免每次启动都做模型源可达性探测，减少初始化阻塞。
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

        self._init_pipeline(use_angle_cls=use_angle_cls, lang=lang)

    def _get_bool_env(self, key: str, default: bool) -> bool:
        value = os.getenv(key)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _get_int_env(self, key: str, default: int) -> int:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except ValueError:
            return default

    def _init_pipeline(self, use_angle_cls: bool, lang: str) -> None:
        """初始化 OCR 后端，优先稳定后端，必要时回退。"""
        init_errors = []
        prefer_vl = os.getenv("USE_PADDLE_OCR_VL", "false").lower() in {"1", "true", "yes"}
        allow_vl_fallback = os.getenv("OCR_ALLOW_VL_FALLBACK", "false").lower() in {"1", "true", "yes"}

        if prefer_vl:
            try:
                self.pipeline = self._create_vl_pipeline()
                self._backend = "vl"
                return
            except Exception as exc:
                init_errors.append(f"PaddleOCRVL init failed: {exc}")
                if self._is_paddle_runtime_import_error(exc):
                    raise RuntimeError(
                        "OCR pipeline initialization failed: "
                        + " | ".join(init_errors)
                        + " | "
                        + self._runtime_conflict_hint()
                    )

        try:
            self.pipeline = self._create_classic_pipeline(use_angle_cls=use_angle_cls, lang=lang)
            self._backend = "classic"
            return
        except Exception as exc:
            init_errors.append(f"PaddleOCR init failed: {exc}")
            if self._is_paddle_runtime_import_error(exc):
                raise RuntimeError(
                    "OCR pipeline initialization failed: "
                    + " | ".join(init_errors)
                    + " | "
                    + self._runtime_conflict_hint()
                )

        if allow_vl_fallback and not prefer_vl:
            try:
                self.pipeline = self._create_vl_pipeline()
                self._backend = "vl"
                return
            except Exception as exc:
                init_errors.append(f"PaddleOCRVL init failed: {exc}")
                if self._is_paddle_runtime_import_error(exc):
                    raise RuntimeError(
                        "OCR pipeline initialization failed: "
                        + " | ".join(init_errors)
                        + " | "
                        + self._runtime_conflict_hint()
                    )

        raise RuntimeError("OCR pipeline initialization failed: " + " | ".join(init_errors))

    def _create_vl_pipeline(self):
        from paddleocr import PaddleOCRVL

        return PaddleOCRVL()

    def _create_classic_pipeline(self, use_angle_cls: bool, lang: str, enable_mkldnn: Optional[bool] = None):
        if enable_mkldnn is None:
            enable_mkldnn = self._classic_enable_mkldnn

        init_signature = inspect.signature(PaddleOCR.__init__)
        params = init_signature.parameters
        kwargs: Dict[str, Any] = {"lang": lang}

        if "use_doc_orientation_classify" in params:
            kwargs["use_doc_orientation_classify"] = use_angle_cls
        elif "use_angle_cls" in params:
            kwargs["use_angle_cls"] = use_angle_cls

        if "enable_mkldnn" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            kwargs["enable_mkldnn"] = bool(enable_mkldnn)
        if "cpu_threads" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            kwargs["cpu_threads"] = self._classic_cpu_threads

        try:
            return PaddleOCR(**kwargs)
        except TypeError:
            # 兼容更老版本构造参数，不支持新参数时回退。
            kwargs.pop("cpu_threads", None)
            kwargs.pop("enable_mkldnn", None)
            return PaddleOCR(**kwargs)
    
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
        tasks = [loop.run_in_executor(self.executor, self._process_single_frame, frame_path) 
                 for frame_path in keyframe_paths if os.path.exists(frame_path)]
        
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
        if self._backend == "classic":
            return self._process_single_frame_with_classic_ocr(frame_path)
        return self._process_single_frame_with_vl_ocr(frame_path)

    def _process_single_frame_with_classic_ocr(self, frame_path: str) -> Dict[str, Any]:
        """使用 PaddleOCR 经典接口处理单帧。"""
        result = self._invoke_classic_ocr(frame_path)
        texts_with_positions = self._extract_texts_from_result(result)

        return {
            "frame_path": frame_path,
            "texts": texts_with_positions,
            "total_text_count": len(texts_with_positions),
            "average_confidence": sum([t['confidence'] for t in texts_with_positions]) /
            len(texts_with_positions) if texts_with_positions else 0,
        }

    def _invoke_classic_ocr(self, frame_path: str):
        """调用 PaddleOCR，兼容旧/新版本参数差异。"""
        try:
            return self._invoke_classic_ocr_once(frame_path)
        except Exception as exc:
            if not self._is_mkldnn_runtime_error(exc):
                raise
            self._fallback_to_non_mkldnn_backend()
            return self._invoke_classic_ocr_once(frame_path)

    def _invoke_classic_ocr_once(self, frame_path: str):
        try:
            return self.pipeline.ocr(frame_path, cls=self._use_angle_cls)
        except TypeError as exc:
            # PaddleOCR 新版 predict() 不支持 cls，ocr 透传时会触发该错误。
            if "unexpected keyword argument 'cls'" not in str(exc):
                raise

            try:
                return self.pipeline.ocr(frame_path)
            except Exception:
                pass

            try:
                return self.pipeline.predict(
                    frame_path,
                    use_doc_orientation_classify=self._use_angle_cls,
                )
            except TypeError:
                return self.pipeline.predict(frame_path)

    def _is_mkldnn_runtime_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        markers = [
            "onednn",
            "mkldnn",
            "onednn_instruction.cc",
            "convertpirattribute2runtimeattribute",
        ]
        return any(marker in text for marker in markers)

    def _is_paddle_runtime_import_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        markers = [
            "can not import paddle core",
            "libpaddle.pyd",
            "already registered",
            "programdesctracer",
            "_gpudeviceproperties",
        ]
        return any(marker in text for marker in markers)

    def _runtime_conflict_hint(self) -> str:
        return (
            "Detected Paddle/Torch runtime conflict on Windows. "
            "Option A: replace paddlepaddle-gpu with paddlepaddle (CPU). "
            "Option B: run OCR in an isolated process/environment away from Torch models."
        )

    def _fallback_to_non_mkldnn_backend(self) -> None:
        if self._backend != "classic" or self._mkldnn_fallback_applied:
            return

        with self._pipeline_lock:
            if self._backend != "classic" or self._mkldnn_fallback_applied:
                return

            self.pipeline = self._create_classic_pipeline(
                use_angle_cls=self._use_angle_cls,
                lang=self._lang,
                enable_mkldnn=False,
            )
            self._classic_enable_mkldnn = False
            self._mkldnn_fallback_applied = True
            print("OCR backend fallback: reinitialized PaddleOCR with enable_mkldnn=False")

    def _extract_texts_from_result(self, result: Any) -> List[Dict[str, Any]]:
        """统一解析 PaddleOCR 不同版本返回结构。"""
        if not result:
            return []

        rows: List[Dict[str, Any]] = []

        if isinstance(result, list):
            # 旧版常见结构：[[[bbox, (text, score)], ...]]
            if result and isinstance(result[0], list):
                for item in result[0]:
                    parsed = self._parse_legacy_item(item)
                    if parsed is not None:
                        rows.append(parsed)
                if rows:
                    return rows

            for entry in result:
                rows.extend(self._extract_texts_from_entry(entry))
            return rows

        return self._extract_texts_from_entry(result)

    def _extract_texts_from_entry(self, entry: Any) -> List[Dict[str, Any]]:
        if entry is None:
            return []

        if isinstance(entry, (list, tuple)):
            parsed = self._parse_legacy_item(entry)
            return [parsed] if parsed is not None else []

        if hasattr(entry, "res"):
            return self._extract_texts_from_entry(getattr(entry, "res"))

        if hasattr(entry, "to_dict"):
            try:
                return self._extract_texts_from_entry(entry.to_dict())
            except Exception:
                pass

        if isinstance(entry, dict):
            texts = entry.get("rec_texts") or entry.get("texts") or []
            scores = entry.get("rec_scores") or entry.get("scores") or []
            bboxes = entry.get("dt_polys") or entry.get("polys") or entry.get("boxes") or []

            if isinstance(texts, str):
                texts = [texts]

            rows: List[Dict[str, Any]] = []
            for idx, text in enumerate(texts):
                if text is None:
                    continue

                confidence = 1.0
                if isinstance(scores, (list, tuple)) and idx < len(scores):
                    try:
                        confidence = float(scores[idx])
                    except Exception:
                        confidence = 1.0

                bbox = bboxes[idx] if isinstance(bboxes, (list, tuple)) and idx < len(bboxes) else None
                rows.append(
                    {
                        "text": str(text),
                        "confidence": confidence,
                        "bbox": bbox,
                    }
                )

            if rows:
                return rows

            if "text" in entry:
                confidence = entry.get("confidence", entry.get("score", 1.0))
                try:
                    confidence = float(confidence)
                except Exception:
                    confidence = 1.0

                return [
                    {
                        "text": str(entry.get("text", "")),
                        "confidence": confidence,
                        "bbox": entry.get("bbox"),
                    }
                ]

        if hasattr(entry, "text"):
            confidence = getattr(entry, "confidence", getattr(entry, "score", 1.0))
            try:
                confidence = float(confidence)
            except Exception:
                confidence = 1.0

            return [
                {
                    "text": str(getattr(entry, "text", "")),
                    "confidence": confidence,
                    "bbox": getattr(entry, "bbox", None),
                }
            ]

        return []

    def _parse_legacy_item(self, item: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            return None

        bbox = item[0]
        rec = item[1]

        if isinstance(rec, (list, tuple)) and len(rec) >= 2:
            text = str(rec[0])
            try:
                confidence = float(rec[1])
            except Exception:
                confidence = 1.0
        else:
            text = str(rec)
            confidence = 1.0

        return {
            "text": text,
            "confidence": confidence,
            "bbox": bbox,
        }

    def _process_single_frame_with_vl_ocr(self, frame_path: str) -> Dict[str, Any]:
        """使用 PaddleOCRVL 接口处理单帧。"""
        result = self.pipeline.predict(frame_path)

        texts_with_positions = []
        if result:
            for item in result:
                text = item.text if hasattr(item, 'text') else str(item)
                bbox = item.bbox if hasattr(item, 'bbox') else None
                confidence = getattr(item, 'score', 1.0)

                texts_with_positions.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox,
                })

        return {
            "frame_path": frame_path,
            "texts": texts_with_positions,
            "total_text_count": len(texts_with_positions),
            "average_confidence": sum([t['confidence'] for t in texts_with_positions]) / 
                                 len(texts_with_positions) if texts_with_positions else 0
        }
    
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