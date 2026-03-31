import io
import os
import subprocess
import tempfile
import uuid
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from PIL import Image


class VideoDeepfakeDetector(nn.Module):
    def __init__(self, num_classes: int = 2):
        super().__init__()
        self.backbone = models.efficientnet_b0(weights=None)
        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier[1] = nn.Linear(in_features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


def extract_single_frame_safe(video_path_or_bytes, timestamp_sec: float = 1.0) -> bytes:
    """安全的单帧提取：支持路径或字节流"""
    tmp_path = None
    # 如果传入的是字节流，先存入临时文件
    if isinstance(video_path_or_bytes, bytes):
        tmp_path = os.path.join(tempfile.gettempdir(), f"infer_{uuid.uuid4()}.mp4")
        with open(tmp_path, "wb") as f:
            f.write(video_path_or_bytes)
        target_path = tmp_path
    else:
        target_path = video_path_or_bytes

    try:
        cmd = [
            "ffmpeg", "-y", "-ss", str(timestamp_sec),
            "-i", target_path, "-vframes", "1",
            "-f", "image2", "-vcodec", "mjpeg", "-loglevel", "error", "pipe:1"
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=20)

        if proc.returncode != 0 or len(proc.stdout) == 0:
            if timestamp_sec > 0:
                return extract_single_frame_safe(target_path, timestamp_sec=0.0)
            err = proc.stderr.decode(errors='ignore').replace('\n', ' ')
            raise RuntimeError(f"FFmpeg Error: {err[:100]}")
        return proc.stdout
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass


class VideoFakeAnalyzer:
    def __init__(self, weight_path: str, input_size: int = 224, snap_timestamp_sec: float = 1.0):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.snap_timestamp_sec = snap_timestamp_sec
        self.model = VideoDeepfakeDetector(num_classes=2)

        if not os.path.exists(weight_path):
            raise FileNotFoundError(f"Missing weights: {weight_path}")

        state_dict = torch.load(weight_path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(state_dict)
        self.model.to(self.device).eval()

        self.preprocess = T.Compose([
            T.Resize((input_size, input_size)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def predict_from_path(self, video_path: str) -> float:
        """从文件路径直接推理"""
        try:
            frame_bytes = extract_single_frame_safe(video_path, self.snap_timestamp_sec)
            return self._infer_from_frame_bytes(frame_bytes)
        except Exception as e:
            print(f"[Analyzer] Path Inference Error: {e}")
            return 0.0

    def predict_from_bytes(self, video_bytes: bytes) -> float:
        """从内存字节推理（向下兼容）"""
        try:
            frame_bytes = extract_single_frame_safe(video_bytes, self.snap_timestamp_sec)
            return self._infer_from_frame_bytes(frame_bytes)
        except Exception as e:
            print(f"[Analyzer] Bytes Inference Error: {e}")
            return 0.0

    def _infer_from_frame_bytes(self, frame_bytes: bytes) -> float:
        frame_image = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
        if np.array(frame_image).std() < 2.0: return 0.0  # 黑屏检测

        input_tensor = self.preprocess(frame_image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(input_tensor)
            probs = torch.softmax(logits, dim=1)
            return float(probs[0][1].item())