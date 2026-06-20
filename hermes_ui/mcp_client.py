from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def normalize_documents(payload: dict[str, Any]) -> dict[str, Any]:
    documents = []
    raw_documents = _value(payload, "documents", [])
    if not isinstance(raw_documents, list):
        return {"documents": documents}

    for document in raw_documents:
        if not isinstance(document, dict):
            continue

        latest = document.get("latest_version_label")
        raw_versions = document.get("versions", [])
        if not isinstance(raw_versions, list):
            raw_versions = []

        documents.append(
            {
                "document_key": document.get("document_key"),
                "latest_version_label": latest,
                "versions": [
                    {"label": version, "searchable": version == latest}
                    for version in raw_versions
                ],
            }
        )

    return {"documents": documents}


def normalize_status(adapter: dict[str, Any], pipeline: dict[str, Any]) -> dict[str, Any]:
    docs = _value(pipeline, "docs", 0)
    if docs is None:
        docs = 0

    return {
        "state": "ok",
        "mcp": {
            "status": _value(adapter, "status"),
            "base_url": _value(adapter, "base_url"),
        },
        "pipeline": {
            "busy": bool(_value(pipeline, "busy", False)),
            "docs": int(docs),
        },
    }


def normalize_snapshot_status(payload: dict[str, Any]) -> dict[str, Any]:
    active_snapshot = _value(payload, "active_snapshot")
    normalized_active = None
    if isinstance(active_snapshot, dict):
        normalized_active = {
            "snapshot_id": active_snapshot.get("snapshot_id"),
            "latest_versions": dict(active_snapshot.get("latest_versions") or {}),
        }

    return {
        "state": str(_value(payload, "state", "unknown")),
        "archived_document_count": int(_value(payload, "archived_document_count", 0)),
        "target_document_count": int(_value(payload, "target_document_count", 0)),
        "can_build": bool(_value(payload, "can_build", False)),
        "reason": str(_value(payload, "reason", "")),
        "latest_versions": dict(_value(payload, "latest_versions", {}) or {}),
        "active_snapshot": normalized_active,
    }


async def call_tool(
    mcp_url: str,
    tool_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args or {})

    content = getattr(result, "content", None) or []
    if not content:
        raise RuntimeError(f"MCP tool {tool_name!r} returned no content")

    text = getattr(content[0], "text", None)
    if not text:
        raise RuntimeError(f"MCP tool {tool_name!r} returned empty text content")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"MCP tool {tool_name!r} returned invalid JSON: {exc.msg}"
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(f"MCP tool {tool_name!r} returned non-object JSON")

    return parsed


async def get_documents(mcp_url: str) -> dict[str, Any]:
    return normalize_documents(await call_tool(mcp_url, "list_documents"))


async def get_status(mcp_url: str) -> dict[str, Any]:
    adapter = await call_tool(mcp_url, "adapter_status")
    pipeline = await call_tool(mcp_url, "get_pipeline_status")
    return normalize_status(adapter, pipeline)


async def get_snapshot_status(mcp_url: str) -> dict[str, Any]:
    return normalize_snapshot_status(await call_tool(mcp_url, "snapshot_status"))
