from langgraph.graph import StateGraph, END
from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput,
    RiskDecisionNodeInput
)
from graphs.nodes.multimodal_input_node import multimodal_input_node
from graphs.nodes.knowledge_search_node import knowledge_search_node
from graphs.nodes.risk_assessment_node import risk_assessment_node
from graphs.nodes.risk_decision_node import risk_decision_node
from graphs.nodes.intervention_node import intervention_node
from graphs.nodes.report_generation_node import report_generation_node

# 条件判断函数：根据风险评分决定后续流程
def risk_decision(state: RiskDecisionNodeInput):
    """
    title: 风险分级决策
    desc: 根据风险评分和等级决定后续处理流程
    """
    if state.risk_score < 40:
        return "低风险处理"
    elif state.risk_score <= 75:
        return "中风险处理"
    else:
        return "高风险处理"

# 创建状态图，指定工作流的入参和出参
builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

# 添加节点
builder.add_node("multimodal_input", multimodal_input_node)
builder.add_node("knowledge_search", knowledge_search_node)
builder.add_node("risk_assessment", risk_assessment_node)
builder.add_node("intervention", intervention_node)
builder.add_node("report_generation", report_generation_node)

# 设置入口点
builder.set_entry_point("multimodal_input")

# 添加边
builder.add_edge("multimodal_input", "knowledge_search")
builder.add_edge("knowledge_search", "risk_assessment")

# 添加条件分支
builder.add_conditional_edges(
    source="risk_assessment",
    path=risk_decision,
    path_map={
        "低风险处理": "intervention",
        "中风险处理": "intervention",
        "高风险处理": "intervention"
    }
)

# 无论何种风险等级，都经过干预节点生成相应的警告文案
builder.add_edge("intervention", "report_generation")
builder.add_edge("report_generation", END)

# 编译图
main_graph = builder.compile()
