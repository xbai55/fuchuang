import json
from langchain_core.runnables import RunnableConfig
from graphs.state import RiskAssessmentNodeInput, RiskAssessmentNodeOutput
from utils.llm_client import call_llm

_SYSTEM_PROMPT = """你是专业的反诈骗风险评估专家。分析用户提供的内容，评估诈骗风险。
必须严格返回以下 JSON 格式（不含任何其他文字）：
{"risk_score": <0-100整数>, "risk_level": "<low|medium|high>", "scam_type": "<诈骗类型>", "risk_clues": "<关键风险线索描述>"}
risk_level 规则：0-39 为 low，40-75 为 medium，76-100 为 high。"""


def risk_assessment_node(state: RiskAssessmentNodeInput, config: RunnableConfig) -> RiskAssessmentNodeOutput:
    """
    title: 风险评估
    desc: 基于多维度信息分析诈骗风险，给出评分、等级和类型判断
    """
    cases_text = "\n".join(state.similar_cases) if state.similar_cases else "无相似案例"
    image_section = f"\n图片分析：{state.image_analysis}" if state.image_analysis else ""
    user_prompt = (
        f"用户角色：{state.user_role}\n"
        f"用户输入：{state.processed_text}"
        f"{image_section}\n"
        f"相似案例：\n{cases_text}\n"
        f"法律依据：{state.legal_basis}\n\n"
        "请综合分析并返回 JSON 格式风险评估结果。"
    )

    response_text = call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1000,
    )

    try:
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end <= json_start:
            raise ValueError("No JSON in response")
        result = json.loads(response_text[json_start:json_end])
        risk_score = max(0, min(100, int(result.get("risk_score", 0))))
        risk_level = result.get("risk_level", "low")
        scam_type = result.get("scam_type", "未知类型")
        risk_clues = result.get("risk_clues", "无明确线索")
    except Exception as e:
        risk_score = 0
        risk_level = "low"
        scam_type = "分析失败"
        risk_clues = f"风险评估失败: {str(e)}"

    return RiskAssessmentNodeOutput(
        risk_score=risk_score,
        risk_level=risk_level,
        scam_type=scam_type,
        risk_clues=risk_clues,
    )
