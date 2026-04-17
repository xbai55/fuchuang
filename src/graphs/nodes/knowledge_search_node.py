from langchain_core.runnables import RunnableConfig
from graphs.state import KnowledgeSearchNodeInput, KnowledgeSearchNodeOutput
from rag.local_rag import get_local_rag

_DEFAULT_LEGAL = (
    "依据《中华人民共和国反电信网络诈骗法》，"
    "任何单位和个人不得非法买卖、出租、出借电话卡、银行账户、支付账户等。"
)


def knowledge_search_node(
    state: KnowledgeSearchNodeInput,
    config: RunnableConfig,
) -> KnowledgeSearchNodeOutput:
    """
    title: 知识库检索
    desc: 基于本地 BM25 RAG 检索相似诈骗案例和法律依据
    """
    query = state.processed_text[:500]

    local_cases, local_legal = [], ""
    try:
        local_cases, local_legal = get_local_rag().search(query)
    except Exception:
        pass

    merged_cases = local_cases[:8] if local_cases else ["暂无相似案例，请继续分析"]
    legal_basis = local_legal or _DEFAULT_LEGAL

    return KnowledgeSearchNodeOutput(
        similar_cases=merged_cases,
        legal_basis=legal_basis,
    )
