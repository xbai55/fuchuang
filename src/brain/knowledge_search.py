"""
增强版 Knowledge Search Service
集成 RAG 检索和风险检测能力
"""
from typing import List, Optional, Tuple

from src.core.models.state import GlobalState, RetrievedCase
from src.brain.rag.retriever import FraudCaseRetriever
from src.brain.rag.detector import RiskDetector
from src.brain.rag.models import RiskAssessmentResult, create_search_hit_from_retrieved_case
from src.brain.rag.vector_store import ChromaVectorStore
from src.brain.rag.indexer import SimilarityIndex


class KnowledgeSearchService:
    """
    增强版知识搜索服务

    集成 RAG 能力：
    - 混合检索 (ChromaDB + TF-IDF)
    - 精细化风险检测 (8种诈骗子类型)
    - 法律依据自动匹配

    Usage:
        # 基础用法
        service = KnowledgeSearchService()
        cases = await service.search(state)

        # 检索 + 风险评估
        cases, risk = await service.search_with_risk(state)

        # 自定义配置
        service = KnowledgeSearchService(
            retriever=FraudCaseRetriever(
                vector_store=chroma_store,
                tfidf_index=tfidf_index,
                use_hybrid=True,
            ),
            detector=RiskDetector(
                high_threshold=0.35,
                medium_threshold=0.20,
            ),
        )
    """

    def __init__(
        self,
        retriever: Optional[FraudCaseRetriever] = None,
        detector: Optional[RiskDetector] = None,
        vector_store: Optional[ChromaVectorStore] = None,
        tfidf_index_path: Optional[str] = None,
    ):
        """
        初始化知识搜索服务

        Args:
            retriever: 自定义检索器
            detector: 自定义风险检测器
            vector_store: ChromaDB 向量存储
            tfidf_index_path: TF-IDF 索引路径
        """
        if retriever:
            self.retriever = retriever
        else:
            # 创建默认检索器
            self.retriever = self._create_default_retriever(
                vector_store, tfidf_index_path
            )

        self.detector = detector or RiskDetector()

    def _create_default_retriever(
        self,
        vector_store: Optional[ChromaVectorStore],
        tfidf_index_path: Optional[str],
    ) -> FraudCaseRetriever:
        """
        创建默认检索器

        Args:
            vector_store: ChromaDB 向量存储
            tfidf_index_path: TF-IDF 索引路径

        Returns:
            FraudCaseRetriever 实例
        """
        # 加载 TF-IDF 索引（如果路径提供）
        tfidf_index = None
        if tfidf_index_path:
            try:
                from pathlib import Path
                tfidf_index = SimilarityIndex.load(Path(tfidf_index_path))
            except Exception as e:
                print(f"[警告] 加载 TF-IDF 索引失败: {e}")

        # 创建 ChromaDB 存储（如果未提供）
        if vector_store is None:
            vector_store = ChromaVectorStore(
                collection_name="fraud_cases",
                persist_directory="./data/vector_store",
            )

        # 判断是否使用混合模式
        use_hybrid = tfidf_index is not None and vector_store is not None

        return FraudCaseRetriever(
            vector_store=vector_store,
            tfidf_index=tfidf_index,
            use_hybrid=use_hybrid,
        )

    async def search(self, state: GlobalState) -> Tuple[List[RetrievedCase], List[str]]:
        """
        搜索相似案例和法律依据

        Args:
            state: 当前工作流状态

        Returns:
            (相似案例列表, 法律依据列表)
        """
        query = state.get_combined_text()

        if not query:
            return [], self._get_default_legal_basis()

        # 检索相似案例
        similar_cases = await self.retriever.retrieve_with_context(
            query=query,
            perception_results=state.perception_results,
            k=5,
        )

        # 获取法律依据
        scam_type = ""
        if state.risk_assessment and state.risk_assessment.scam_type:
            scam_type = state.risk_assessment.scam_type

        legal_basis = await self.retriever.get_legal_basis(scam_type)

        return similar_cases, legal_basis

    async def search_with_risk(
        self,
        state: GlobalState,
    ) -> Tuple[List[RetrievedCase], RiskAssessmentResult]:
        """
        检索 + 风险评估一体化

        Args:
            state: 当前工作流状态

        Returns:
            (相似案例列表, 风险评估结果)
        """
        query = state.get_combined_text()

        if not query:
            return [], RiskAssessmentResult(
                risk_level="low",
                confidence=0.0,
                matched_subtypes=[],
                matched_tags=[],
                recommendations=["未检索到明显关联知识，建议继续人工核验。"],
                hits=[],
            )

        # 检索相似案例
        retrieved_cases = await self.retriever.retrieve_with_context(
            query=query,
            perception_results=state.perception_results,
            k=5,
        )

        # 构建 SearchHit 列表用于风险评估
        search_hits = [
            create_search_hit_from_retrieved_case(
                case,
                category=getattr(case, 'category', 'case'),
                subtype=getattr(case, 'subtype', None),
                tags=getattr(case, 'tags', []),
            )
            for case in retrieved_cases
        ]

        # 执行风险评估
        risk_result = self.detector.assess(query, search_hits)

        return retrieved_cases, risk_result

    async def ingest_case(
        self,
        case_id: str,
        title: str,
        content: str,
        case_type: str,
        source: str = "manual",
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        将新案例入库

        Args:
            case_id: 案例唯一标识
            title: 案例标题
            content: 案例内容
            case_type: 诈骗类型
            source: 来源
            metadata: 额外元数据

        Returns:
            是否成功
        """
        try:
            from src.brain.rag.vector_store import VectorDocument

            meta = metadata or {}
            meta.update({
                "title": title,
                "type": case_type,
                "source": source,
            })

            document = VectorDocument(
                id=case_id,
                content=content,
                metadata=meta,
            )

            await self.retriever.vector_store.add_documents([document])
            return True

        except Exception as e:
            print(f"[错误] 案例入库失败: {e}")
            return False

    async def ingest_legal_basis(
        self,
        law_id: str,
        content: str,
        law_type: str,
    ) -> bool:
        """
        将法律依据入库

        Args:
            law_id: 法律条文标识
            content: 法律内容
            law_type: 法律类型

        Returns:
            是否成功
        """
        try:
            from src.brain.rag.vector_store import VectorDocument

            document = VectorDocument(
                id=law_id,
                content=content,
                metadata={
                    "type": "legal_basis",
                    "law_type": law_type,
                },
            )

            await self.retriever.vector_store.add_documents([document])
            return True

        except Exception as e:
            print(f"[错误] 法律依据入库失败: {e}")
            return False

    async def get_stats(self) -> dict:
        """
        获取知识库统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "retriever": self.retriever.get_stats(),
            "detector": self.detector.get_stats(),
        }

        # 添加向量存储统计
        if self.retriever.vector_store:
            try:
                vector_stats = await self.retriever.vector_store.get_stats()
                stats["vector_store"] = vector_stats
            except Exception as e:
                stats["vector_store_error"] = str(e)

        # 添加 TF-IDF 统计
        if self.retriever.tfidf_index:
            stats["tfidf_index"] = self.retriever.tfidf_index.get_stats()

        return stats

    def _get_default_legal_basis(self) -> List[str]:
        """
        获取默认法律依据

        Returns:
            法律依据列表
        """
        return [
            "《中华人民共和国刑法》第二百六十六条：诈骗罪",
            "《中华人民共和国反电信网络诈骗法》",
            "《关于办理电信网络诈骗等刑事案件适用法律若干问题的意见》",
        ]
