import json
from langchain_core.runnables import RunnableConfig
from graphs.state import InterventionNodeInput, InterventionNodeOutput
from utils.llm_client import call_llm

_SYSTEM_PROMPT = """你是专业的反诈骗干预专家。根据风险评估结果生成个性化预警信息。
必须严格返回以下 JSON 格式（不含任何其他文字）：
{"warning_message": "<针对用户角色的个性化警告文案>", "guardian_alert": <true|false>, "alert_reason": "<通知监护人的原因，不需要则为空字符串>"}
用户角色策略：elderly(老人)措辞温和详细；student(学生)强调不轻信陌生人；finance(财会)强调资金审批流程；general使用通用警告。
高风险（score>75）必须将 guardian_alert 设为 true。"""


def intervention_node(state: InterventionNodeInput, config: RunnableConfig) -> InterventionNodeOutput:
    """
    title: 干预措施生成
    desc: 根据风险等级和用户角色生成个性化预警文案和干预策略
    """
    cases_text = "\n".join(state.similar_cases) if state.similar_cases else "无"
    guardian_section = f"监护人：{state.guardian_name}" if state.guardian_name else ""
    user_prompt = (
        f"风险评分：{state.risk_score}，风险等级：{state.risk_level}\n"
        f"诈骗类型：{state.scam_type}\n"
        f"风险线索：{state.risk_clues}\n"
        f"用户角色：{state.user_role}\n"
        f"{guardian_section}\n"
        f"相似案例：{cases_text}\n"
        f"法律依据：{state.legal_basis}\n\n"
        "请生成个性化预警方案并返回 JSON 结果。"
    )

    response_text = call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        max_tokens=2000,
    )

    try:
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end <= json_start:
            raise ValueError("No JSON in response")
        result = json.loads(response_text[json_start:json_end])
        warning_message = result.get("warning_message", "请提高警惕，注意个人信息和资金安全。")
        guardian_alert = bool(result.get("guardian_alert", False))
        alert_reason = result.get("alert_reason", "")
    except Exception as e:
        warning_message = "警告：请立即停止与对方联系，不要转账汇款，并联系家人或拨打110报警。"
        guardian_alert = state.risk_score > 75
        alert_reason = "系统自动触发高风险预警" if guardian_alert else ""

    return InterventionNodeOutput(
        warning_message=warning_message,
        guardian_alert=guardian_alert,
        alert_reason=alert_reason,
    )
