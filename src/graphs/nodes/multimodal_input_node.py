import os
import base64
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import ASRClient, LLMClient
from langchain_core.messages import HumanMessage, SystemMessage
from graphs.state import MultimodalInputNodeInput, MultimodalInputNodeOutput

def multimodal_input_node(state: MultimodalInputNodeInput, config: RunnableConfig, runtime: Runtime[Context]) -> MultimodalInputNodeOutput:
    """
    title: 多模态输入处理
    desc: 处理用户输入的文本、语音和图片，提取关键信息
    integrations: 音频识别, 大语言模型
    """
    ctx = runtime.context
    
    processed_text = state.input_text
    image_analysis = ""
    
    # 处理语音文件：转文字
    if state.input_audio is not None:
        try:
            asr_client = ASRClient(ctx=ctx)
            
            # 判断是否为URL还是本地文件
            audio_source = state.input_audio.url
            
            # 如果是本地文件，转换为base64
            if not audio_source.startswith("http://") and not audio_source.startswith("https://"):
                with open(audio_source, "rb") as f:
                    audio_base64 = base64.b64encode(f.read()).decode("utf-8")
                recognized_text, _ = asr_client.recognize(uid="fraud_detection", base64_data=audio_base64)
            else:
                recognized_text, _ = asr_client.recognize(uid="fraud_detection", url=audio_source)
            
            if processed_text:
                processed_text += "\n\n[语音内容]\n" + recognized_text
            else:
                processed_text = recognized_text
        except Exception as e:
            # 语音识别失败，记录错误但继续处理
            if processed_text:
                processed_text += f"\n\n[语音识别失败: {str(e)}]"
            else:
                processed_text = f"[语音识别失败: {str(e)}]"
    
    # 处理图片文件：使用多模态模型分析
    if state.input_image is not None:
        try:
            llm_client = LLMClient(ctx=ctx)
            
            messages = [
                SystemMessage(content="你是一个专业的图片分析专家，擅长识别图片中的诈骗线索和可疑元素。"),
                HumanMessage(content=[
                    {"type": "text", "text": "请分析这张图片，识别其中的关键信息（如二维码、转账界面、验证码、可疑链接等），并描述图片内容和可能的诈骗风险。"},
                    {"type": "image_url", "image_url": {"url": state.input_image.url}}
                ])
            ]
            
            response = llm_client.invoke(
                messages=messages,
                model="doubao-seed-1-6-vision-250815",
                temperature=0.3
            )
            
            # 安全地提取响应内容
            if isinstance(response.content, str):
                image_analysis = response.content
            elif isinstance(response.content, list):
                if response.content and isinstance(response.content[0], str):
                    image_analysis = " ".join(response.content)
                else:
                    text_parts = [item.get("text", "") for item in response.content if isinstance(item, dict) and item.get("type") == "text"]
                    image_analysis = " ".join(text_parts)
            else:
                image_analysis = str(response.content)
            
            # 将图片分析结果追加到文本中
            if processed_text:
                processed_text += f"\n\n[图片分析]\n{image_analysis}"
            else:
                processed_text = f"[图片分析]\n{image_analysis}"
        except Exception as e:
            # 图片分析失败，记录错误但继续处理
            error_msg = f"[图片分析失败: {str(e)}]"
            image_analysis = error_msg
            if processed_text:
                processed_text += f"\n\n{error_msg}"
            else:
                processed_text = error_msg
    
    return MultimodalInputNodeOutput(
        processed_text=processed_text,
        image_analysis=image_analysis
    )
