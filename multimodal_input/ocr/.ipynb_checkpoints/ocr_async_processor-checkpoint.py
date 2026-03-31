import json
import os
from typing import List, Dict, Any
from pathlib import Path
from paddleocr import PaddleOCRVL  # 修改为使用PaddleOCRVL
import cv2
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor


class AsyncKeyframeOCRProcessor:
    """
    异步处理关键帧OCR的类，使用PaddleOCR识别关键帧中的文本
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
        
        # 使用PaddleOCRVL替代原来的PaddleOCR
        self.pipeline = PaddleOCRVL()  # 直接初始化PaddleOCRVL
        
        # 创建线程池执行器
        self.executor = ThreadPoolExecutor(max_workers=4)
    
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
        # 使用PaddleOCRVL预测
        result = self.pipeline.predict(frame_path)
        
        # 提取文字和位置信息
        texts_with_positions = []
        if result:  # 确保结果存在且不为空
            for item in result:
                # 从PaddleOCRVL的结果中提取文本信息
                # 根据PaddleOCRVL的输出格式调整
                text = item.text if hasattr(item, 'text') else str(item)
                bbox = item.bbox if hasattr(item, 'bbox') else None
                confidence = getattr(item, 'score', 1.0)  # 如果没有置信度，默认为1.0
                
                texts_with_positions.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox
                })
        
        # 返回当前帧的OCR结果
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