import json

import httpx
import pytest

from lightrag_mcp.client import LightRAGClient


@pytest.mark.asyncio
async def test_client_sends_api_key_header():
    seen_headers = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = LightRAGClient("http://lightrag-api:9621", "secret", http=http)
        result = await client.health()

    assert result == {"status": "ok"}
    assert seen_headers["x-api-key"] == "secret"


@pytest.mark.asyncio
async def test_query_posts_expected_payload():
    seen_json = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_json.update(json.loads(request.content))
        return httpx.Response(200, json={"response": "answer", "references": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = LightRAGClient("http://lightrag-api:9621", "", http=http)
        result = await client.query("What changed?", mode="mix")

    assert seen_json["query"] == "What changed?"
    assert seen_json["mode"] == "mix"
    assert result["response"] == "answer"


@pytest.mark.asyncio
async def test_insert_text_posts_file_source():
    seen_json = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_json.update(json.loads(request.content))
        return httpx.Response(200, json={"status": "success", "track_id": "insert-1"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = LightRAGClient("http://lightrag-api:9621", "", http=http)
        result = await client.insert_text(
            "Version body",
            file_source="handbook@2026-07-01-final.md",
        )

    assert seen_json["text"] == "Version body"
    assert seen_json["file_source"] == "handbook@2026-07-01-final.md"
    assert result["track_id"] == "insert-1"
