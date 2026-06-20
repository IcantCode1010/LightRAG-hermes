from __future__ import annotations

import base64
import binascii
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from lightrag_mcp.client import LightRAGClient
from lightrag_mcp.config import MCPConfig
from lightrag_mcp.snapshots import (
    ActiveSnapshot,
    LatestSnapshotBuilder,
    SourceRegistry,
    read_active_snapshot,
)
from lightrag_mcp.versioning import validate_document_key


config = MCPConfig.from_env()
mcp = FastMCP("lightrag-hermes", host=config.host, port=config.port)


def build_adapter_status(
    *, base_url: str, source_dir: Path, snapshot_dir: Path
) -> dict[str, str]:
    return {
        "status": "ok",
        "base_url": base_url,
        "source_dir": str(source_dir),
        "snapshot_dir": str(snapshot_dir),
    }


def build_list_documents(registry: SourceRegistry) -> dict[str, list[dict[str, object]]]:
    sources = registry.list_sources()
    latest = registry.latest_sources()
    document_keys = sorted({source.document_key for source in sources})
    documents: list[dict[str, object]] = []
    for key in document_keys:
        versions = sorted(
            source.version_label for source in sources if source.document_key == key
        )
        documents.append(
            {
                "document_key": key,
                "latest_version_label": latest[key].version_label,
                "versions": versions,
            }
        )
    return {"documents": documents}


def build_ingest_text_version(
    registry: SourceRegistry,
    *,
    document_key: str,
    version_label: str,
    title: str,
    text: str,
) -> dict[str, object]:
    source_path = registry.write_text_version(document_key, version_label, title, text)
    return {
        "status": "stored",
        "document_key": document_key,
        "version_label": version_label,
        "source_name": source_path.name,
        "source_path": str(source_path),
        "indexed": False,
        "message": (
            "Version archived. It is not searchable until a latest-version "
            "snapshot is built and activated."
        ),
    }


def build_ingest_file_version(
    registry: SourceRegistry,
    *,
    document_key: str,
    version_label: str,
    filename: str,
    content_base64: str,
) -> dict[str, object]:
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("content_base64 must be valid base64") from error

    source_path = registry.write_file_version(
        document_key,
        version_label,
        filename,
        content,
    )
    return {
        "status": "stored",
        "document_key": document_key,
        "version_label": version_label,
        "source_name": source_path.name,
        "source_path": str(source_path),
        "indexed": False,
        "message": (
            "File version archived. It is not searchable until a latest-version "
            "snapshot is built and activated."
        ),
    }


def build_selected_document_query(
    question: str,
    *,
    document_keys: list[str],
    registry: SourceRegistry,
) -> str:
    latest = registry.latest_sources()
    selected: list[str] = []
    for raw_key in document_keys:
        key = validate_document_key(raw_key)
        source = latest.get(key)
        if source is None:
            raise ValueError(f"Unknown document_key: {key}")
        selected.append(f"{source.document_key}@{source.version_label}")

    selected_sources = ", ".join(selected)
    return (
        "Answer the question using only the latest active index content for "
        f"these document versions: {selected_sources}.\n\n"
        f"Question: {question}"
    )


async def query_latest_all_with_client(
    question: str,
    *,
    mode: str,
    active_snapshot_file: Path,
    api_key: str,
    http=None,
) -> dict[str, object]:
    active = read_active_snapshot(active_snapshot_file)
    if active is None:
        raise RuntimeError(
            "No active latest-version snapshot is configured. "
            "Build and activate a latest-only snapshot before querying."
        )
    return await LightRAGClient(active.base_url, api_key, http=http).query(
        question,
        mode=mode,
    )


async def build_latest_snapshot_with_client(
    *,
    registry: SourceRegistry,
    active_snapshot_file: Path,
    snapshot_id: str,
    snapshot_base_url: str,
    client,
) -> dict[str, object]:
    builder = LatestSnapshotBuilder(registry, active_snapshot_file)
    result = await builder.build_and_activate(
        snapshot_id=snapshot_id,
        base_url=snapshot_base_url,
        client=client,
    )
    return {
        "status": "active",
        "snapshot_id": result.snapshot.snapshot_id,
        "base_url": result.snapshot.base_url,
        "latest_versions": result.snapshot.latest_versions,
        "indexed_sources": result.indexed_sources,
        "insert_results": result.insert_results,
    }


async def build_snapshot_status_with_client(
    *,
    registry: SourceRegistry,
    active_snapshot_file: Path,
    snapshot_base_url: str,
    client,
) -> dict[str, object]:
    latest = registry.latest_sources()
    target_documents = await client.documents()
    target_count = len(target_documents.get("documents") or [])
    can_build = target_count == 0
    active = read_active_snapshot(active_snapshot_file)
    return {
        "state": "ready" if can_build else "blocked",
        "snapshot_base_url": snapshot_base_url,
        "archived_document_count": len(latest),
        "latest_versions": {
            key: source.version_label for key, source in sorted(latest.items())
        },
        "active_snapshot": _snapshot_payload(active),
        "target_document_count": target_count,
        "can_build": can_build,
        "reason": (
            "Snapshot target is empty."
            if can_build
            else "Rotate or archive snapshot target storage before building."
        ),
    }


def _snapshot_payload(snapshot: ActiveSnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "snapshot_id": snapshot.snapshot_id,
        "base_url": snapshot.base_url,
        "latest_versions": snapshot.latest_versions,
    }


@mcp.tool()
def adapter_status() -> dict[str, str]:
    """Return adapter configuration that is safe to expose to Hermes."""
    return build_adapter_status(
        base_url=config.base_url,
        source_dir=config.source_dir,
        snapshot_dir=config.snapshot_dir,
    )


@mcp.tool()
def list_documents() -> dict[str, list[dict[str, object]]]:
    """List known document keys and their stored version labels."""
    return build_list_documents(SourceRegistry(config.source_dir))


@mcp.tool()
def ingest_text_version(
    document_key: str,
    version_label: str,
    title: str,
    text: str,
) -> dict[str, object]:
    """Archive a new document version without deleting or indexing old versions."""
    return build_ingest_text_version(
        SourceRegistry(config.source_dir),
        document_key=document_key,
        version_label=version_label,
        title=title,
        text=text,
    )


@mcp.tool()
def ingest_file_version(
    document_key: str,
    version_label: str,
    filename: str,
    content_base64: str,
) -> dict[str, object]:
    """Archive a new file version without deleting or indexing old versions."""
    return build_ingest_file_version(
        SourceRegistry(config.source_dir),
        document_key=document_key,
        version_label=version_label,
        filename=filename,
        content_base64=content_base64,
    )


@mcp.tool()
async def query_latest_all(question: str, mode: str | None = None) -> dict[str, object]:
    """Query only the active latest-version LightRAG snapshot."""
    return await query_latest_all_with_client(
        question,
        mode=mode or config.default_query_mode,
        active_snapshot_file=config.active_snapshot_file,
        api_key=config.api_key,
    )


@mcp.tool()
async def query_latest_documents(
    question: str,
    document_keys: list[str],
    mode: str | None = None,
) -> dict[str, object]:
    """Query the active latest-version snapshot with selected document guidance."""
    selected_query = build_selected_document_query(
        question,
        document_keys=document_keys,
        registry=SourceRegistry(config.source_dir),
    )
    return await query_latest_all_with_client(
        selected_query,
        mode=mode or config.default_query_mode,
        active_snapshot_file=config.active_snapshot_file,
        api_key=config.api_key,
    )


@mcp.tool()
async def build_latest_snapshot(
    snapshot_id: str,
    snapshot_base_url: str | None = None,
) -> dict[str, object]:
    """Index latest archived versions into a clean snapshot endpoint and activate it."""
    target_base_url = snapshot_base_url or config.snapshot_base_url
    return await build_latest_snapshot_with_client(
        registry=SourceRegistry(config.source_dir),
        active_snapshot_file=config.active_snapshot_file,
        snapshot_id=snapshot_id,
        snapshot_base_url=target_base_url,
        client=LightRAGClient(target_base_url, config.api_key),
    )


@mcp.tool()
async def snapshot_status() -> dict[str, object]:
    """Report whether the latest-only snapshot target is ready to build."""
    return await build_snapshot_status_with_client(
        registry=SourceRegistry(config.source_dir),
        active_snapshot_file=config.active_snapshot_file,
        snapshot_base_url=config.snapshot_base_url,
        client=LightRAGClient(config.snapshot_base_url, config.api_key),
    )


@mcp.tool()
async def get_pipeline_status() -> dict[str, object]:
    """Return pipeline status from the active LightRAG endpoint."""
    active = read_active_snapshot(config.active_snapshot_file)
    base_url = active.base_url if active else config.base_url
    return await LightRAGClient(base_url, config.api_key).pipeline_status()


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
