from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import KnowledgeClient, Config
from graphs.state import KnowledgeSearchNodeInput, KnowledgeSearchNodeOutput

def knowledge_search_node(state: KnowledgeSearchNodeInput, config: RunnableConfig, runtime: Runtime[Context]) -> KnowledgeSearchNodeOutput:
    """
    title: 知识库检索
    desc: 在知识库中检索与输入内容相似的诈骗案例和法律依据
    integrations: 知识库
    """
    ctx = runtime.context
    
    # 初始化知识库客户端
    config_obj = Config()
    client = KnowledgeClient(config=config_obj, ctx=ctx)
    
    # 构建检索查询
    query = f"诈骗案例 警示 法律依据: {state.processed_text[:500]}"
    
    try:
        # 搜索相似案例和法律依据
        response = client.search(
            query=query,
            top_k=5,
            min_score=0.5
        )
        
        similar_cases = []
        legal_basis = ""
        
        if response.code == 0 and response.chunks:
            # 提取相似案例
            for chunk in response.chunks:
                if chunk.score > 0.6:
                    similar_cases.append(f"[相似度: {chunk.score:.2f}] {chunk.content}")
            
            # 构建法律依据（从搜索结果中提取包含法律条文的内容）
            legal_chunks = [chunk.content for chunk in response.chunks 
                           if "法律" in chunk.content or "法条" in chunk.content or "反电信网络诈骗法" in chunk.content]
            if legal_chunks:
                legal_basis = "\n\n".join(legal_chunks[:3])
        
        # 如果没有搜索到结果，返回默认提示
        if not similar_cases:
            similar_cases = ["暂无相似案例，请继续分析"]
        if not legal_basis:
            legal_basis = "依据《中华人民共和国反电信网络诈骗法》，任何单位和个人不得非法买卖、出租、出借电话卡、银行账户、支付账户等。"
    
    except Exception as e:
        # 搜索失败，返回默认信息
        similar_cases = [f"知识库检索失败: {str(e)}"]
        legal_basis = "依据《中华人民共和国反电信网络诈骗法》，任何单位和个人不得非法买卖、出租、出借电话卡、银行账户、支付账户等。"
    
    return KnowledgeSearchNodeOutput(
        similar_cases=similar_cases,
        legal_basis=legal_basis
    )
