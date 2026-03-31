import torch
import numpy as np
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks


class AntiFraudAudioEngine:
    def __init__(self, device="cuda"):
        # 初始化阿里 FunASR 流水线
        # 自动加载 Paraformer-large 语音识别模型
        # 同时加载 FSMN-VAD 语音端点检测模型与 CT-Transformer 标点恢复模型
        self.inference_pipeline = pipeline(
            task=Tasks.auto_speech_recognition,
            model='damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
            vad_model='damo/speech_fsmn_vad_zh-cn-16k-common-pytorch',
            punc_model='damo/punc_ct-transformer_zh-cn-common-vocab272727-pytorch',
            device=device
        )

    def process_pipeline(self, audio_array: np.ndarray):
        """核心流水线：使用阿里 FunASR 进行端到端识别"""

        # 检查音频采样率（FunASR 强制要求 16000Hz）
        # 如果 audio_array 是 float 格式，通常保持在 [-1, 1] 范围内
        try:
            # 执行推理
            # param_dict 支持设置 hotwords，用于增强反诈关键词的敏感度
            results = self.inference_pipeline(
                input=audio_array,
                batch_size_s=300,
                hotwords="公安局 专案组 洗钱 安全账户 转账 验证码 国家补贴"
            )

            if not results or len(results) == 0:
                return "未检测到有效语音", []

            # 提取转写结果
            full_text = results[0].get('text', "")

            # 提取 VAD 时间戳信息 (FunASR 的 VAD 信息通常在结果的 timestamps 字段中)
            # 格式通常为 [[start_ms, end_ms], ...]
            vad_timestamps = results[0].get('timestamps', [])

            if not full_text:
                return "语音过短或无法识别", []

            return full_text, vad_timestamps

        except Exception as e:
            print(f"ASR 推理发生错误: {str(e)}")
            return f"识别失败: {str(e)}", []


# 单元测试示例
if __name__ == "__main__":
    # 模拟一段 16kHz 的 1秒空白音频
    dummy_audio = np.zeros(16000, dtype=np.float32)
    engine = AntiFraudAudioEngine()
    text, stamps = engine.process_pipeline(dummy_audio)
    print(f"识别结果: {text}")