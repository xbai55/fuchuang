import os
# 禁用 PaddleOCR 模型源检查，加速启动
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

import time
import asyncio
import uuid
import tempfile
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from enum import Enum

# 导入各模块
from ocr.ocr_async_processor import AsyncKeyframeOCRProcessor
from video_module.video_inference import VideoFakeAnalyzer
from video_module.keyframe_extractor import KeyframeExtractor
from audio_module.audio_inference import AudioFakeAnalyzer, convert_bytes_to_ndarray
from audio_module.VAD import AntiFraudAudioEngine

app = FastAPI(title="反诈智能助手 - 统一多模态处理模块")

# ==========================================
# 枚举定义输入类型
# ==========================================
class InputType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"


# ==========================================
# 全局模型预热
# ==========================================
ocr_processor: AsyncKeyframeOCRProcessor | None = None
video_fake_analyzer: VideoFakeAnalyzer | None = None
keyframe_extractor: KeyframeExtractor | None = None
audio_fake_analyzer: AudioFakeAnalyzer | None = None
nlp_engine: AntiFraudAudioEngine | None = None

print("正在预热所有AI模型...")
try:
    # OCR模型
    ocr_processor = AsyncKeyframeOCRProcessor(use_angle_cls=True, lang='ch')
    
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
    
    # 音频分析模型
    audio_fake_analyzer = AudioFakeAnalyzer(weight_path="./audio_module/weights/latest_best_audio_model.pth")
    nlp_engine = AntiFraudAudioEngine(device="cuda")
    
    print("所有流水线装载完毕。")
except Exception as e:
    print(f"[警告] 模型加载失败: {e}")


def _check_models_ready(input_type: InputType):
    if input_type == InputType.VIDEO:
        if ocr_processor is None or video_fake_analyzer is None or keyframe_extractor is None:
            raise HTTPException(
                status_code=503,
                detail="视频AI模型尚未就绪，请检查权重文件后重启服务。"
            )
    elif input_type == InputType.AUDIO:
        if audio_fake_analyzer is None or nlp_engine is None:
            raise HTTPException(
                status_code=503,
                detail="音频AI模型尚未就绪，请检查权重文件后重启服务。"
            )
    elif input_type == InputType.IMAGE:
        if ocr_processor is None:
            raise HTTPException(
                status_code=503,
                detail="OCR模型尚未就绪，请检查PaddleOCR安装后重启服务。"
            )


# 安全字符串清洗，防止 JSON 序列化崩溃
def safe_str(obj):
    return "".join([c if (31 < ord(c) < 128) else "?" for c in str(obj)])


# ==========================================
# 统一接口：根据输入类型进行处理
# ==========================================
@app.post("/api/v1/analyze_multimodal")
async def analyze_multimodal(input_type: InputType, file: UploadFile = File(...)):
    """
    统一接口：根据输入类型并行处理多模态数据
    """
    _check_models_ready(input_type)

    start_time = time.time()
    task_id = str(uuid.uuid4())

    try:
        content = await file.read()
        if not content:
            return JSONResponse(status_code=400, content={"message": "文件为空"})

        loop = asyncio.get_event_loop()
        
        if input_type == InputType.VIDEO:
            # 视频处理：并行执行视频分析和OCR
            temp_dir = tempfile.gettempdir()
            video_tmp_path = os.path.join(temp_dir, f"upload_{task_id}.mp4")

            with open(video_tmp_path, "wb") as f:
                f.write(content)

            # 并行执行视频分析任务
            task_fake = loop.run_in_executor(
                None, video_fake_analyzer.predict_from_path, video_tmp_path
            )
            task_keyframe = loop.run_in_executor(
                None, keyframe_extractor.extract, video_tmp_path, task_id
            )
            
            # 等待视频分析结果
            fake_prob, keyframe_result = await asyncio.gather(task_fake, task_keyframe)
            
            # 异步执行OCR分析
            ocr_result = await ocr_processor.process_video_analysis(keyframe_result)

            # 组装结果
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

            result = JSONResponse(content={
                "status": "success",
                "task_id": task_id,
                "cost_time": f"{time.time() - start_time:.2f}s",
                "data": {
                    "mllm_prompt": mllm_payload,
                    "is_fake_alert": is_fake,
                    "fake_probability": round(fake_prob, 4),
                    "keyframe_dir": safe_str(keyframe_result.frame_dir),
                    "ocr_results": ocr_result
                },
            })
            
        elif input_type == InputType.AUDIO:
            # 音频处理：并行执行音频分析
            # 内存级重采样
            audio_ndarray = await loop.run_in_executor(None, convert_bytes_to_ndarray, content)

            # 并行启动音频分析任务
            task_fake = loop.run_in_executor(None, audio_fake_analyzer.predict, audio_ndarray)
            task_nlp = loop.run_in_executor(None, nlp_engine.process_pipeline, audio_ndarray)

            # 等待音频分析结果
            fake_prob, (transcribed_text, vad_timestamps) = await asyncio.gather(task_fake, task_nlp)
            
            is_fake = fake_prob > 0.8

            # 触发毫秒级终端预警
            warning_prompt = ""
            if is_fake:
                print(f"\n[高危预警] 检测到高危 AI 合成语音！伪造概率: {fake_prob:.4f}")
                print("正在等待全量语义解析以生成 MLLM 提示词...\n")
                warning_prompt = f"【系统前置判定】：极大概率为 AI 伪造合成语音 (置信度 {fake_prob:.2f})。\n"
            else:
                warning_prompt = f"【系统前置判定】：未检测到明显 AI 伪造痕迹。\n"

            # 组装给MLLM的提示
            mllm_payload = (
                f"以下是一段监控截获的音频分析数据。\n"
                f"{warning_prompt}"
                f"【语音识别文本】：“{transcribed_text}”\n"
                f"请结合上述前置判定与文本内容，分析该段语音是否存在针对客户的诈骗意图，"
                f"并直接给出具体的防范措施或话术建议。"
            )

            result = JSONResponse(content={
                "status": "success",
                "task_id": task_id,
                "cost_time": f"{time.time() - start_time:.2f}s",
                "data": {
                    "mllm_prompt": mllm_payload,
                    "raw_text": transcribed_text,
                    "is_fake_alert": is_fake,
                    "fake_probability": round(fake_prob, 4)
                }
            })
            
        elif input_type == InputType.IMAGE:
            # 图像处理：执行OCR分析
            temp_dir = tempfile.gettempdir()
            image_tmp_path = os.path.join(temp_dir, f"upload_{task_id}.jpg")

            with open(image_tmp_path, "wb") as f:
                f.write(content)

            # 异步执行OCR分析
            ocr_result = await ocr_processor.process_keyframes([image_tmp_path])

            # 组装给MLLM的提示
            mllm_payload = (
                f"以下是一张图像的OCR分析结果。\n"
                f"【OCR文本内容】：{ocr_result.get('summary_texts', [])}\n"
                f"请分析图像中是否存在诈骗相关的信息。"
            )

            result = JSONResponse(content={
                "status": "success",
                "task_id": task_id,
                "cost_time": f"{time.time() - start_time:.2f}s",
                "data": {
                    "mllm_prompt": mllm_payload,
                    "ocr_results": ocr_result
                }
            })
        else:
            raise ValueError(f"Unsupported input type: {input_type}")

        return result

    except Exception as e:
        # 清洗异常信息防止返回时崩掉
        clean_err = safe_str(e)
        print(f"--- 任务 {task_id} 失败 ---")
        print(f"错误类型: {type(e).__name__}, 详情: {clean_err}")
        return JSONResponse(status_code=500, content={"status": "error", "message": clean_err})


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "module": "Unified Multimodal Processing Module"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)