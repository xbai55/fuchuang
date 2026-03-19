import time
import asyncio
import os
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from audio_inference import AudioFakeAnalyzer, convert_bytes_to_ndarray
from VAD import AntiFraudAudioEngine

from pathlib import Path

# 获取当前项目根目录（假设 main.py 在 audio_module 下，向上退一级）
# 如果 main.py 就在项目根目录，用 Path(__file__).parent 即可
project_root = Path(__file__).parent.parent 
model_cache_dir = project_root / "model_hub"

# 设置 ModelScope 缓存路径环境变量
os.environ['MODELSCOPE_CACHE'] = str(model_cache_dir)

print(f"模型缓存路径已设置为: {model_cache_dir}")

app = FastAPI(title="反诈智能助手 - 多模态极速引擎")

print("正在预热 AI 模型...")
try:
    # 1. 获取当前脚本 (main.py) 所在的绝对目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 2. 拼接音频模型的绝对路径
    # 使用 os.path.join 会自动处理 Windows (\) 和 Linux (/) 的路径分隔符差异
    audio_weight_path = os.path.join(current_dir, "weights", "latest_best_audio_model.pth")
    # 3. 传入增强后的路径
    fake_analyzer = AudioFakeAnalyzer(weight_path=audio_weight_path)
    nlp_engine = AntiFraudAudioEngine(device="cuda")
    print("纯内存流水线装载完毕。")
except Exception as e:
    print(f"模型加载失败，请检查权重: {e}")


@app.post("/api/v1/analyze_audio_for_mllm")
async def analyze_audio_for_mllm(file: UploadFile = File(...)):
    start_time = time.time()

    try:
        audio_bytes = await file.read()
        loop = asyncio.get_event_loop()

        # 内存级重采样
        audio_ndarray = await loop.run_in_executor(None, convert_bytes_to_ndarray, audio_bytes)

        # 1. 并发启动：将两个任务同时丢进线程池起跑
        task_fake = loop.run_in_executor(None, fake_analyzer.predict, audio_ndarray)
        task_nlp = loop.run_in_executor(None, nlp_engine.process_pipeline, audio_ndarray)

        # 2. 优先截获鉴伪结果
        # 由于 fake_analyzer 内部有 5 秒截断逻辑，此 await 通常在 100-200ms 内完成
        fake_prob = await task_fake
        is_fake = fake_prob > 0.8

        # 触发毫秒级终端预警 (在此处也可接入针对硬件设备的串口信令或前端 WebSocket 推送)
        warning_prompt = ""
        if is_fake:
            print(f"\n[高危预警] 检测到高危 AI 合成语音！伪造概率: {fake_prob:.4f}")
            print("正在等待全量语义解析以生成 MLLM 提示词...\n")
            warning_prompt = f"【系统前置判定】：极大概率为 AI 伪造合成语音 (置信度 {fake_prob:.2f})。\n"
        else:
            warning_prompt = f"【系统前置判定】：未检测到明显 AI 伪造痕迹。\n"

        # 3. 等待大体积 ASR 模型交卷
        transcribed_text, vad_timestamps = await task_nlp

        # 4. 组装多模态大模型 (MLLM) 专属 Prompt
        mllm_payload = (
            f"以下是一段监控截获的音频分析数据。\n"
            f"{warning_prompt}"
            f"【语音识别文本】：“{transcribed_text}”\n"
            f"请结合上述前置判定与文本内容，分析该段语音是否存在针对客户的诈骗意图，"
            f"并直接给出具体的防范措施或话术建议。"
        )

        cost_time = time.time() - start_time
        print(f"音频全量分析与 MLLM Prompt 组装完成，总耗时: {cost_time:.2f} 秒")

        return JSONResponse(content={
            "status": "success",
            "cost_time": f"{cost_time:.2f}s",
            "data": {
                "mllm_prompt": mllm_payload,
                "raw_text": transcribed_text,
                "is_fake_alert": is_fake
            }
        })

    except Exception as e:
        print(f"处理音频时发生错误: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)