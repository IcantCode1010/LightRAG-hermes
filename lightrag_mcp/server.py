from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from lightrag_mcp.client import LightRAGClient
from lightrag_mcp.config import MCPConfig
from lightrag_mcp.snapshots import SourceRegistry, read_active_snapshot
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
async def get_pipeline_status() -> dict[str, object]:
    """Return pipeline status from the active LightRAG endpoint."""
    active = read_active_snapshot(config.active_snapshot_file)
    base_url = active.base_url if active else config.base_url
    return await LightRAGClient(base_url, config.api_key).pipeline_status()


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
