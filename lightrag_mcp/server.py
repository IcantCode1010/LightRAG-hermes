from __future__ import annotations

import base64
import binascii
import re
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
from lightrag_mcp.versioning import parse_source_name


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


def build_list_documents(
    registry: SourceRegistry,
    *,
    active_snapshot: ActiveSnapshot | None = None,
) -> dict[str, list[dict[str, object]]]:
    sources = registry.list_sources()
    latest = registry.latest_sources()
    document_keys = sorted({source.document_key for source in sources})
    documents: list[dict[str, object]] = []
    for key in document_keys:
        key_sources = sorted(
            (source for source in sources if source.document_key == key),
            key=lambda source: source.version_label,
        )
        if active_snapshot is None:
            versions: list[object] = [source.version_label for source in key_sources]
        else:
            active_version = active_snapshot.latest_versions.get(key)
            versions = [
                {
                    "label": source.version_label,
                    "searchable": active_version == source.version_label,
                }
                for source in key_sources
            ]
        documents.append(
            {
                "document_key": key,
                "latest_version_label": latest[key].version_label,
                "versions": versions,
            }
        )
    return {"documents": documents}


def _source_payload(
    source,
    *,
    active_snapshot: ActiveSnapshot | None,
) -> dict[str, object]:
    active_snapshot_id = active_snapshot.snapshot_id if active_snapshot else None
    searchable = (
        active_snapshot is not None
        and active_snapshot.latest_versions.get(source.document_key)
        == source.version_label
    )
    return {
        "document_key": source.document_key,
        "latest_version_label": source.version_label,
        "source_name": source.source_name,
        "searchable": searchable,
        "active_snapshot_id": active_snapshot_id,
    }


def _paginate(items: list[dict[str, object]], *, limit: int, offset: int):
    safe_limit = max(1, min(int(limit), 100))
    safe_offset = max(0, int(offset))
    return safe_limit, safe_offset, items[safe_offset : safe_offset + safe_limit]


def _query_terms(query: str) -> list[str]:
    return [term for term in re.split(r"[^a-z0-9]+", query.lower()) if term]


def build_search_documents(
    registry: SourceRegistry,
    query: str,
    *,
    active_snapshot: ActiveSnapshot | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, object]:
    latest = registry.latest_sources()
    terms = _query_terms(query)
    matches = []
    for key in sorted(latest):
        source = latest[key]
        haystack = f"{source.document_key} {source.source_name}".lower()
        if not terms or all(term in haystack for term in terms):
            matches.append(_source_payload(source, active_snapshot=active_snapshot))

    safe_limit, safe_offset, page = _paginate(matches, limit=limit, offset=offset)
    return {
        "query": query,
        "total": len(matches),
        "limit": safe_limit,
        "offset": safe_offset,
        "documents": page,
    }


def build_document_state(
    registry: SourceRegistry,
    document_key: str,
    *,
    active_snapshot: ActiveSnapshot | None = None,
) -> dict[str, object]:
    key = validate_document_key(document_key)
    sources = [
        source for source in registry.list_sources() if source.document_key == key
    ]
    if not sources:
        raise ValueError(f"Unknown document_key: {key}")

    sources = sorted(sources, key=lambda source: source.version_label)
    latest = sources[-1]
    active_version = (
        active_snapshot.latest_versions.get(key) if active_snapshot is not None else None
    )
    return {
        "document_key": key,
        "latest_version_label": latest.version_label,
        "latest_searchable": active_version == latest.version_label,
        "active_snapshot_id": active_snapshot.snapshot_id if active_snapshot else None,
        "active_snapshot_version_label": active_version,
        "versions": [
            {
                "label": source.version_label,
                "source_name": source.source_name,
                "searchable": active_version == source.version_label,
            }
            for source in sources
        ],
    }


def build_list_unsearchable_latest(
    registry: SourceRegistry,
    *,
    active_snapshot: ActiveSnapshot | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, object]:
    latest = registry.latest_sources()
    missing = []
    for key in sorted(latest):
        source = latest[key]
        if (
            active_snapshot is None
            or active_snapshot.latest_versions.get(key) != source.version_label
        ):
            missing.append(_source_payload(source, active_snapshot=active_snapshot))

    safe_limit, safe_offset, page = _paginate(missing, limit=limit, offset=offset)
    return {
        "total": len(missing),
        "limit": safe_limit,
        "offset": safe_offset,
        "documents": page,
    }


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
        "failed_sources": result.failed_sources,
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
    latest_versions = {
        key: source.version_label for key, source in sorted(latest.items())
    }
    target_documents = await client.documents()
    target_document_records = target_documents.get("documents") or []
    target_count = len(target_document_records)
    active = read_active_snapshot(active_snapshot_file)
    active_versions = active.latest_versions if active is not None else {}
    processed_versions = _processed_latest_versions(target_document_records)
    can_build = target_count == 0
    active_matches_latest = active is not None and active_versions == latest_versions
    processed_matches_latest = processed_versions == latest_versions
    active_matches_processed = active is not None and active_versions == processed_versions
    current = target_count > 0 and active_matches_latest and processed_matches_latest
    degraded = (
        target_count > 0
        and not current
        and bool(processed_versions)
        and active_matches_processed
    )
    needs_rotation = target_count > 0 and not current
    if current:
        state = "current"
        reason = (
            "Active snapshot is current. Rotate snapshot target storage only before "
            "building the next replacement snapshot."
        )
    elif degraded:
        state = "degraded"
        missing_count = max(len(latest_versions) - len(processed_versions), 0)
        reason = (
            f"Active snapshot is searchable for {len(processed_versions)} latest "
            f"document(s); {missing_count} latest document(s) failed or produced "
            "no chunks."
        )
    elif can_build:
        state = "ready"
        reason = "Snapshot target is empty."
    elif active_matches_latest and not processed_matches_latest:
        state = "blocked"
        reason = (
            "Active snapshot metadata matches latest versions, but the snapshot "
            "target is missing processed chunks for one or more latest documents. "
            "Rotate snapshot target storage and rebuild."
        )
    else:
        state = "blocked"
        reason = "Rotate or archive snapshot target storage before building."
    return {
        "state": state,
        "snapshot_base_url": snapshot_base_url,
        "archived_document_count": len(latest),
        "latest_versions": latest_versions,
        "active_snapshot": _snapshot_payload(active),
        "target_document_count": target_count,
        "can_build": can_build,
        "current": current,
        "needs_rotation": needs_rotation,
        "reason": reason,
    }


def _processed_latest_versions(documents: list[object]) -> dict[str, str]:
    processed: dict[str, str] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        if str(document.get("status") or "") != "processed":
            continue
        chunks_count = document.get("chunks_count")
        if not isinstance(chunks_count, int) or chunks_count < 1:
            continue
        try:
            source = parse_source_name(str(document.get("file_path") or ""))
        except ValueError:
            continue
        processed[source.document_key] = source.version_label
    return processed


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
    return build_list_documents(
        SourceRegistry(config.source_dir),
        active_snapshot=read_active_snapshot(config.active_snapshot_file),
    )


@mcp.tool()
def search_documents(
    query: str,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, object]:
    """Search registered latest document metadata without reading document contents."""
    return build_search_documents(
        SourceRegistry(config.source_dir),
        query,
        active_snapshot=read_active_snapshot(config.active_snapshot_file),
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def get_document_state(document_key: str) -> dict[str, object]:
    """Return versions and active-snapshot searchability for one document key."""
    return build_document_state(
        SourceRegistry(config.source_dir),
        document_key,
        active_snapshot=read_active_snapshot(config.active_snapshot_file),
    )


@mcp.tool()
def list_unsearchable_latest(limit: int = 25, offset: int = 0) -> dict[str, object]:
    """List latest registered document versions missing from the active snapshot."""
    return build_list_unsearchable_latest(
        SourceRegistry(config.source_dir),
        active_snapshot=read_active_snapshot(config.active_snapshot_file),
        limit=limit,
        offset=offset,
    )


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
