"""
多模态输入服务配置文件
用于管理各个模块的配置参数，便于LangGraph集成
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import os


@dataclass
class ServiceConfig:
    """服务配置基类"""
    name: str
    host: str = "0.0.0.0"
    port: int = 8000
    endpoint: str = "/"
    enabled: bool = True
    model_path: Optional[str] = None


@dataclass
class AudioServiceConfig(ServiceConfig):
    """音频服务配置"""
    name: str = "audio_service"
    port: int = 8000
    endpoint: str = "/api/v1/analyze_audio_for_mllm"
    model_path: str = "./audio_module/weights/latest_best_audio_model.pth"
    vad_model: str = 'damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch'
    device: str = "cuda"


@dataclass
class VideoServiceConfig(ServiceConfig):
    """视频服务配置"""
    name: str = "video_service"
    port: int = 8001
    endpoint: str = "/api/v1/analyze_video_for_mllm"
    model_path: str = "./video_module/weights/final_model.pth"
    snap_timestamp_sec: float = 1.0
    keyframe_output_root: str = "./video_module/keyframes"


@dataclass
class OCRServiceConfig(ServiceConfig):
    """OCR服务配置"""
    name: str = "ocr_service"
    port: int = 8002
    endpoint: str = "/api/v1/ocr_analyze_keyframes"
    use_angle_cls: bool = True
    lang: str = "ch"
    max_side_len: int = 960


@dataclass
class UnifiedServiceConfig(ServiceConfig):
    """统一多模态服务配置"""
    name: str = "unified_service"
    port: int = 8000
    endpoint: str = "/api/v1/analyze_multimodal"
    ocr_model_path: str = "./ocr/weights/"
    video_model_path: str = "./video_module/weights/final_model.pth"
    audio_model_path: str = "./audio_module/weights/latest_best_audio_model.pth"


class MultimodalConfig:
    """多模态服务总配置"""
    
    def __init__(self):
        self.audio = AudioServiceConfig()
        self.video = VideoServiceConfig()
        self.ocr = OCRServiceConfig()
        self.unified = UnifiedServiceConfig()
        
        # 从环境变量覆盖配置
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 音频服务配置
        if os.getenv("AUDIO_SERVICE_PORT"):
            self.audio.port = int(os.getenv("AUDIO_SERVICE_PORT"))
        
        if os.getenv("AUDIO_MODEL_PATH"):
            self.audio.model_path = os.getenv("AUDIO_MODEL_PATH")
        
        # 视频服务配置
        if os.getenv("VIDEO_SERVICE_PORT"):
            self.video.port = int(os.getenv("VIDEO_SERVICE_PORT"))
        
        if os.getenv("VIDEO_MODEL_PATH"):
            self.video.model_path = os.getenv("VIDEO_MODEL_PATH")
        
        # OCR服务配置
        if os.getenv("OCR_SERVICE_PORT"):
            self.ocr.port = int(os.getenv("OCR_SERVICE_PORT"))
        
        if os.getenv("OCR_USE_ANGLE_CLS"):
            self.ocr.use_angle_cls = os.getenv("OCR_USE_ANGLE_CLS").lower() == "true"
        
        # 统一服务配置
        if os.getenv("UNIFIED_SERVICE_PORT"):
            self.unified.port = int(os.getenv("UNIFIED_SERVICE_PORT"))
    
    def get_service_config(self, service_type: str) -> ServiceConfig:
        """获取特定服务的配置"""
        mapping = {
            'audio': self.audio,
            'video': self.video,
            'ocr': self.ocr,
            'unified': self.unified
        }
        
        if service_type not in mapping:
            raise ValueError(f"Unknown service type: {service_type}")
        
        return mapping[service_type]
    
    def validate_configs(self) -> Dict[str, bool]:
        """验证配置的有效性"""
        results = {}
        
        # 检查模型文件是否存在
        for service_type in ['audio', 'video']:
            service_config = self.get_service_config(service_type)
            if service_config.model_path and not os.path.exists(service_config.model_path):
                results[service_type] = False
            else:
                results[service_type] = True
        
        return results
    
    def get_langgraph_node_config(self) -> Dict[str, Any]:
        """获取适用于LangGraph节点的配置"""
        return {
            "audio": {
                "url": f"http://{self.audio.host}:{self.audio.port}{self.audio.endpoint}",
                "enabled": self.audio.enabled,
                "model_path": self.audio.model_path
            },
            "video": {
                "url": f"http://{self.video.host}:{self.video.port}{self.video.endpoint}",
                "enabled": self.video.enabled,
                "model_path": self.video.model_path
            },
            "ocr": {
                "url": f"http://{self.ocr.host}:{self.ocr.port}{self.ocr.endpoint}",
                "enabled": self.ocr.enabled
            },
            "unified": {
                "url": f"http://{self.unified.host}:{self.unified.port}{self.unified.endpoint}",
                "enabled": self.unified.enabled
            }
        }


# 全局配置实例
multimodal_config = MultimodalConfig()


def get_config() -> MultimodalConfig:
    """获取全局配置实例"""
    return multimodal_config