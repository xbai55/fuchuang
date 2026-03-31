"""
Anti-Fraud Workflow Graph - PDIE Architecture

Refactored graph using the new Perception-Decision-Intervention-Evolution architecture.
This replaces the original graph with cleaner, modular node implementations.
"""
from langgraph.graph import StateGraph, END

# Import new state model
from src.core.models import GlobalState, RiskLevel

# Import new node classes
from src.graphs.nodes import (
    PerceptionNode,
    KnowledgeSearchNode,
    RiskAssessmentNode,
    RiskDecisionNode,
    InterventionNode,
    ReportNode,
)


def create_graph():
    """
    Create the anti-fraud workflow graph.

    Workflow:
    1. Perception: Process multi-modal inputs (text, audio, image, video)
    2. Knowledge Search: Retrieve similar cases using RAG
    3. Risk Assessment: Evaluate fraud risk
    4. Risk Decision: Route based on risk level
    5. Intervention: Generate warnings and alerts
    6. Report: Generate final report

    Returns:
        Compiled StateGraph
    """
    # Create node instances
    perception = PerceptionNode()
    knowledge = KnowledgeSearchNode()
    risk = RiskAssessmentNode()
    decision = RiskDecisionNode()
    intervention = InterventionNode()
    report = ReportNode()

    # Build graph
    builder = StateGraph(GlobalState)

    # Add nodes (注意：节点名不能和 GlobalState 字段名冲突)
    builder.add_node("perception", perception.run)
    builder.add_node("knowledge_search", knowledge.run)
    builder.add_node("risk_assessor", risk.run)  # 避免与 state.risk_assessment 冲突
    builder.add_node("risk_decision", decision.run)
    builder.add_node("intervention_node", intervention.run)  # 避免与 state.intervention 冲突
    builder.add_node("report_generation", report.run)

    # Set entry point
    builder.set_entry_point("perception")

    # Add edges
    builder.add_edge("perception", "knowledge_search")
    builder.add_edge("knowledge_search", "risk_assessor")
    builder.add_edge("risk_assessor", "risk_decision")

    # Add conditional routing based on risk level
    builder.add_conditional_edges(
        source="risk_decision",
        path=lambda state: state.risk_assessment.level.value if state.risk_assessment else "low",
        path_map={
            "low": "intervention_node",
            "medium": "intervention_node",
            "high": "intervention_node",
        }
    )

    # All risk levels go to intervention (with different handling inside)
    builder.add_edge("intervention_node", "report_generation")
    builder.add_edge("report_generation", END)

    return builder.compile()


# Create and compile the graph
main_graph = create_graph()

# For backward compatibility
builder = create_graph()
