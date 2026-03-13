import os
import json
from typing import Union, List, Dict
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage
from jinja2 import Template
from graphs.state import InterventionNodeInput, InterventionNodeOutput

def intervention_node(state: InterventionNodeInput, config: RunnableConfig, runtime: Runtime[Context]) -> InterventionNodeOutput:
    """
    title: 干预措施生成
    desc: 根据风险等级和用户角色生成个性化的预警文案和干预策略
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up_template = _cfg.get("up", "")
    
    # 使用jinja2模板渲染用户提示词
    up_tpl = Template(up_template)
    user_prompt_content = up_tpl.render(
        risk_score=state.risk_score,
        risk_level=state.risk_level,
        scam_type=state.scam_type,
        risk_clues=state.risk_clues,
        similar_cases=state.similar_cases,
        legal_basis=state.legal_basis,
        user_role=state.user_role,
        guardian_name=state.guardian_name
    )
    
    # 初始化LLM客户端
    llm_client = LLMClient(ctx=ctx)
    
    # 构建消息
    messages = [
        {"type": "system", "content": sp},
        {"type": "user", "content": user_prompt_content}
    ]
    
    # 调用大模型
    response = llm_client.invoke(
        messages=messages,
        model=llm_config.get("model", "doubao-seed-1-8-251228"),
        temperature=llm_config.get("temperature", 0.5),
        max_completion_tokens=llm_config.get("max_completion_tokens", 3000),
        top_p=llm_config.get("top_p", 0.95)
    )
    
    # 安全地提取响应内容
    def get_text_content(content: Union[str, List[Union[str, Dict]]]) -> str:
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            if content and isinstance(content[0], str):
                return " ".join(content)
            else:
                text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
                return " ".join(text_parts)
        return str(content)
    
    response_text = get_text_content(response.content)
    
    # 解析JSON响应
    try:
        # 尝试提取JSON部分（可能包含```json标记）
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")
        
        warning_message = result.get("warning_message", "请提高警惕，注意个人信息和资金安全。")
        guardian_alert = bool(result.get("guardian_alert", False))
        alert_reason = result.get("alert_reason", "")
    except Exception as e:
        # JSON解析失败，使用默认值
        warning_message = f"警告文案生成失败，请立即停止与对方的联系并联系家人或警方。错误: {str(e)}"
        guardian_alert = state.risk_score > 75  # 高风险默认通知
        alert_reason = "系统自动触发" if guardian_alert else ""
    
    return InterventionNodeOutput(
        warning_message=warning_message,
        guardian_alert=guardian_alert,
        alert_reason=alert_reason
    )
