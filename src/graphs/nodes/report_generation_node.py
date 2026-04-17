from datetime import datetime
from langchain_core.runnables import RunnableConfig
from graphs.state import ReportGenerationNodeInput, ReportGenerationNodeOutput
from utils.llm_client import call_llm

_SYSTEM_PROMPT = """你是专业的反诈骗安全报告生成专家。请根据分析结果生成完整的安全监测报告（Markdown格式）。
报告结构：
# 反诈骗安全监测报告
## 风险概览
## 诈骗类型分析
## 关键风险线索
## 相关法律依据
## 干预建议
---"""


def report_generation_node(state: ReportGenerationNodeInput, config: RunnableConfig) -> ReportGenerationNodeOutput:
    """
    title: 报告生成
    desc: 汇总所有分析结果，生成完整的安全监测报告
    """
    cases_text = "\n".join(state.similar_cases) if state.similar_cases else "无"
    user_prompt = (
        f"风险评分：{state.risk_score}，风险等级：{state.risk_level}\n"
        f"诈骗类型：{state.scam_type}\n"
        f"风险线索：{state.risk_clues}\n"
        f"相似案例：{cases_text}\n"
        f"法律依据：{state.legal_basis}\n"
        f"警告文案：{state.warning_message}\n"
        f"通知监护人：{'是' if state.guardian_alert else '否'}"
        + (f"，原因：{state.alert_reason}" if state.alert_reason else "") + "\n\n"
        "请生成完整的安全监测报告。"
    )

    final_report = call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=3000,
    )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    final_report += f"\n\n---\n\n报告生成时间：{timestamp}"

    return ReportGenerationNodeOutput(final_report=final_report)
