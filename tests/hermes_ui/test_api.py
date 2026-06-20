from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from hermes_ui.api import create_app
from hermes_ui.config import HermesUISettings


def _settings(tmp_path: Path) -> HermesUISettings:
    return HermesUISettings(
        hermes_home=tmp_path / "hermes",
        mcp_url="http://mcp.local:8765/mcp",
    )


def _client(tmp_path: Path, **kwargs) -> TestClient:
    app = create_app(settings=_settings(tmp_path), provision_hermes=False, **kwargs)
    return TestClient(app)


def test_status_returns_reader_json(tmp_path):
    async def status_reader(mcp_url):
        return {
            "state": "ok",
            "mcp": {"status": "connected", "base_url": mcp_url},
            "pipeline": {"busy": False, "docs": 2},
        }

    client = _client(tmp_path, status_reader=status_reader)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {
        "state": "ok",
        "mcp": {
            "status": "connected",
            "base_url": "http://mcp.local:8765/mcp",
        },
        "pipeline": {"busy": False, "docs": 2},
    }


def test_documents_returns_reader_json(tmp_path):
    async def document_reader(mcp_url):
        return {
            "documents": [
                {
                    "document_key": "policy",
                    "latest_version_label": "v2026.06.20.001",
                    "versions": [
                        {"label": "v2026.06.20.001", "searchable": True},
                    ],
                },
            ],
            "source": mcp_url,
        }

    client = _client(tmp_path, document_reader=document_reader)

    response = client.get("/api/documents")

    assert response.status_code == 200
    assert response.json() == {
        "documents": [
            {
                "document_key": "policy",
                "latest_version_label": "v2026.06.20.001",
                "versions": [
                    {"label": "v2026.06.20.001", "searchable": True},
                ],
            },
        ],
        "source": "http://mcp.local:8765/mcp",
    }


def test_chat_no_selected_docs_uses_query_latest_all_wording(tmp_path):
    calls = []

    async def hermes_runner(prompt, settings):
        calls.append((prompt, settings))
        return {"state": "ok", "text": "answer"}

    client = _client(tmp_path, hermes_runner=hermes_runner)

    response = client.post("/api/chat", json={"message": "What changed?"})

    assert response.status_code == 200
    assert response.json() == {"state": "ok", "text": "answer"}
    prompt, settings = calls[0]
    assert "lightrag-hermes" in prompt
    assert "query_latest_all" in prompt
    assert "query_latest_documents" not in prompt
    assert "What changed?" in prompt
    assert settings.mcp_url == "http://mcp.local:8765/mcp"


def test_chat_selected_docs_uses_query_latest_documents_and_includes_keys(tmp_path):
    calls = []

    async def hermes_runner(prompt, settings):
        calls.append((prompt, settings))
        return {"state": "ok", "text": "selected answer"}

    client = _client(tmp_path, hermes_runner=hermes_runner)

    response = client.post(
        "/api/chat",
        json={
            "message": "Summarize these",
            "document_keys": ["policy", "guide"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"state": "ok", "text": "selected answer"}
    prompt, _settings = calls[0]
    assert "lightrag-hermes" in prompt
    assert "query_latest_documents" in prompt
    assert "query_latest_all" not in prompt
    assert "policy" in prompt
    assert "guide" in prompt
    assert "Summarize these" in prompt


def test_chat_rejects_empty_message(tmp_path):
    client = _client(tmp_path)

    response = client.post("/api/chat", json={"message": ""})

    assert response.status_code == 422


def test_ingest_rejects_invalid_version_label(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/api/ingest",
        json={
            "document_key": "policy",
            "version_label": "2026-06-20",
            "title": "Policy",
            "text": "Body",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    [
        "document_key",
        "title",
        "text",
    ],
)
def test_ingest_rejects_empty_required_text_fields(tmp_path, field):
    client = _client(tmp_path)
    payload = {
        "document_key": "policy",
        "version_label": "v2026.06.20.001",
        "title": "Policy",
        "text": "Body",
    }
    payload[field] = ""

    response = client.post("/api/ingest", json=payload)

    assert response.status_code == 422


def test_ingest_calls_runner_with_ingest_prompt(tmp_path):
    calls = []

    async def hermes_runner(prompt, settings):
        calls.append((prompt, settings))
        return {"state": "ok", "text": "ingested"}

    client = _client(tmp_path, hermes_runner=hermes_runner)

    response = client.post(
        "/api/ingest",
        json={
            "document_key": "policy",
            "version_label": "v2026.06.20.001",
            "title": "Policy",
            "text": "Body",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"state": "ok", "text": "ingested"}
    prompt, _settings = calls[0]
    assert "ingest_text_version" in prompt
    assert "policy" in prompt
    assert "v2026.06.20.001" in prompt
    assert "Policy" in prompt
    assert "Body" in prompt


def test_snapshots_build_calls_runner_with_snapshot_prompt(tmp_path):
    calls = []

    async def hermes_runner(prompt, settings):
        calls.append((prompt, settings))
        return {"state": "ok", "text": "built"}

    client = _client(tmp_path, hermes_runner=hermes_runner)

    response = client.post(
        "/api/snapshots/build",
        json={"snapshot_id": "snapshot-2026-06-20"},
    )

    assert response.status_code == 200
    assert response.json() == {"state": "ok", "text": "built"}
    prompt, _settings = calls[0]
    assert "build_latest_snapshot" in prompt
    assert "snapshot-2026-06-20" in prompt


def test_snapshots_build_rejects_empty_snapshot_id(tmp_path):
    client = _client(tmp_path)

    response = client.post("/api/snapshots/build", json={"snapshot_id": ""})

    assert response.status_code == 422


def test_provision_hermes_false_avoids_openai_api_key_requirement(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = create_app(settings=_settings(tmp_path), provision_hermes=False)

    assert app is not None
