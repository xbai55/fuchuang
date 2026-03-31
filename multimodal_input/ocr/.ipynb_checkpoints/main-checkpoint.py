import time
import asyncio
import uuid
import tempfile
import os
import sys
import shutil  # 新增：用于环境检查
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import json
from typing import Dict, Any

# 环境修复：在导入视频模块前强制注入 FFmpeg 路径
FFMPEG_BIN_PATH = r"/usr/bin/ffmpeg"#注意：请根据实际情况修改
if os.path.exists(FFMPEG_BIN_PATH):
    if FFMPEG_BIN_PATH not in os.environ["PATH"]:
        os.environ["PATH"] = FFMPEG_BIN_PATH + os.pathsep + os.environ["PATH"]
    print(f"✅已识别到 FFmpeg -> {shutil.which('ffmpeg')}")
else:
    print(f"❌ 警告：指定的 FFmpeg 路径不存在: {FFMPEG_BIN_PATH}")

# 添加当前目录到路径以支持模块导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 导入OCR和视频模块
from ocr_async_processor import AsyncKeyframeOCRProcessor
from video_module.video_inference import VideoFakeAnalyzer
from video_module.keyframe_extractor import KeyframeExtractor

app = FastAPI(title="反诈智能助手 - 多模态并行处理模块")

# ==========================================
# 全局模型预热
# ==========================================
ocr_processor: AsyncKeyframeOCRProcessor | None = None
video_fake_analyzer: VideoFakeAnalyzer | None = None
keyframe_extractor: KeyframeExtractor | None = None

print("正在预热OCR和视频AI模型...")
try:
    # OCR模型
    ocr_processor = AsyncKeyframeOCRProcessor(use_angle_cls=True, lang='ch')
    print("OCR流水线装载完毕。")
except Exception as e:
    print(f"[警告] OCR模型加载失败: {e}")

try:
    # 视频分析模型
    video_fake_analyzer = VideoFakeAnalyzer(
        weight_path="./video_module/weights/final_model.pth",
        snap_timestamp_sec=1.0,
    )
    keyframe_extractor = KeyframeExtractor(
        output_root="./video_module/keyframes",
        interval_sec=2.0,
        scene_threshold=0.35,
        max_frames=20,
    )
    print("视频流水线装载完毕。")
except Exception as e:
    # 这里如果报错，会打印详细原因（如路径或 FFmpeg 不可用）
    print(f"[警告] 视频模型加载失败: {e}")


def _check_models_ready():
    if ocr_processor is None:
        raise HTTPException(
            status_code=503,
            detail="OCR模型尚未就绪，请检查PaddleOCR安装后重启服务。"
        )
    # 仅检查OCR处理器，视频模型可选


def _check_video_models_ready():
    """检查视频相关模型是否就绪"""
    if video_fake_analyzer is None or keyframe_extractor is None:
        raise HTTPException(
            status_code=503,
            detail="视频AI模型尚未就绪，请检查权重文件后重启服务。"
        )


# 安全字符串清洗，防止 JSON 序列化崩溃
def safe_str(obj):
    return "".join([c if (31 < ord(c) < 128) else "?" for c in str(obj)])


# ==========================================
# 核心接口：并行处理视频OCR和视频分析
# ==========================================
@app.post("/api/v1/analyze_video_ocr_parallel")
async def analyze_video_ocr_parallel(file: UploadFile = File(...)):
    """
    并行处理视频OCR和视频分析
    """
    _check_video_models_ready()  # 检查视频相关模型
    _check_models_ready()  # 检查OCR模型

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
        # 调用视频鉴伪模型
        task_fake = loop.run_in_executor(
            None, video_fake_analyzer.predict_from_path, video_tmp_path
        )
        
        # 调用关键帧提取器
        task_keyframe = loop.run_in_executor(
            None, keyframe_extractor.extract, video_tmp_path, task_id
        )
        
        # 等待视频分析结果
        fake_prob, keyframe_result = await asyncio.gather(task_fake, task_keyframe)

        # 打印视频分析结果
        print("视频分析结果：", fake_prob, keyframe_result)
        
        # 异步执行OCR分析
        ocr_result = await ocr_processor.process_video_analysis(keyframe_result)

        # 3. 组装结果
        is_fake = fake_prob > 0.6
        
        # 合并视频分析和OCR结果
        combined_warning_prompt = (
            f"【系统前置判定】：极大概率为 AI 伪造合成视频 (置信度 {fake_prob:.2f})。\n"
            if is_fake else "【系统前置判定】：未检测到明显 AI 伪造痕迹。\n"
        )
        
        # 添加OCR文本信息
        ocr_summary = ocr_result.get('agent_prompt', '')
        
        # 组装给MLLM的提示
        mllm_payload = (
            f"以下是一段监控截获的视频分析数据。\n"
            f"{combined_warning_prompt}"
            f"{ocr_summary}"
            f"请结合关键帧图像和OCR文本内容分析是否存在 AI 换脸诈骗风险。"
        )

        cost_time = time.time() - start_time
        return JSONResponse(content={
            "status": "success",
            "task_id": task_id,
            "cost_time": f"{cost_time:.2f}s",
            "data": {
                "mllm_payload": mllm_payload,
                "is_fake_alert": is_fake,
                "fake_probability": round(fake_prob, 4),
                "keyframe_dir": safe_str(keyframe_result.frame_dir),
                "ocr_results": ocr_result
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


# ==========================================
# 传统接口：仅OCR分析
# ==========================================
@app.post("/api/v1/ocr_analyze_keyframes")
async def ocr_analyze_keyframes(frame_files: list[UploadFile] = File(...)):
    """
    接收多个关键帧文件，执行OCR分析并返回JSON格式结果给agent
    """
    _check_models_ready()  # 只需要检查OCR模型

    temp_paths = []
    try:
        # 保存上传的帧文件到临时目录
        for frame_file in frame_files:
            content = await frame_file.read()
            if not content:
                continue

            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            temp_paths.append(temp_path)
            
            with os.fdopen(temp_fd, 'wb') as tmp_file:
                tmp_file.write(content)

        # 异步调用OCR处理器
        ocr_results = await ocr_processor.process_keyframes(temp_paths)

        return JSONResponse(content={
            "status": "success",
            "data": ocr_results
        })

    except Exception as e:
        print(f"OCR分析任务失败: {str(e)}")
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "message": str(e)}
        )

    finally:
        # 清理临时文件
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass


@app.post("/api/v1/ocr_analyze_from_json")
async def ocr_analyze_from_json(request: Dict[Any, Any]):
    """
    接收包含关键帧路径的JSON，执行OCR分析并返回结果给agent
    """
    _check_models_ready()  # 只需要检查OCR模型

    try:
        keyframe_paths = request.get("keyframe_paths", [])
        
        if not keyframe_paths:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "缺少关键帧路径"}
            )

        # 检查所有路径是否存在
        invalid_paths = [path for path in keyframe_paths if not os.path.exists(path)]
        if invalid_paths:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": f"以下路径不存在: {invalid_paths}"}
            )

        # 异步调用OCR处理器
        ocr_results = await ocr_processor.process_keyframes(keyframe_paths)

        return JSONResponse(content={
            "status": "success",
            "data": ocr_results
        })

    except Exception as e:
        print(f"OCR分析任务失败: {str(e)}")
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "message": str(e)}
        )


@app.get("/health")
async def health_check():
    """健康检查端点"""
    ocr_status = ocr_processor is not None
    video_status = video_fake_analyzer is not None and keyframe_extractor is not None
    
    if ocr_status:
        if video_status:
            return {
                "status": "healthy", 
                "module": "Multimodal Parallel Processing Module",
                "services": {
                    "ocr": "available",
                    "video_analysis": "available"
                }
            }
        else:
            return {
                "status": "partial", 
                "module": "Multimodal Parallel Processing Module",
                "services": {
                    "ocr": "available",
                    "video_analysis": "unavailable"
                },
                "message": "Video analysis models are unavailable, but OCR service works fine."
            }
    else:
        return {
            "status": "unhealthy", 
            "module": "Multimodal Parallel Processing Module",
            "services": {
                "ocr": "unavailable",
                "video_analysis": "unavailable"
            }
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)