import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

import yaml

from src.brain.rag import external_case_sync


def _make_temp_root() -> Path:
    base_dir = Path(__file__).resolve().parents[1] / ".manual_checks"
    base_dir.mkdir(parents=True, exist_ok=True)
    root = base_dir / f"external-case-sync-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def _write_test_config(tmp_path: Path, json_path: Path) -> Path:
    config_path = tmp_path / "external_sources.yaml"
    state_path = tmp_path / "external_sync_state.json"
    payload = {
        "enabled": True,
        "interval_seconds": 300,
        "min_content_length": 10,
        "state_file": str(state_path),
        "sources": [
            {
                "name": "unit_json_source",
                "enabled": True,
                "type": "json_file",
                "path": str(json_path),
                "records_path": "items",
                "title_field": "title",
                "content_field": "content",
                "category": "case",
                "subtype": "internet_fraud_case",
                "tags": ["unit-test"],
            }
        ],
    }
    config_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return config_path


def _write_local_directory_config(tmp_path: Path, directory_path: Path) -> Path:
    config_path = tmp_path / "external_sources_local_directory.yaml"
    state_path = tmp_path / "external_sync_local_directory_state.json"
    payload = {
        "enabled": True,
        "interval_seconds": 300,
        "min_content_length": 10,
        "state_file": str(state_path),
        "sources": [
            {
                "name": "unit_local_case_directory",
                "enabled": True,
                "type": "local_case_directory",
                "path": str(directory_path),
                "category": "case",
                "tags": ["unit-test", "local-case"],
            }
        ],
    }
    config_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return config_path


def test_external_case_sync_json_file_dedup(monkeypatch):
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_CONFIG", raising=False)

    root = _make_temp_root()
    try:
        json_path = root / "cases.json"
        json_payload = {
            "items": [
                {
                    "title": "Case A",
                    "content": "fraud scenario details " * 12,
                }
            ]
        }
        json_path.write_text(json.dumps(json_payload, ensure_ascii=False), encoding="utf-8")
        config_path = _write_test_config(root, json_path)

        ingest_calls = []

        async def _fake_ingest(docs):
            ingest_calls.append([doc.doc_id for doc in docs])
            return {
                "status": "ok",
                "added_chunks": len(docs),
                "skipped_chunks": 0,
                "total_chunks": len(docs),
            }

        monkeypatch.setattr(external_case_sync, "ingest_documents_async", _fake_ingest)

        first = asyncio.run(external_case_sync.sync_external_case_sources(config_path))
        second = asyncio.run(external_case_sync.sync_external_case_sources(config_path))

        assert first["status"] == "ok"
        assert first["total_new_documents"] == 1
        assert second["status"] == "ok"
        assert second["total_new_documents"] == 0
        assert len(ingest_calls) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_external_case_sync_status_contains_latest_state(monkeypatch):
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_CONFIG", raising=False)

    root = _make_temp_root()
    try:
        json_path = root / "cases_status.json"
        json_payload = {
            "items": [
                {
                    "title": "Case B",
                    "content": "risk warning narrative " * 12,
                }
            ]
        }
        json_path.write_text(json.dumps(json_payload, ensure_ascii=False), encoding="utf-8")
        config_path = _write_test_config(root, json_path)

        async def _fake_ingest(docs):
            return {
                "status": "ok",
                "added_chunks": len(docs),
                "skipped_chunks": 0,
                "total_chunks": len(docs),
            }

        monkeypatch.setattr(external_case_sync, "ingest_documents_async", _fake_ingest)
        asyncio.run(external_case_sync.sync_external_case_sources(config_path))

        status_payload = external_case_sync.get_external_case_sync_status(config_path)

        assert status_payload["status"] == "ok"
        assert status_payload["enabled"] is True
        assert status_payload["seen_fingerprint_count"] == 1
        assert len(status_payload["sources"]) == 1
        assert status_payload["sources"][0]["name"] == "unit_json_source"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_external_case_sync_local_case_directory_import(monkeypatch):
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_CONFIG", raising=False)

    root = _make_temp_root()
    try:
        case_dir = root / "local_cases"
        case_dir.mkdir()
        sample_file = case_dir / "sogou_cases.json"
        sample_file.write_text(
            json.dumps(
                {
                    "website_name": "Sogou Cases",
                    "source_url": "https://weixin.sogou.com/weixin?query=%E5%8F%8D%E8%AF%88&type=2",
                    "source_data": [
                        {
                            "title": "Case From Local Directory",
                            "content": "fraud warning narrative " * 20,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        config_path = _write_local_directory_config(root, case_dir)

        captured = []

        async def _fake_ingest(docs):
            captured.extend(docs)
            return {
                "status": "ok",
                "added_chunks": len(docs),
                "skipped_chunks": 0,
                "total_chunks": len(docs),
            }

        monkeypatch.setattr(external_case_sync, "ingest_documents_async", _fake_ingest)

        result = asyncio.run(external_case_sync.sync_external_case_sources(config_path))

        assert result["status"] == "ok"
        assert result["total_new_documents"] == 1
        assert len(captured) == 1
        assert captured[0].metadata["source_file"] == "sogou_cases.json"
        assert captured[0].metadata["source_directory"] == "local_cases"
        assert captured[0].canonical_url.startswith("local-case://")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_external_case_sync_batches_ingest_once_for_multiple_sources(monkeypatch):
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_ENABLED", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("EXTERNAL_CASE_SYNC_CONFIG", raising=False)

    root = _make_temp_root()
    try:
        json_path_a = root / "cases_a.json"
        json_path_b = root / "cases_b.json"
        json_path_a.write_text(
            json.dumps({"items": [{"title": "Case A", "content": "fraud narrative alpha " * 12}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        json_path_b.write_text(
            json.dumps({"items": [{"title": "Case B", "content": "fraud narrative beta " * 12}]}, ensure_ascii=False),
            encoding="utf-8",
        )

        config_path = root / "external_sources_batch.yaml"
        state_path = root / "external_sync_batch_state.json"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "enabled": True,
                    "interval_seconds": 300,
                    "min_content_length": 10,
                    "state_file": str(state_path),
                    "sources": [
                        {
                            "name": "unit_json_source_a",
                            "enabled": True,
                            "type": "json_file",
                            "path": str(json_path_a),
                            "records_path": "items",
                            "title_field": "title",
                            "content_field": "content",
                            "category": "case",
                            "tags": ["unit-test"],
                        },
                        {
                            "name": "unit_json_source_b",
                            "enabled": True,
                            "type": "json_file",
                            "path": str(json_path_b),
                            "records_path": "items",
                            "title_field": "title",
                            "content_field": "content",
                            "category": "case",
                            "tags": ["unit-test"],
                        },
                    ],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        ingest_calls = []

        async def _fake_ingest(docs):
            ingest_calls.append([doc.doc_id for doc in docs])
            return {
                "status": "ok",
                "added_chunks": len(docs),
                "skipped_chunks": 0,
                "total_chunks": len(docs),
            }

        monkeypatch.setattr(external_case_sync, "ingest_documents_async", _fake_ingest)

        result = asyncio.run(external_case_sync.sync_external_case_sources(config_path))

        assert result["status"] == "ok"
        assert result["total_new_documents"] == 2
        assert len(ingest_calls) == 1
        assert len(ingest_calls[0]) == 2
        assert all(source["ingest"]["status"] == "ok" for source in result["sources"])
        assert all(source["ingest"]["added_chunks"] == 1 for source in result["sources"])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_default_external_sync_config_uses_eight_remote_sources():
    config_path = Path(__file__).resolve().parents[1] / "config" / "external_case_sources.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert payload["enabled"] is True
    assert payload["interval_seconds"] == 300

    sources = payload["sources"]
    assert len(sources) == 8
    assert all(source["enabled"] is True for source in sources)
    assert all(str(source.get("type") or "url") == "url" for source in sources)
    assert all("path" not in source for source in sources)
    assert {source["name"] for source in sources} == {
        "baidu_anti_fraud_classroom",
        "sohu_anti_fraud_cases",
        "supreme_procuratorate_telecom_fraud",
        "guangxi_anti_fraud_publicity",
        "sogou_wechat_anti_fraud_search",
        "npc_anti_telecom_fraud_law",
        "supreme_court_telecom_fraud_cases",
        "supreme_court_livelihood_fraud_cases",
    }
