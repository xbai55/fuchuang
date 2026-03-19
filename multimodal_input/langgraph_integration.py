"""
多模态输入服务与LangGraph集成模块
提供将音频、视频、OCR服务集成到LangGraph工作流的功能
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Union, List, Optional
from pathlib import Path
from enum import Enum

from .config import get_config, ServiceConfig
from multimodal_input.video_module.keyframe_extractor import KeyframeResult


class MediaType(Enum):
    """媒体类型枚举"""
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    TEXT = "text"


class MultimodalNode:
    """多模态处理节点基类"""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def process(self, input_data: Union[str, bytes, List[str]], **kwargs) -> Dict[str, Any]:
        """处理输入数据的抽象方法"""
        raise NotImplementedError("Subclasses must implement process method")


class AudioAnalysisNode(MultimodalNode):
    """音频分析节点"""
    
    def __init__(self):
        config = get_config().audio
        super().__init__(config)
    
    async def process(self, audio_file_path: str, **kwargs) -> Dict[str, Any]:
        """处理音频文件"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # 读取音频文件
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
            
            # 发送请求到音频服务
            url = f"http://{self.config.host}:{self.config.port}{self.config.endpoint}"
            
            data = aiohttp.FormData()
            data.add_field('file', audio_data, filename=Path(audio_file_path).name)
            
            async with self.session.post(url, data=data) as response:
                result = await response.json()
                
                if response.status != 200:
                    self.logger.error(f"Audio analysis failed: {result}")
                    return {"status": "error", "message": result}
                
                return result
        except Exception as e:
            self.logger.error(f"Error in audio analysis: {str(e)}")
            return {"status": "error", "message": str(e)}


class VideoAnalysisNode(MultimodalNode):
    """视频分析节点"""
    
    def __init__(self):
        config = get_config().video
        super().__init__(config)
    
    async def process(self, video_file_path: str, **kwargs) -> Dict[str, Any]:
        """处理视频文件"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # 读取视频文件
            with open(video_file_path, 'rb') as f:
                video_data = f.read()
            
            # 发送请求到视频服务
            url = f"http://{self.config.host}:{self.config.port}{self.config.endpoint}"
            
            data = aiohttp.FormData()
            data.add_field('file', video_data, filename=Path(video_file_path).name)
            
            async with self.session.post(url, data=data) as response:
                result = await response.json()
                
                if response.status != 200:
                    self.logger.error(f"Video analysis failed: {result}")
                    return {"status": "error", "message": result}
                
                return result
        except Exception as e:
            self.logger.error(f"Error in video analysis: {str(e)}")
            return {"status": "error", "message": str(e)}


class OCRAnalysisNode(MultimodalNode):
    """OCR分析节点"""
    
    def __init__(self):
        config = get_config().ocr
        super().__init__(config)
    
    async def process(self, image_paths: List[str], **kwargs) -> Dict[str, Any]:
        """处理图像文件列表"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # 发送请求到OCR服务
            url = f"http://{self.config.host}:{self.config.port}{self.config.endpoint}"
            
            data = aiohttp.FormData()
            for path in image_paths:
                with open(path, 'rb') as f:
                    data.add_field('frame_files', f.read(), filename=Path(path).name)
            
            async with self.session.post(url, data=data) as response:
                result = await response.json()
                
                if response.status != 200:
                    self.logger.error(f"OCR analysis failed: {result}")
                    return {"status": "error", "message": result}
                
                return result
        except Exception as e:
            self.logger.error(f"Error in OCR analysis: {str(e)}")
            return {"status": "error", "message": str(e)}


class UnifiedMultimodalNode(MultimodalNode):
    """统一多模态处理节点"""
    
    def __init__(self):
        config = get_config().unified
        super().__init__(config)
    
    async def process(self, media_type: MediaType, file_path: str, **kwargs) -> Dict[str, Any]:
        """处理多媒体文件"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # 读取文件
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # 发送请求到统一服务
            url = f"http://{self.config.host}:{self.config.port}{self.config.endpoint}"
            
            data = aiohttp.FormData()
            data.add_field('input_type', media_type.value)
            data.add_field('file', file_data, filename=Path(file_path).name)
            
            async with self.session.post(url, data=data) as response:
                result = await response.json()
                
                if response.status != 200:
                    self.logger.error(f"Unified multimodal analysis failed: {result}")
                    return {"status": "error", "message": result}
                
                return result
        except Exception as e:
            self.logger.error(f"Error in unified multimodal analysis: {str(e)}")
            return {"status": "error", "message": str(e)}


class MultimodalOrchestrator:
    """多模态处理编排器"""
    
    def __init__(self):
        self.nodes = {
            MediaType.AUDIO: AudioAnalysisNode(),
            MediaType.VIDEO: VideoAnalysisNode(),
            MediaType.IMAGE: OCRAnalysisNode()
        }
        self.unified_node = UnifiedMultimodalNode()
        self.logger = logging.getLogger(__name__)
    
    async def analyze_media(self, media_type: MediaType, file_path: str) -> Dict[str, Any]:
        """分析媒体文件"""
        async with self.unified_node:
            return await self.unified_node.process(media_type, file_path)
    
    async def analyze_video_with_ocr(self, video_path: str) -> Dict[str, Any]:
        """分析视频并进行OCR处理"""
        async with self.unified_node:
            return await self.unified_node.process(MediaType.VIDEO, video_path)
    
    async def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """分析音频"""
        async with self.unified_node:
            return await self.unified_node.process(MediaType.AUDIO, audio_path)
    
    async def analyze_images(self, image_paths: List[str]) -> Dict[str, Any]:
        """分析图像列表"""
        async with self.unified_node:
            results = []
            for image_path in image_paths:
                result = await self.unified_node.process(MediaType.IMAGE, image_path)
                results.append(result)
            return {"status": "success", "results": results}


def create_multimodal_nodes() -> Dict[str, Any]:
    """创建用于LangGraph的多模态处理节点"""
    orchestrator = MultimodalOrchestrator()
    
    async def audio_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """音频处理节点"""
        audio_path = state.get("audio_path")
        if not audio_path:
            return {"error": "No audio path provided"}
        
        result = await orchestrator.analyze_audio(audio_path)
        return {"audio_analysis_result": result}
    
    async def video_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """视频处理节点"""
        video_path = state.get("video_path")
        if not video_path:
            return {"error": "No video path provided"}
        
        result = await orchestrator.analyze_video_with_ocr(video_path)
        return {"video_analysis_result": result}
    
    async def image_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """图像处理节点"""
        image_paths = state.get("image_paths", [])
        if not image_paths:
            return {"error": "No image paths provided"}
        
        result = await orchestrator.analyze_images(image_paths)
        return {"image_analysis_result": result}
    
    return {
        "audio_processing": audio_processing_node,
        "video_processing": video_processing_node,
        "image_processing": image_processing_node
    }


# 示例用法
async def main():
    """示例用法"""
    orchestrator = MultimodalOrchestrator()
    
    # 示例：分析音频
    # result = await orchestrator.analyze_audio("./sample_audio.wav")
    # print("Audio Analysis Result:", result)
    
    # 示例：分析视频
    # result = await orchestrator.analyze_video_with_ocr("./sample_video.mp4")
    # print("Video Analysis Result:", result)
    
    # 示例：分析图像
    # result = await orchestrator.analyze_images(["./image1.jpg", "./image2.jpg"])
    # print("Image Analysis Result:", result)


if __name__ == "__main__":
    # 运行示例
    # asyncio.run(main())
    pass