import base64
from langchain_core.runnables import RunnableConfig
from graphs.state import MultimodalInputNodeInput, MultimodalInputNodeOutput


def multimodal_input_node(state: MultimodalInputNodeInput, config: RunnableConfig) -> MultimodalInputNodeOutput:
    """
    title: 多模态输入处理
    desc: 处理用户输入的文本、语音和图片，提取关键信息
    """
    processed_text = state.input_text
    image_analysis = ""

    # 语音处理（依赖 FunASR，失败时降级）
    if state.input_audio is not None:
        try:
            from audio_module.audio_inference import recognize_audio
            audio_source = state.input_audio.url
            if not audio_source.startswith("http://") and not audio_source.startswith("https://"):
                with open(audio_source, "rb") as f:
                    audio_bytes = f.read()
                recognized_text = recognize_audio(audio_bytes)
            else:
                import urllib.request
                with urllib.request.urlopen(audio_source) as r:
                    recognized_text = recognize_audio(r.read())
            processed_text = (processed_text + "\n\n[语音内容]\n" + recognized_text).strip()
        except Exception as e:
            error_msg = f"[语音识别失败: {str(e)}]"
            processed_text = (processed_text + "\n\n" + error_msg).strip() if processed_text else error_msg

    # 图片分析（使用多模态 LLM，失败时降级）
    if state.input_image is not None:
        try:
            from utils.llm_client import call_llm
            messages = [
                {"role": "system", "content": "你是专业的图片分析专家，擅长识别图片中的诈骗线索。"},
                {"role": "user", "content": [
                    {"type": "text", "text": "请分析这张图片，识别关键信息（二维码、转账界面、验证码、可疑链接等），描述内容和可能的诈骗风险。"},
                    {"type": "image_url", "image_url": {"url": state.input_image.url}}
                ]}
            ]
            image_analysis = call_llm(messages, model="qwen-vl-plus", temperature=0.3)
            processed_text = (processed_text + f"\n\n[图片分析]\n{image_analysis}").strip()
        except Exception as e:
            error_msg = f"[图片分析失败: {str(e)}]"
            image_analysis = error_msg
            processed_text = (processed_text + f"\n\n{error_msg}").strip()

    return MultimodalInputNodeOutput(
        processed_text=processed_text,
        image_analysis=image_analysis,
    )
