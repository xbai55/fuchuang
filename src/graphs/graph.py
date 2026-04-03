"""
Anti-fraud workflow graph using the PDIE architecture.
"""
from langgraph.graph import END, StateGraph

from src.core.models import GlobalState
from src.graphs.nodes import (
    IntentRecognitionNode,
    InterventionNode,
    KnowledgeSearchNode,
    PerceptionNode,
    ReportNode,
    RiskAssessmentNode,
    RiskDecisionNode,
)
from src.storage.memory.memory_saver import get_memory_saver


_graph_components = {}


def create_graph():
    """Create and compile the main anti-fraud workflow graph."""
    perception = PerceptionNode()
    intent = IntentRecognitionNode()
    knowledge = KnowledgeSearchNode()
    risk = RiskAssessmentNode()
    decision = RiskDecisionNode()
    intervention = InterventionNode()
    report = ReportNode()

    global _graph_components
    _graph_components = {
        "perception": perception,
        "intent_recognition": intent,
        "knowledge_search": knowledge,
        "risk_assessment": risk,
        "risk_decision": decision,
        "intervention": intervention,
        "report_generation": report,
    }

    builder = StateGraph(GlobalState)
    builder.add_node("perception", perception.run)
    builder.add_node("intent_recognition", intent.run)
    builder.add_node("knowledge_search", knowledge.run)
    builder.add_node("risk_assessor", risk.run)
    builder.add_node("risk_decision", decision.run)
    builder.add_node("intervention_node", intervention.run)
    builder.add_node("report_generation", report.run)

    builder.set_entry_point("perception")
    builder.add_edge("perception", "intent_recognition")
    builder.add_edge("intent_recognition", "knowledge_search")
    builder.add_edge("knowledge_search", "risk_assessor")
    builder.add_edge("risk_assessor", "risk_decision")
    builder.add_conditional_edges(
        source="risk_decision",
        path=lambda state: state.risk_assessment.level.value if state.risk_assessment else "low",
        path_map={
            "low": "intervention_node",
            "medium": "intervention_node",
            "high": "intervention_node",
        },
    )
    builder.add_edge("intervention_node", "report_generation")
    builder.add_edge("report_generation", END)

    return builder.compile(checkpointer=get_memory_saver())


_main_graph = None


def get_main_graph():
    """Lazily create the compiled graph."""
    global _main_graph
    if _main_graph is None:
        _main_graph = create_graph()
    return _main_graph


def get_graph_components():
    """Get graph node instances used by the compiled workflow."""
    get_main_graph()
    return _graph_components


class _LazyGraph:
    """Proxy that compiles the graph only when first used."""

    def __getattr__(self, name):
        return getattr(get_main_graph(), name)


main_graph = _LazyGraph()
builder = main_graph
