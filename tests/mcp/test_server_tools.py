from pathlib import Path

import httpx
import pytest

from lightrag_mcp.server import (
    build_adapter_status,
    build_ingest_text_version,
    build_list_documents,
    build_selected_document_query,
    query_latest_all_with_client,
)
from lightrag_mcp.snapshots import ActiveSnapshot, SourceRegistry, write_active_snapshot


def test_build_adapter_status_exposes_safe_paths(tmp_path):
    result = build_adapter_status(
        base_url="http://lightrag-api:9621",
        source_dir=tmp_path / "sources",
        snapshot_dir=tmp_path / "snapshots",
    )

    assert result["status"] == "ok"
    assert result["base_url"] == "http://lightrag-api:9621"


def test_build_list_documents_marks_latest_versions(tmp_path: Path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "A", "one")
    registry.write_text_version("handbook", "2026-07-01-final", "A", "two")

    result = build_list_documents(registry)

    assert result["documents"][0]["document_key"] == "handbook"
    assert result["documents"][0]["latest_version_label"] == "2026-07-01-final"
    assert result["documents"][0]["versions"] == [
        "2026-06-19-review",
        "2026-07-01-final",
    ]


def test_build_ingest_text_version_archives_without_indexing(tmp_path: Path):
    registry = SourceRegistry(tmp_path)

    result = build_ingest_text_version(
        registry,
        document_key="handbook",
        version_label="2026-07-01-final",
        title="Handbook",
        text="New policy",
    )

    assert result["document_key"] == "handbook"
    assert result["version_label"] == "2026-07-01-final"
    assert result["indexed"] is False
    assert (tmp_path / "handbook@2026-07-01-final.md").exists()


def test_build_selected_document_query_uses_latest_versions(tmp_path: Path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "A", "one")
    registry.write_text_version("handbook", "2026-07-01-final", "A", "two")

    query = build_selected_document_query(
        "What changed?",
        document_keys=["handbook"],
        registry=registry,
    )

    assert "What changed?" in query
    assert "handbook@2026-07-01-final" in query
    assert "2026-06-19-review" not in query


def test_build_selected_document_query_rejects_unknown_document(tmp_path: Path):
    registry = SourceRegistry(tmp_path)

    with pytest.raises(ValueError, match="Unknown document_key"):
        build_selected_document_query(
            "What changed?",
            document_keys=["missing"],
            registry=registry,
        )


@pytest.mark.asyncio
async def test_query_latest_all_requires_active_snapshot(tmp_path: Path):
    with pytest.raises(RuntimeError, match="No active latest-version snapshot"):
        await query_latest_all_with_client(
            "What changed?",
            mode="mix",
            active_snapshot_file=tmp_path / "missing.json",
            api_key="",
        )


@pytest.mark.asyncio
async def test_query_latest_all_uses_active_snapshot_base_url(tmp_path: Path):
    seen_url = ""

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = str(request.url)
        return httpx.Response(200, json={"response": "answer"})

    active_path = tmp_path / "active.json"
    write_active_snapshot(
        active_path,
        ActiveSnapshot(
            snapshot_id="snapshot-1",
            base_url="http://snapshot-api:9621",
            latest_versions={"handbook": "2026-07-01-final"},
        ),
    )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        result = await query_latest_all_with_client(
            "What changed?",
            mode="mix",
            active_snapshot_file=active_path,
            api_key="",
            http=http,
        )

    assert seen_url == "http://snapshot-api:9621/query"
    assert result["response"] == "answer"
