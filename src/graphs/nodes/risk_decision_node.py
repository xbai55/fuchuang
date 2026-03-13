from graphs.state import RiskDecisionNodeInput

def risk_decision_node(state: RiskDecisionNodeInput):
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
