from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import KnowledgeClient, Config
from graphs.state import KnowledgeSearchNodeInput, KnowledgeSearchNodeOutput
from rag.local_rag import get_local_rag

_DEFAULT_LEGAL = (
    "依据《中华人民共和国反电信网络诈骗法》，"
    "任何单位和个人不得非法买卖、出租、出借电话卡、银行账户、支付账户等。"
)


def knowledge_search_node(
    state: KnowledgeSearchNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context],
) -> KnowledgeSearchNodeOutput:
    """
    title: 知识库检索
    desc: 融合本地 BM25 RAG 与 Coze 云端知识库，检索相似诈骗案例和法律依据
    integrations: 知识库
    """
    query = state.processed_text[:500]

    # ── 1. 本地 RAG ──────────────────────────────────────────────────────
    local_cases, local_legal = [], ""
    try:
        local_cases, local_legal = get_local_rag().search(query)
    except Exception as e:
        pass  # 本地检索失败不影响主流程

    # ── 2. Coze 云端知识库 ──────────────────────────────────────────────
    cloud_cases, cloud_legal = [], ""
    try:
        ctx = runtime.context
        client = KnowledgeClient(config=Config(), ctx=ctx)
        response = client.search(
            query=f"诈骗案例 警示 法律依据: {query}",
            top_k=5,
            min_score=0.5,
        )
        if response.code == 0 and response.chunks:
            for chunk in response.chunks:
                if chunk.score > 0.6:
                    cloud_cases.append(f"[相似度:{chunk.score:.2f}] {chunk.content}")
            legal_chunks = [
                c.content for c in response.chunks
                if any(kw in c.content for kw in ("法律", "法条", "反电信网络诈骗法"))
            ]
            if legal_chunks:
                cloud_legal = "\n\n".join(legal_chunks[:3])
    except Exception:
        pass  # 云端不可用时退化到纯本地

    # ── 3. 合并结果 ──────────────────────────────────────────────────────
    # 本地案例优先（带 [本地案例] 标签），云端案例追加在后，总数不超过 8 条
    seen: set = set()
    merged_cases = []
    for case in local_cases + cloud_cases:
        key = case[:80]
        if key not in seen:
            seen.add(key)
            merged_cases.append(case)
        if len(merged_cases) >= 8:
            break

    if not merged_cases:
        merged_cases = ["暂无相似案例，请继续分析"]

    # 法律依据：本地优先，云端补充，最终兜底默认条文
    legal_basis = local_legal or cloud_legal or _DEFAULT_LEGAL

    return KnowledgeSearchNodeOutput(
        similar_cases=merged_cases,
        legal_basis=legal_basis,
    )
