import os
import subprocess
import numpy as np
import torch
import torch.nn as nn
import torchaudio.transforms as T
import torchvision.models as models


# ==========================================
# 1. 核心模型定义 (必须与训练时完全一致)
# ==========================================
class AudioDeepfakeDetector(nn.Module):
    def __init__(self, num_classes=2):
        super(AudioDeepfakeDetector, self).__init__()
        self.backbone = models.mobilenet_v3_small(weights=None)

        original_first_layer = self.backbone.features[0][0]
        self.backbone.features[0][0] = nn.Conv2d(
            1, original_first_layer.out_channels,
            kernel_size=original_first_layer.kernel_size,
            stride=original_first_layer.stride,
            padding=original_first_layer.padding,
            bias=False
        )
        self.backbone.classifier[3] = nn.Linear(self.backbone.classifier[3].in_features, num_classes)
        self.softmax = nn.Softmax(dim=1)

    def forward(self, x):
        logits = self.backbone(x)
        return self.softmax(logits)


# ==========================================
# 2. 全格式音频极速清洗器 (纯内存流)
# ==========================================
def convert_bytes_to_ndarray(audio_bytes: bytes) -> np.ndarray:
    """内存级格式清洗：读取原始字节流，通过管道直接输出为 16kHz ndarray"""
    cmd = [
        "ffmpeg", "-y", "-i", "pipe:0",
        "-ac", "1", "-ar", "16000",
        "-f", "s16le", "-loglevel", "error", "pipe:1"
    ]

    # 启动子进程，直接在内存中进行流转码
    process = subprocess.run(cmd, input=audio_bytes, capture_output=True)
    if process.returncode != 0:
        raise RuntimeError("FFmpeg 内存解码失败，请检查文件格式。")

    # 直接读取 s16le (16位PCM) 裸数据并归一化
    audio_data = np.frombuffer(process.stdout, dtype=np.int16)
    return audio_data.astype(np.float32) / 32768.0


# ==========================================
# 3. 推理主控台
# ==========================================
class AudioFakeAnalyzer:
    def __init__(self, weight_path="./weights/latest_best_audio_model.pth", target_sample_rate=16000, max_duration=4.0):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"初始化声纹鉴伪引擎... [算力后端: {self.device}]")

        # 加载模型与权重
        self.model = AudioDeepfakeDetector(num_classes=2)
        if not os.path.exists(weight_path):
            raise FileNotFoundError(f"找不到权重文件: {weight_path}")

        state_dict = torch.load(weight_path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(state_dict)
        self.model.to(self.device)
        self.model.eval()  # 开启评估模式

        # 特征提取器初始化
        self.target_sample_rate = target_sample_rate
        self.max_length = int(target_sample_rate * max_duration)
        self.mel_transform = T.MelSpectrogram(
            sample_rate=target_sample_rate, n_fft=1024, hop_length=512, n_mels=64
        ).to(self.device)
        self.amplitude_to_db = T.AmplitudeToDB().to(self.device)

    def predict(self, audio_array: np.ndarray) -> float:
        """
        核心推理流水线：直接接收 ndarray -> 截断 -> 提取特征 -> 输出概率
        """
        # 1. 强行截断，只取前 5 秒的数据，极大加速推理并剔除冗余计算
        max_samples = 5 * self.target_sample_rate
        if len(audio_array) > max_samples:
            audio_array = audio_array[:max_samples]

        # 2. 转换为 Tensor 并增加通道维度 (1, time_steps)
        waveform = torch.from_numpy(audio_array).unsqueeze(0)

        # 3. 长度对齐 (保证送入模型的矩阵尺寸严格一致)
        if waveform.shape[1] > self.max_length:
            waveform = waveform[:, :self.max_length]
        else:
            padding = self.max_length - waveform.shape[1]
            waveform = torch.nn.functional.pad(waveform, (0, padding))

        waveform = waveform.to(self.device)

        # 4. 提取梅尔声谱图特征并送入模型
        with torch.no_grad():
            mel_spec = self.mel_transform(waveform)
            mel_spec_db = self.amplitude_to_db(mel_spec)

            # 增加 Batch 和 Channel 维度 -> (1, 1, 64, time_steps)
            inputs_gpu = mel_spec_db.unsqueeze(0)

            probs = self.model(inputs_gpu)
            fake_probability = probs[0][1].item()  # 索引 1 为 AI 合成概率

        return fake_probability


# ==========================================
# 独立模块测试入口
# ==========================================
if __name__ == "__main__":
    analyzer = AudioFakeAnalyzer()

    # 模拟从前端传来的二进制文件流进行独立测试
    test_audio_path = "test_sample.wav"

    if os.path.exists(test_audio_path):
        with open(test_audio_path, "rb") as f:
            audio_bytes = f.read()

        try:
            print("正在进行纯内存流转换...")
            audio_ndarray = convert_bytes_to_ndarray(audio_bytes)

            print("正在进行推理...")
            prob = analyzer.predict(audio_ndarray)

            print(f"分析完毕！")
            print(f"AI 合成概率: {prob * 100:.2f}%")
        except Exception as e:
            print(f"分析失败: {e}")
    else:
        print(f"找不到测试文件 {test_audio_path}，跳过独立测试。")