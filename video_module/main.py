import time
import uuid
import asyncio
import os
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from video_inference import VideoFakeAnalyzer
from keyframe_extractor import KeyframeExtractor

app = FastAPI(title="反诈智能助手 - 视频多模态极速引擎")

# ==========================================
# 全局模型预热
# ==========================================
video_fake_analyzer: VideoFakeAnalyzer | None = None
keyframe_extractor: KeyframeExtractor | None = None

print("正在预热视频 AI 模型...")
try:
    # 请确保该路径下确实存在模型权重文件
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. 动态拼接权重文件的绝对路径
    model_weight_path = os.path.join(current_dir, "weights", "final_model.pth")

    # 3. 传入修改后的路径
    video_fake_analyzer = VideoFakeAnalyzer(
        weight_path=model_weight_path,
        snap_timestamp_sec=1.0,
    )
    keyframe_extractor = KeyframeExtractor(
        output_root="./keyframes",
        interval_sec=2.0,
        scene_threshold=0.35,
        max_frames=20,
    )
    print("视频流水线装载完毕。")
except Exception as e:
    print(f"[警告] 模型加载失败: {e}")


def _check_models_ready():
    if video_fake_analyzer is None or keyframe_extractor is None:
        raise HTTPException(
            status_code=503,
            detail="视频 AI 模型尚未就绪，请检查权重文件后重启服务。"
        )


# 安全字符串清洗，防止 JSON 序列化崩溃
def safe_str(obj):
    return "".join([c if (31 < ord(c) < 128) else "?" for c in str(obj)])


# ==========================================
# 核心接口
# ==========================================
@app.post("/api/v1/analyze_video_for_mllm")
async def analyze_video_for_mllm(file: UploadFile = File(...)):
    _check_models_ready()

    start_time = time.time()
    task_id = str(uuid.uuid4())

    # 1. 物理隔离：先将上传的文件保存为临时文件
    # 这是解决 UnicodeDecodeError 的核心，不再把 bytes 传给 extractor
    temp_dir = tempfile.gettempdir()
    video_tmp_path = os.path.join(temp_dir, f"upload_{task_id}.mp4")

    try:
        content = await file.read()
        if not content:
            return JSONResponse(status_code=400, content={"message": "文件为空"})

        with open(video_tmp_path, "wb") as f:
            f.write(content)

        loop = asyncio.get_running_loop()

        # 2. 并发执行：全部基于文件路径调用
        # 调用鉴伪模型（使用新增的 predict_from_path 方法）
        task_fake = loop.run_in_executor(
            None, video_fake_analyzer.predict_from_path, video_tmp_path
        )
        # 调用关键帧提取器（它原本就接收路径）
        task_keyframe = loop.run_in_executor(
            None, keyframe_extractor.extract, video_tmp_path, task_id
        )

        # 3. 等待结果
        fake_prob = await task_fake
        is_fake = fake_prob > 0.6
        keyframe_result = await task_keyframe

        # 4. 组装结果
        warning_prompt = (
            f"【系统前置判定】：极大概率为 AI 伪造合成视频 (置信度 {fake_prob:.2f})。\n"
            if is_fake else "【系统前置判定】：未检测到明显 AI 伪造痕迹。\n"
        )

        frame_paths_str = "\n".join(
            f"  [{fm.frame_index:02d}] {safe_str(fm.path)} "
            f"(ts≈{fm.timestamp_sec:.1f}s, src={fm.source})"
            for fm in keyframe_result.frames
        )

        mllm_payload = (
            f"以下是一段监控截获的视频分析数据。\n"
            f"{warning_prompt}"
            f"【关键帧信息】：共提取 {len(keyframe_result.frames)} 帧。详情如下：\n"
            f"{frame_paths_str}\n"
            f"请结合关键帧图像分析是否存在 AI 换脸诈骗风险。"
        )

        cost_time = time.time() - start_time
        return JSONResponse(content={
            "status": "success",
            "task_id": task_id,
            "cost_time": f"{cost_time:.2f}s",
            "data": {
                "mllm_prompt": mllm_payload,
                "is_fake_alert": is_fake,
                "fake_probability": round(fake_prob, 4),
                "keyframe_dir": safe_str(keyframe_result.frame_dir),
            },
        })

    except Exception as e:
        # 清洗异常信息防止返回时崩掉
        clean_err = safe_str(e)
        print(f"--- 任务 {task_id} 失败 ---")
        print(f"错误类型: {type(e).__name__}, 详情: {clean_err}")
        return JSONResponse(status_code=500, content={"status": "error", "message": clean_err})

    finally:
        # 5. 清理临时视频文件
        if os.path.exists(video_tmp_path):
            try:
                os.remove(video_tmp_path)
            except:
                pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)