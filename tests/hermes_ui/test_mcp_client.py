from __future__ import annotations

import json

import pytest

from hermes_ui import mcp_client
from hermes_ui.mcp_client import (
    normalize_documents,
    normalize_snapshot_status,
    normalize_status,
)


def test_normalize_documents_marks_latest_version() -> None:
    payload = {
        "documents": [
            {
                "document_key": "policy",
                "versions": ["v2026.06.19.001", "v2026.06.20.001"],
                "latest_version_label": "v2026.06.20.001",
            }
        ]
    }

    result = normalize_documents(payload)

    assert result == {
        "documents": [
            {
                "document_key": "policy",
                "latest_version_label": "v2026.06.20.001",
                "versions": [
                    {"label": "v2026.06.19.001", "searchable": False},
                    {"label": "v2026.06.20.001", "searchable": True},
                ],
            }
        ]
    }


def test_normalize_documents_preserves_version_searchability_payload() -> None:
    payload = {
        "documents": [
            {
                "document_key": "policy",
                "versions": [
                    {"label": "2026-06-19-001", "searchable": True},
                    {"label": "2026-06-20-001", "searchable": False},
                ],
                "latest_version_label": "2026-06-20-001",
            }
        ]
    }

    result = normalize_documents(payload)

    assert result == {
        "documents": [
            {
                "document_key": "policy",
                "latest_version_label": "2026-06-20-001",
                "versions": [
                    {"label": "2026-06-19-001", "searchable": True},
                    {"label": "2026-06-20-001", "searchable": False},
                ],
            }
        ]
    }


def test_normalize_documents_handles_empty_payload() -> None:
    assert normalize_documents({}) == {"documents": []}


def test_normalize_status_redacts_adapter_paths_and_coerces_pipeline_values() -> None:
    result = normalize_status(
        adapter={
            "status": "ok",
            "base_url": "http://lightrag-api:9621",
            "source_dir": "C:/secret/source",
        },
        pipeline={
            "busy": 1,
            "docs": "2",
            "snapshot_dir": "C:/secret/snapshot",
            "api_key": "secret",
        },
    )

    assert result == {
        "state": "ok",
        "mcp": {"status": "ok", "base_url": "http://lightrag-api:9621"},
        "pipeline": {"busy": True, "docs": 2},
    }


def test_normalize_snapshot_status_redacts_urls_and_coerces_counts() -> None:
    result = normalize_snapshot_status(
        {
            "state": "blocked",
            "snapshot_base_url": "http://snapshot-api:9621",
            "archived_document_count": "3",
            "target_document_count": "2",
            "can_build": False,
            "current": True,
            "needs_rotation": False,
            "reason": "Rotate or archive snapshot target storage.",
            "latest_versions": {"policy": "2026-06-20-001"},
            "active_snapshot": {
                "snapshot_id": "snapshot-1",
                "base_url": "http://snapshot-api:9621",
                "latest_versions": {"policy": "2026-06-19-001"},
            },
        }
    )

    assert result == {
        "state": "blocked",
        "archived_document_count": 3,
        "target_document_count": 2,
        "can_build": False,
        "current": True,
        "needs_rotation": False,
        "reason": "Rotate or archive snapshot target storage.",
        "latest_versions": {"policy": "2026-06-20-001"},
        "active_snapshot": {
            "snapshot_id": "snapshot-1",
            "latest_versions": {"policy": "2026-06-19-001"},
        },
    }


@pytest.mark.asyncio
async def test_call_tool_parses_first_text_content_as_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStreamableHttpClient:
        async def __aenter__(self):
            return "read-stream", "write-stream", "session-id"

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeContent:
        text = json.dumps({"status": "ok"})

    class FakeResult:
        content = [FakeContent()]

    class FakeSession:
        def __init__(self, read, write):
            self.read = read
            self.write = write
            self.initialized = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def initialize(self):
            self.initialized = True

        async def call_tool(self, tool_name, args):
            assert self.read == "read-stream"
            assert self.write == "write-stream"
            assert self.initialized is True
            assert tool_name == "adapter_status"
            assert args == {"verbose": False}
            return FakeResult()

    monkeypatch.setattr(
        mcp_client,
        "streamablehttp_client",
        lambda mcp_url: FakeStreamableHttpClient(),
    )
    monkeypatch.setattr(mcp_client, "ClientSession", FakeSession)

    result = await mcp_client.call_tool(
        "http://localhost:8000/mcp",
        "adapter_status",
        {"verbose": False},
    )

    assert result == {"status": "ok"}
