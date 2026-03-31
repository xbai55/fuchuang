"""
RAG 模块集成测试
验证融合后的 RAG 功能是否正常工作
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试模块导入")
    print("=" * 60)

    try:
        from src.brain.rag import (
            KnowledgeChunk,
            KnowledgeDocument,
            SearchHit,
            RiskAssessmentResult,
            SimilarityIndex,
            RiskDetector,
            FraudCaseRetriever,
            KnowledgePipeline,
            SUBTYPE_ADVICE,
        )
        print("✓ RAG 模块导入成功")
        return True
    except Exception as e:
        print(f"✗ RAG 模块导入失败: {e}")
        return False


def test_models():
    """测试数据模型"""
    print("\n" + "=" * 60)
    print("测试数据模型")
    print("=" * 60)

    from src.brain.rag import KnowledgeChunk, SearchHit

    try:
        # 创建 KnowledgeChunk
        chunk = KnowledgeChunk(
            chunk_id="test-001",
            doc_id="doc-001",
            category="case",
            subtype="investment_fraud",
            title="虚假投资诈骗案例",
            text="诈骗分子通过高收益截图诱骗受害者投资",
            source_url="https://example.com/case/001",
            source_site="example.com",
            tags=["投资诈骗", "高收益"],
        )
        print(f"✓ KnowledgeChunk 创建成功: {chunk.title}")

        # 创建 SearchHit
        hit = SearchHit(score=0.85, chunk=chunk)
        print(f"✓ SearchHit 创建成功: score={hit.score}")

        # 测试序列化
        chunk_dict = chunk.to_dict()
        print(f"✓ 序列化成功: {len(chunk_dict)} 个字段")

        # 测试反序列化
        chunk_restored = KnowledgeChunk.from_dict(chunk_dict)
        print(f"✓ 反序列化成功: {chunk_restored.title}")

        return True
    except Exception as e:
        print(f"✗ 数据模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_detector():
    """测试风险检测器"""
    print("\n" + "=" * 60)
    print("测试风险检测器")
    print("=" * 60)

    from src.brain.rag import RiskDetector, KnowledgeChunk, SearchHit

    try:
        detector = RiskDetector(
            high_threshold=0.32,
            medium_threshold=0.18,
        )
        print("✓ RiskDetector 创建成功")

        # 创建测试数据
        chunks = [
            KnowledgeChunk(
                chunk_id=f"test-{i:03d}",
                doc_id=f"doc-{i:03d}",
                category=cat,
                subtype=sub,
                title=f"案例 {i}",
                text=f"诈骗文本示例 {i}",
                source_url="https://example.com",
                source_site="example.com",
                tags=tags,
            )
            for i, (cat, sub, tags) in enumerate([
                ("case", "investment_fraud", ["投资诈骗", "高收益"]),
                ("law", "fraud_law", ["法律", "刑法"]),
                ("photo_type", "fake_investment_dashboard", ["截图", "虚假"]),
            ])
        ]

        hits = [
            SearchHit(score=0.35, chunk=chunks[0]),
            SearchHit(score=0.25, chunk=chunks[1]),
            SearchHit(score=0.20, chunk=chunks[2]),
        ]

        # 执行评估
        result = detector.assess("投资高收益截图诈骗", hits)
        print(f"✓ 风险评估成功")
        print(f"  - 风险等级: {result.risk_level}")
        print(f"  - 置信度: {result.confidence:.2%}")
        print(f"  - 匹配子类型: {result.matched_subtypes}")
        print(f"  - 建议数: {len(result.recommendations)}")

        return True
    except Exception as e:
        print(f"✗ 风险检测器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_indexer():
    """测试索引器"""
    print("\n" + "=" * 60)
    print("测试 TF-IDF 索引器")
    print("=" * 60)

    from src.brain.rag import SimilarityIndex, KnowledgeChunk

    try:
        # 创建测试数据
        chunks = [
            KnowledgeChunk(
                chunk_id=f"chunk-{i:03d}",
                doc_id=f"doc-{i:03d}",
                category="case",
                subtype="investment_fraud" if i % 2 == 0 else "customer_service_fraud",
                title=f"诈骗案例 {i}",
                text=text,
                source_url="https://example.com",
                source_site="example.com",
            )
            for i, text in enumerate([
                "高收益投资理财诈骗，保本保息",
                "虚假客服退款诈骗，要求转账",
                "投资导师带单，保证收益",
                "冒充客服要求验证码",
            ])
        ]

        # 构建索引
        index = SimilarityIndex.build(chunks, backend="tfidf")
        print(f"✓ TF-IDF 索引构建成功: {len(chunks)} chunks")

        # 搜索测试
        hits = index.search("投资理财高收益", top_k=3)
        print(f"✓ 搜索成功: 返回 {len(hits)} 条结果")

        if hits:
            print(f"  - 最佳匹配: {hits[0].chunk.title} (score={hits[0].score:.4f})")

        # 测试保存/加载
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            index.save(tmp_path)
            print(f"✓ 索引保存成功")

            loaded_index = SimilarityIndex.load(tmp_path)
            print(f"✓ 索引加载成功: backend={loaded_index.backend}")

        return True
    except Exception as e:
        print(f"✗ 索引器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_conversion():
    """测试模型转换"""
    print("\n" + "=" * 60)
    print("测试模型转换 (SearchHit ↔ RetrievedCase)")
    print("=" * 60)

    from src.brain.rag import (
        KnowledgeChunk,
        SearchHit,
        convert_search_hit_to_retrieved_case,
        create_search_hit_from_retrieved_case,
    )
    from src.core.models.state import RetrievedCase

    try:
        # SearchHit -> RetrievedCase
        chunk = KnowledgeChunk(
            chunk_id="test-001",
            doc_id="doc-001",
            category="case",
            subtype="investment_fraud",
            title="投资诈骗案例",
            text="诈骗详情...",
            source_url="https://example.com",
            source_site="example.com",
            tags=["投资诈骗"],
        )
        hit = SearchHit(score=0.85, chunk=chunk)

        case = convert_search_hit_to_retrieved_case(hit)
        print(f"✓ SearchHit -> RetrievedCase 成功")
        print(f"  - case_id: {case.case_id}")
        print(f"  - title: {case.title}")
        print(f"  - similarity: {case.similarity}")

        # RetrievedCase -> SearchHit
        case2 = RetrievedCase(
            case_id="case-002",
            title="客服诈骗案例",
            content="冒充客服诈骗详情...",
            similarity=0.75,
            source="example.com",
        )
        hit2 = create_search_hit_from_retrieved_case(
            case2,
            category="case",
            subtype="customer_service_fraud",
            tags=["客服诈骗"],
        )
        print(f"✓ RetrievedCase -> SearchHit 成功")
        print(f"  - chunk_id: {hit2.chunk.chunk_id}")
        print(f"  - category: {hit2.chunk.category}")
        print(f"  - subtype: {hit2.chunk.subtype}")

        return True
    except Exception as e:
        print(f"✗ 模型转换测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_pipeline():
    """测试知识库管道"""
    print("\n" + "=" * 60)
    print("测试知识库管道")
    print("=" * 60)

    from src.brain.rag import KnowledgePipeline

    try:
        config = {
            "root": "./test_data",
            "paths": {
                "raw_documents": "test_data/raw/documents.jsonl",
                "processed_documents": "test_data/processed/documents.jsonl",
                "chunks": "test_data/processed/chunks.jsonl",
                "index_dir": "test_data/index",
            },
            "index": {
                "backend": "tfidf",
                "chunk_size": 100,
                "chunk_overlap": 20,
                "top_k": 5,
            },
        }

        pipeline = KnowledgePipeline(config)
        print("✓ KnowledgePipeline 创建成功")

        stats = pipeline.get_stats()
        print(f"✓ 获取统计信息成功")
        print(f"  - 后端: {stats['config']['backend']}")
        print(f"  - 分块大小: {stats['config']['chunk_size']}")

        return True
    except Exception as e:
        print(f"✗ 管道测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """测试配置加载"""
    print("\n" + "=" * 60)
    print("测试配置加载")
    print("=" * 60)

    from src.brain.rag import load_rag_config_from_dict

    try:
        config_dict = {
            "root": ".",
            "index": {
                "backend": "hybrid",
                "high_threshold": 0.35,
                "medium_threshold": 0.20,
            },
        }

        config = load_rag_config_from_dict(config_dict)
        print(f"✓ 配置加载成功")
        print(f"  - 后端: {config.index.backend}")
        print(f"  - 高风险阈值: {config.warning.high_threshold}")
        print(f"  - 中风险阈值: {config.warning.medium_threshold}")

        return True
    except Exception as e:
        print(f"✗ 配置加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("RAG 模块集成测试")
    print("=" * 60)

    results = []

    # 运行所有测试
    results.append(("模块导入", test_imports()))
    results.append(("数据模型", test_models()))
    results.append(("风险检测器", test_detector()))
    results.append(("TF-IDF 索引器", test_indexer()))
    results.append(("模型转换", test_model_conversion()))
    results.append(("配置加载", test_config()))

    # 异步测试
    results.append(("知识库管道", asyncio.run(test_pipeline())))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")

    print(f"\n总计: {passed}/{total} 项通过")

    if passed == total:
        print("\n🎉 所有测试通过！RAG 模块集成成功。")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 项测试失败，请检查日志。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
