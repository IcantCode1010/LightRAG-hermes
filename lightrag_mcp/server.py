from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from lightrag_mcp.client import LightRAGClient
from lightrag_mcp.config import MCPConfig
from lightrag_mcp.snapshots import SourceRegistry, read_active_snapshot


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
async def get_pipeline_status() -> dict[str, object]:
    """Return pipeline status from the active LightRAG endpoint."""
    active = read_active_snapshot(config.active_snapshot_file)
    base_url = active.base_url if active else config.base_url
    return await LightRAGClient(base_url, config.api_key).pipeline_status()


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
