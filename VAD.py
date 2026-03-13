import torch
import numpy as np
from faster_whisper import WhisperModel


class AntiFraudAudioEngine:
    def __init__(self, model_size="large-v3", device="cuda"):
        # 启用 large-v3 大模型以获取极限语义精度
        # 使用 int8_float16 量化，大幅降低显存占用，防止 OOM 报错
        self.asr_model = WhisperModel(model_size, device=device, compute_type="int8_float16")

        # 加载 Silero VAD 模型用于高精度端点检测
        self.vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False
        )
        (self.get_speech_timestamps, _, _, _, _) = utils

    def process_pipeline(self, audio_array: np.ndarray):
        """核心流水线：接收纯内存 numpy 数组进行 VAD 截断和 ASR 高精度转写"""

        # 1. 转换为 Tensor 供 Silero VAD 使用
        wav_tensor = torch.from_numpy(audio_array).float()

        # 2. 执行 VAD 端点检测 (采样率固定为 16000)
        speech_timestamps = self.get_speech_timestamps(wav_tensor, self.vad_model, sampling_rate=16000)

        if not speech_timestamps:
            return "未检测到有效语音", []

        # 3. 执行大模型 ASR 转录 (注入反诈专属先验提示词)
        segments, info = self.asr_model.transcribe(
            audio_array,
            beam_size=5,
            language="zh",
            vad_filter=True,
            initial_prompt="这是一段诈骗录音，可能包含以下词汇：公安局、专案组、洗钱、安全账户、转账、银行卡、验证码、理疗仪、国家补贴。"
        )

        # 拼接全量文本
        full_text = "".join([segment.text for segment in segments])

        return full_text, speech_timestamps