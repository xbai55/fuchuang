import asyncio
from datetime import datetime

from src.evolution.case_ingestor import CaseIngestor, FraudCase


def _build_case(case_id: str) -> FraudCase:
    return FraudCase(
        case_id=case_id,
        title="自动更新测试案例",
        content="这是一个用于验证自动知识库更新流程的测试文本。",
        case_type="phishing",
        source="test",
        timestamp=datetime.now(),
    )


def test_case_ingestor_auto_initializes_knowledge_service(monkeypatch):
    created = {"count": 0}
    ingested_calls = []

    class _FakeKnowledgeService:
        async def ingest_case(self, case_id, title, content, case_type, source):
            ingested_calls.append(
                {
                    "case_id": case_id,
                    "title": title,
                    "content": content,
                    "case_type": case_type,
                    "source": source,
                }
            )
            return True

    def _fake_create_service(self):
        created["count"] += 1
        return _FakeKnowledgeService()

    monkeypatch.setattr(CaseIngestor, "_create_knowledge_service", _fake_create_service)

    ingestor = CaseIngestor()
    first_result = asyncio.run(ingestor.ingest(_build_case("case_1")))
    second_result = asyncio.run(ingestor.ingest(_build_case("case_2")))

    assert first_result["success"] is True
    assert second_result["success"] is True
    assert created["count"] == 1
    assert len(ingested_calls) == 2
    assert ingested_calls[0]["case_id"] == "case_1"
    assert ingested_calls[1]["case_id"] == "case_2"


def test_case_ingestor_reports_error_when_service_unavailable(monkeypatch):
    def _fake_create_service(self):
        self._service_init_error = "init failed"
        return None

    monkeypatch.setattr(CaseIngestor, "_create_knowledge_service", _fake_create_service)

    ingestor = CaseIngestor()
    result = asyncio.run(ingestor.ingest(_build_case("case_fail")))

    assert result["success"] is False
    assert "Knowledge service unavailable" in result["error"]
    assert "init failed" in result["error"]
