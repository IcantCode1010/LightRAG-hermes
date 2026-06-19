from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lightrag_mcp.config import MCPConfig


config = MCPConfig.from_env()
mcp = FastMCP("lightrag-hermes", host=config.host, port=config.port)


@mcp.tool()
def adapter_status() -> dict[str, str]:
    """Return adapter configuration that is safe to expose to Hermes."""
    return {
        "status": "ok",
        "base_url": config.base_url,
        "source_dir": str(config.source_dir),
        "snapshot_dir": str(config.snapshot_dir),
    }


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
