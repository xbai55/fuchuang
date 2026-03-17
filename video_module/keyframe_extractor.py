import os
import subprocess
import cv2
import numpy as np
from dataclasses import dataclass, field

# ==========================================
# 数据结构
# ==========================================
@dataclass
class FrameMeta:
    """单个关键帧的元数据"""
    frame_index: int          # 在当前任务中的全局序号（0-based）
    timestamp_sec: float      # 帧在视频中的时间戳（秒），-1 表示未知
    path: str                 # 落盘后的完整文件路径
    source: str = "uniform"   # 来源："uniform" | "scene" | "face"
    has_face: bool = False     # 是否包含人脸
    face_count: int = 0        # 检测到的人脸数量


@dataclass
class KeyframeResult:
    """关键帧提取任务的完整结果"""
    task_id: str
    frame_dir: str
    frames: list[FrameMeta] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.frames)

    @property
    def paths(self) -> list[str]:
        return [f.path for f in self.frames]

    @property
    def face_frames(self) -> list[FrameMeta]:
        """仅返回含人脸的帧"""
        return [f for f in self.frames if f.has_face]


# ==========================================
# 人脸检测器
# ==========================================
class FaceDetector:
    CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

    def __init__(
        self,
        scale_factor: float = 1.1,
        min_neighbors: int = 4,
        min_face_size: tuple[int, int] = (40, 40),
    ):
        self.detector = cv2.CascadeClassifier(self.CASCADE_PATH)
        if self.detector.empty():
            raise RuntimeError(f"无法加载 Haar Cascade 文件: {self.CASCADE_PATH}")
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_face_size = min_face_size

    def detect(self, image_path: str) -> int:
        img = cv2.imread(image_path)
        if img is None:
            return 0
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        scale = min(1.0, 480.0 / max(h, w))
        if scale < 1.0:
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
        faces = self.detector.detectMultiScale(
            gray, scaleFactor=self.scale_factor, minNeighbors=self.min_neighbors, minSize=self.min_face_size
        )
        return len(faces) if isinstance(faces, np.ndarray) else 0


# ==========================================
# 关键帧提取引擎 (Windows 稳定版)
# ==========================================
class KeyframeExtractor:
    def __init__(
        self,
        output_root: str = "./keyframes",
        interval_sec: float = 2.0,
        scene_threshold: float = 0.35,
        max_frames: int = 20,
        face_priority: bool = True,
        ffmpeg_timeout: int = 120,
    ):
        self.output_root = os.path.abspath(output_root)
        self.interval_sec = interval_sec
        self.scene_threshold = scene_threshold
        self.max_frames = max_frames
        self.face_priority = face_priority
        self.ffmpeg_timeout = ffmpeg_timeout
        self.face_detector = FaceDetector() if face_priority else None

    def extract(self, video_path: str, task_id: str) -> KeyframeResult:
        """
        主入口：接收视频文件路径。
        """
        video_path = os.path.abspath(video_path)
        frame_dir = os.path.abspath(os.path.join(self.output_root, task_id.replace(".", "_")))
        os.makedirs(frame_dir, exist_ok=True)

        # ── 策略 A & B：FFmpeg 提取 ───────────────────────────
        uniform_files = self._extract_uniform(video_path, frame_dir)
        scene_files   = self._extract_scene(video_path, frame_dir)

        # 合并去重并排序
        all_files = sorted(list(set(uniform_files + scene_files)))

        # ── 策略 C：人脸检测标注 ──────────────────────────────────
        annotated = self._annotate_faces(all_files, frame_dir)

        if self.face_priority:
            # 人脸帧在前
            annotated.sort(key=lambda x: (0 if x[2] else 1, x[0]))

        annotated = annotated[:self.max_frames]

        # ── 组装结果 ─────────────────────────────────────────────
        frames = []
        for idx, (fname, source, has_face, face_count) in enumerate(annotated):
            ts = self._estimate_timestamp(fname)
            frames.append(FrameMeta(
                frame_index=idx,
                timestamp_sec=ts,
                path=os.path.join(frame_dir, fname),
                source=source,
                has_face=has_face,
                face_count=face_count,
            ))

        result = KeyframeResult(task_id=task_id, frame_dir=frame_dir, frames=frames)
        face_total = sum(1 for f in frames if f.has_face)
        print(f"[KeyframeExtractor] task={task_id} | 总帧数={result.count} | 含人脸帧:{face_total}")
        return result

    def _extract_uniform(self, video_path: str, frame_dir: str) -> list[str]:
        output_pattern = os.path.join(frame_dir, "uniform_%06d.jpg")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps=1/{self.interval_sec}",
            "-strict", "-2",  # <--- 添加这一行，允许非标准 YUV 处理
            "-vsync", "vfr", "-loglevel", "error",
            output_pattern,
        ]
        self._run_ffmpeg(cmd, label="均匀采样")
        return [f for f in os.listdir(frame_dir) if f.startswith("uniform_") and f.endswith(".jpg")]

    def _extract_scene(self, video_path: str, frame_dir: str) -> list[str]:
        output_pattern = os.path.join(frame_dir, "scene_%06d.jpg")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"select='gt(scene,{self.scene_threshold})'",
            "-strict", "-2",  # <--- 添加这一行
            "-vsync", "vfr", "-loglevel", "error",
            output_pattern,
        ]
        self._run_ffmpeg(cmd, label="场景切换")
        return [f for f in os.listdir(frame_dir) if f.startswith("scene_") and f.endswith(".jpg")]

    def _annotate_faces(self, filenames: list[str], frame_dir: str) -> list[tuple[str, str, bool, int]]:
        results = []
        for fname in filenames:
            source = fname.split("_")[0]
            full_path = os.path.join(frame_dir, fname)
            if self.face_detector:
                count = self.face_detector.detect(full_path)
                has_face = count > 0
            else:
                count, has_face = 0, False
            results.append((fname, source, has_face, count))
        return results

    def _run_ffmpeg(self, cmd: list[str], label: str = "") -> None:
        """统一 FFmpeg 调用，不再接收 video_bytes"""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.ffmpeg_timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if proc.returncode != 0:
                if "Output file is empty" not in proc.stderr:
                    print(f"[KeyframeExtractor] {label} FFmpeg 警告 (code={proc.returncode}): {proc.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"[KeyframeExtractor] {label} FFmpeg 超时，已终止")
        except Exception as e:
            print(f"[KeyframeExtractor] {label} 运行出错: {e}")

    def _estimate_timestamp(self, filename: str) -> float:
        try:
            parts = filename.replace(".jpg", "").split("_")
            source, seq = parts[0], int(parts[1])
            if source == "uniform":
                return max(0.0, (seq - 1) * self.interval_sec)
        except:
            pass
        return -1.0

if __name__ == "__main__":
    import sys
    test_video = sys.argv[1] if len(sys.argv) > 1 else "test.mp4"
    if os.path.exists(test_video):
        extractor = KeyframeExtractor(output_root="./keyframes_test")
        # 测试时直接传入路径
        result = extractor.extract(test_video, task_id="test_v1")
        print(f"提取完成，路径: {result.frame_dir}")