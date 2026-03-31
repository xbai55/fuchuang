"""
增强版 FraudCaseRetriever
支持 ChromaDB + TF-IDF 混合检索
从原 retriever.py 升级，集成 RAG 能力
"""
from typing import List, Optional, Any

from src.brain.rag.indexer import SimilarityIndex
from src.brain.rag.models import (
    SearchHit,
    KnowledgeChunk,
    convert_search_hits_to_retrieved_cases,
)
from src.core.models.state import RetrievedCase


class FraudCaseRetriever:
    """
    统一检索器 - 支持多种后端

    Features:
    - ChromaDB 语义检索 (默认)
    - TF-IDF 字符级检索 (备用)
    - 混合检索模式 (加权融合)

    Usage:
        # 仅使用 ChromaDB
        retriever = FraudCaseRetriever(vector_store=chroma_store)

        # 仅使用 TF-IDF
        retriever = FraudCaseRetriever(tfidf_index=tfidf_index)

        # 混合模式
        retriever = FraudCaseRetriever(
            vector_store=chroma_store,
            tfidf_index=tfidf_index,
            use_hybrid=True,
        )
    """

    def __init__(
        self,
        vector_store: Optional[Any] = None,
        tfidf_index: Optional[SimilarityIndex] = None,
        default_k: int = 5,
        use_hybrid: bool = False,
        hybrid_weights: Optional[dict] = None,
    ):
        """
        初始化检索器

        Args:
            vector_store: ChromaDB 向量存储实例
            tfidf_index: TF-IDF 索引实例
            default_k: 默认返回结果数
            use_hybrid: 是否使用混合检索
            hybrid_weights: 混合检索权重 {"dense": float, "sparse": float}
        """
        self.vector_store = vector_store
        self.tfidf_index = tfidf_index
        self.default_k = default_k
        self.use_hybrid = use_hybrid
        self.hybrid_weights = hybrid_weights or {"dense": 0.7, "sparse": 0.3}

    async def retrieve(
        self,
        query: str,
        perception_result: Optional[Any] = None,
        k: Optional[int] = None,
    ) -> List[RetrievedCase]:
        """
        统一检索入口

        Strategy:
        1. 优先使用 ChromaDB 语义检索
        2. 如不可用，使用 TF-IDF
        3. 混合模式：两者结果加权融合

        Args:
            query: 查询文本
            perception_result: 感知层结果（用于查询增强）
            k: 返回结果数量

        Returns:
            RetrievedCase 列表
        """
        k = k or self.default_k

        # 查询增强
        enhanced_query = self._enhance_query(query, perception_result)

        if self.use_hybrid and self.tfidf_index and self.vector_store:
            # 混合检索
            hits = await self._hybrid_search(enhanced_query, k)
        elif self.vector_store:
            # ChromaDB 检索
            hits = await self._vector_search(enhanced_query, k)
        elif self.tfidf_index:
            # TF-IDF 检索
            hits = self._tfidf_search(enhanced_query, k)
        else:
            raise RuntimeError("No search backend available")

        return convert_search_hits_to_retrieved_cases(hits)

    async def retrieve_with_context(
        self,
        query: str,
        perception_results: List[Any],
        k: int = 5,
    ) -> List[RetrievedCase]:
        """
        带上下文的检索

        Args:
            query: 基础查询
            perception_results: 多个感知结果
            k: 返回结果数

        Returns:
            RetrievedCase 列表
        """
        # 合并所有文本
        all_texts = [query]
        all_indicators = []

        for result in perception_results:
            if hasattr(result, 'text_content') and result.text_content:
                all_texts.append(result.text_content)
            if hasattr(result, 'get_risk_indicators'):
                all_indicators.extend(result.get_risk_indicators())

        combined_query = "\n".join(all_texts)

        # 添加风险上下文
        if all_indicators:
            risk_context = "风险特征: " + ", ".join(all_indicators)
            combined_query = f"{combined_query}\n{risk_context}"

        return await self.retrieve(combined_query, k=k)

    async def _vector_search(self, query: str, k: int) -> List[SearchHit]:
        """
        ChromaDB 向量检索

        Args:
            query: 查询文本
            k: 返回结果数

        Returns:
            SearchHit 列表
        """
        if not self.vector_store:
            return []

        documents = await self.vector_store.search(query=query, k=k)

        hits = []
        for i, doc in enumerate(documents):
            # 构建 KnowledgeChunk
            metadata = doc.metadata or {}
            chunk = KnowledgeChunk(
                chunk_id=doc.id,
                doc_id=doc.id,
                category=metadata.get("type", "case"),
                subtype=metadata.get("subtype"),
                title=metadata.get("title", "未知案例"),
                text=doc.content,
                source_url=metadata.get("source", ""),
                source_site=metadata.get("source", ""),
                tags=metadata.get("tags", []),
            )
            # ChromaDB 不直接返回相似度分数，使用排名推导
            score = 1.0 - (i * 0.1)
            hits.append(SearchHit(score=score, chunk=chunk))

        return hits

    def _tfidf_search(self, query: str, k: int) -> List[SearchHit]:
        """
        TF-IDF 检索

        Args:
            query: 查询文本
            k: 返回结果数

        Returns:
            SearchHit 列表
        """
        if not self.tfidf_index:
            return []

        return self.tfidf_index.search(query, top_k=k)

    async def _hybrid_search(self, query: str, k: int) -> List[SearchHit]:
        """
        混合检索：语义 + TF-IDF 加权融合

        Fusion Strategy:
        1. 分别获取两种检索的 top-2k 结果
        2. 归一化分数
        3. 加权融合相同文档的分数
        4. 重新排序取 top-k

        Args:
            query: 查询文本
            k: 返回结果数

        Returns:
            SearchHit 列表
        """
        # 获取更多结果用于融合
        vector_hits = await self._vector_search(query, k * 2)
        tfidf_hits = self._tfidf_search(query, k * 2)

        # 融合结果
        merged = self._merge_hits(
            vector_hits,
            tfidf_hits,
            k,
            self.hybrid_weights["dense"],
            self.hybrid_weights["sparse"],
        )

        return merged

    def _merge_hits(
        self,
        dense_hits: List[SearchHit],
        sparse_hits: List[SearchHit],
        k: int,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> List[SearchHit]:
        """
        融合两种检索结果

        Args:
            dense_hits: 密集检索结果
            sparse_hits: 稀疏检索结果
            k: 返回结果数
            dense_weight: 密集检索权重
            sparse_weight: 稀疏检索权重

        Returns:
            融合后的 SearchHit 列表
        """
        # 归一化分数
        dense_max = max([h.score for h in dense_hits], default=1.0) or 1.0
        sparse_max = max([h.score for h in sparse_hits], default=1.0) or 1.0

        # 构建文档到分数的映射
        score_map: dict[str, float] = {}
        chunk_map: dict[str, KnowledgeChunk] = {}

        # 添加密集检索结果
        for hit in dense_hits:
            key = hit.chunk.chunk_id
            normalized_score = hit.score / dense_max
            score_map[key] = score_map.get(key, 0) + normalized_score * dense_weight
            chunk_map[key] = hit.chunk

        # 添加稀疏检索结果
        for hit in sparse_hits:
            key = hit.chunk.chunk_id
            normalized_score = hit.score / sparse_max
            score_map[key] = score_map.get(key, 0) + normalized_score * sparse_weight
            if key not in chunk_map:
                chunk_map[key] = hit.chunk

        # 排序并取 top-k
        sorted_items = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:k]

        return [SearchHit(score=score, chunk=chunk_map[key]) for key, score in sorted_items]

    def _enhance_query(
        self,
        query: str,
        perception_result: Optional[Any],
    ) -> str:
        """
        增强搜索查询

        Args:
            query: 原始查询
            perception_result: 感知结果

        Returns:
            增强后的查询
        """
        if not perception_result:
            return query

        parts = [query]

        # 添加风险指标
        if hasattr(perception_result, 'get_risk_indicators'):
            risk_indicators = perception_result.get_risk_indicators()
            if risk_indicators:
                parts.append("风险特征: " + ", ".join(risk_indicators))

        # 添加伪造检测信息
        if hasattr(perception_result, 'fake_analysis'):
            fake_analysis = perception_result.fake_analysis
            if fake_analysis and getattr(fake_analysis, 'is_fake', False):
                parts.append("AI伪造内容检测")

        return "\n".join(parts)

    async def get_legal_basis(self, case_type: str) -> List[str]:
        """
        获取相关法律依据

        Args:
            case_type: 案例类型

        Returns:
            法律依据列表
        """
        default_basis = [
            "《中华人民共和国刑法》第二百六十六条：诈骗罪",
            "《中华人民共和国反电信网络诈骗法》",
            "《关于办理电信网络诈骗等刑事案件适用法律若干问题的意见》",
        ]

        try:
            if self.tfidf_index:
                hits = self.tfidf_index.search(f"法律依据 {case_type}", top_k=3)
                # 过滤法律类别
                law_hits = [h for h in hits if h.chunk.category == "law"]
                if law_hits:
                    return [h.chunk.text for h in law_hits]

            if self.vector_store:
                documents = await self.vector_store.search(
                    query=f"法律依据 {case_type}",
                    k=3,
                    filter_dict={"type": "legal_basis"},
                )
                if documents:
                    return [doc.content for doc in documents]
        except Exception as e:
            print(f"[警告] 获取法律依据失败: {e}")

        return default_basis

    def get_stats(self) -> dict:
        """
        获取检索器统计信息

        Returns:
            统计信息字典
        """
        return {
            "has_vector_store": self.vector_store is not None,
            "has_tfidf_index": self.tfidf_index is not None,
            "use_hybrid": self.use_hybrid,
            "default_k": self.default_k,
            "hybrid_weights": self.hybrid_weights,
        }
