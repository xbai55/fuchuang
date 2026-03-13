import os
import json
from typing import Union, List, Dict
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage
from jinja2 import Template
from graphs.state import RiskAssessmentNodeInput, RiskAssessmentNodeOutput

def risk_assessment_node(state: RiskAssessmentNodeInput, config: RunnableConfig, runtime: Runtime[Context]) -> RiskAssessmentNodeOutput:
    """
    title: 风险评估
    desc: 基于多维度信息分析诈骗风险，给出评分、等级和类型判断
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
    
    # 准备相似案例文本
    similar_cases_text = "\n".join(state.similar_cases) if state.similar_cases else "无相似案例"
    
    # 使用jinja2模板渲染用户提示词
    up_tpl = Template(up_template)
    user_prompt_content = up_tpl.render(
        user_role=state.user_role,
        processed_text=state.processed_text,
        image_analysis=state.image_analysis,
        similar_cases=state.similar_cases,
        legal_basis=state.legal_basis
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
        temperature=llm_config.get("temperature", 0.3),
        max_completion_tokens=llm_config.get("max_completion_tokens", 4000),
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
        
        risk_score = int(result.get("risk_score", 0))
        risk_level = result.get("risk_level", "low")
        scam_type = result.get("scam_type", "未知类型")
        risk_clues = result.get("risk_clues", "无明确线索")
    except Exception as e:
        # JSON解析失败，使用默认值
        risk_score = 0
        risk_level = "low"
        scam_type = "分析失败"
        risk_clues = f"风险评估失败: {str(e)}"
    
    return RiskAssessmentNodeOutput(
        risk_score=risk_score,
        risk_level=risk_level,
        scam_type=scam_type,
        risk_clues=risk_clues
    )
