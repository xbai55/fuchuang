"""
RAG 模块简单测试（不依赖完整项目环境）
"""
import sys
from pathlib import Path

# 只添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_models():
    """测试数据模型"""
    print("=" * 60)
    print("Test: Data Models")
    print("=" * 60)

    try:
        from brain.rag.models import KnowledgeChunk, SearchHit, RiskAssessmentResult

        chunk = KnowledgeChunk(
            chunk_id="test-001",
            doc_id="doc-001",
            category="case",
            subtype="investment_fraud",
            title="Fake Investment Case",
            text="Scam text example",
            source_url="https://example.com",
            source_site="example.com",
            tags=["investment", "fraud"],
        )
        print(f"[PASS] KnowledgeChunk created: {chunk.title}")

        hit = SearchHit(score=0.85, chunk=chunk)
        print(f"[PASS] SearchHit created: score={hit.score}")

        result = RiskAssessmentResult(
            risk_level="high",
            confidence=0.85,
            matched_subtypes=["investment_fraud"],
            matched_tags=["高收益", "投资"],
            recommendations=["Stop transfer", "Verify identity"],
            hits=[],
        )
        print(f"[PASS] RiskAssessmentResult created: {result.risk_level}")

        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_detector():
    """测试风险检测器"""
    print("\n" + "=" * 60)
    print("Test: Risk Detector")
    print("=" * 60)

    try:
        from brain.rag.detector import RiskDetector
        from brain.rag.models import KnowledgeChunk, SearchHit

        detector = RiskDetector(high_threshold=0.32, medium_threshold=0.18)
        print("[PASS] RiskDetector created")

        chunks = [
            KnowledgeChunk(
                chunk_id=f"test-{i:03d}",
                doc_id=f"doc-{i:03d}",
                category=cat,
                subtype=sub,
                title=f"Case {i}",
                text=f"Scam example {i}",
                source_url="https://example.com",
                source_site="example.com",
                tags=tags,
            )
            for i, (cat, sub, tags) in enumerate([
                ("case", "investment_fraud", ["投资诈骗"]),
                ("law", "fraud_law", ["法律"]),
                ("photo_type", "fake_investment_dashboard", ["截图"]),
            ])
        ]

        hits = [
            SearchHit(score=0.35, chunk=chunks[0]),
            SearchHit(score=0.25, chunk=chunks[1]),
            SearchHit(score=0.20, chunk=chunks[2]),
        ]

        result = detector.assess("投资高收益截图", hits)
        print(f"[PASS] Risk assessment done")
        print(f"  - Risk Level: {result.risk_level}")
        print(f"  - Confidence: {result.confidence:.2%}")
        print(f"  - Subtypes: {result.matched_subtypes}")

        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_indexer():
    """测试索引器"""
    print("\n" + "=" * 60)
    print("Test: TF-IDF Indexer")
    print("=" * 60)

    try:
        from brain.rag.indexer import SimilarityIndex
        from brain.rag.models import KnowledgeChunk

        chunks = [
            KnowledgeChunk(
                chunk_id=f"chunk-{i:03d}",
                doc_id=f"doc-{i:03d}",
                category="case",
                subtype="investment_fraud" if i % 2 == 0 else "customer_service_fraud",
                title=f"Case {i}",
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

        index = SimilarityIndex.build(chunks, backend="tfidf")
        print(f"[PASS] Index built: {len(chunks)} chunks")

        hits = index.search("投资理财高收益", top_k=3)
        print(f"[PASS] Search done: {len(hits)} results")

        if hits:
            print(f"  - Best match: {hits[0].chunk.title} (score={hits[0].score:.4f})")

        # Test save/load
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            index.save(tmp_path)
            print("[PASS] Index saved")

            loaded_index = SimilarityIndex.load(tmp_path)
            print(f"[PASS] Index loaded: backend={loaded_index.backend}")

        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """测试配置"""
    print("\n" + "=" * 60)
    print("Test: Config")
    print("=" * 60)

    try:
        from brain.rag.config import load_rag_config_from_dict

        config = load_rag_config_from_dict({
            "root": ".",
            "index": {
                "backend": "hybrid",
                "chunk_size": 200,
            },
        })
        print(f"[PASS] Config loaded")
        print(f"  - Backend: {config.index.backend}")
        print(f"  - Chunk size: {config.index.chunk_size}")

        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline():
    """测试管道"""
    print("\n" + "=" * 60)
    print("Test: Pipeline")
    print("=" * 60)

    try:
        from brain.rag.pipeline import KnowledgePipeline, chunk_text

        # Test chunk_text
        text = "第一句。第二句！第三句？第四句。"
        chunks = chunk_text(text, chunk_size=10, chunk_overlap=2)
        print(f"[PASS] chunk_text: {len(chunks)} chunks")

        # Test pipeline (without actual crawling)
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "root": tmpdir,
                "paths": {
                    "raw_documents": f"{tmpdir}/raw/documents.jsonl",
                    "processed_documents": f"{tmpdir}/processed/documents.jsonl",
                    "chunks": f"{tmpdir}/processed/chunks.jsonl",
                    "index_dir": f"{tmpdir}/index",
                },
                "index": {
                    "backend": "tfidf",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                    "top_k": 5,
                },
            }

            pipeline = KnowledgePipeline(config)
            print("[PASS] KnowledgePipeline created")

            stats = pipeline.get_stats()
            print(f"[PASS] Stats: backend={stats['config']['backend']}")

        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 60)
    print("RAG Module Integration Test")
    print("=" * 60)

    results = [
        ("Data Models", test_models()),
        ("Risk Detector", test_detector()),
        ("TF-IDF Indexer", test_indexer()),
        ("Config", test_config()),
        ("Pipeline", test_pipeline()),
    ]

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")

    print(f"\nTotal: {passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
