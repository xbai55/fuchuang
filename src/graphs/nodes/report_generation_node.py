import os
import json
from typing import Union, List, Dict
from datetime import datetime
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage
from jinja2 import Template
from graphs.state import ReportGenerationNodeInput, ReportGenerationNodeOutput

def report_generation_node(state: ReportGenerationNodeInput, config: RunnableConfig, runtime: Runtime[Context]) -> ReportGenerationNodeOutput:
    """
    title: 报告生成
    desc: 汇总所有分析结果，生成完整的安全监测报告
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
        warning_message=state.warning_message,
        guardian_alert=state.guardian_alert,
        alert_reason=state.alert_reason
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
        temperature=llm_config.get("temperature", 0.4),
        max_completion_tokens=llm_config.get("max_completion_tokens", 5000),
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
    
    final_report = get_text_content(response.content)
    
    # 添加时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "---" in final_report:
        final_report = final_report.replace("---", f"---\n\n报告生成时间：{timestamp}")
    else:
        final_report += f"\n\n---\n\n报告生成时间：{timestamp}"
    
    return ReportGenerationNodeOutput(
        final_report=final_report
    )
