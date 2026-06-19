from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MCPConfig:
    base_url: str
    snapshot_base_url: str
    api_key: str
    source_dir: Path
    snapshot_dir: Path
    active_snapshot_file: Path
    default_query_mode: str
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "MCPConfig":
        snapshot_dir = Path(
            os.getenv("LIGHTRAG_MCP_SNAPSHOT_DIR", "/app/data/hermes_snapshots")
        )
        return cls(
            base_url=os.getenv("LIGHTRAG_MCP_BASE_URL", "http://lightrag-api:9621"),
            snapshot_base_url=os.getenv(
                "LIGHTRAG_MCP_SNAPSHOT_BASE_URL",
                "http://lightrag-snapshot:9621",
            ),
            api_key=os.getenv("LIGHTRAG_MCP_API_KEY", ""),
            source_dir=Path(
                os.getenv("LIGHTRAG_MCP_SOURCE_DIR", "/app/data/hermes_sources")
            ),
            snapshot_dir=snapshot_dir,
            active_snapshot_file=Path(
                os.getenv(
                    "LIGHTRAG_MCP_ACTIVE_SNAPSHOT_FILE",
                    str(snapshot_dir / "active.json"),
                )
            ),
            default_query_mode=os.getenv("LIGHTRAG_MCP_DEFAULT_QUERY_MODE", "mix"),
            host=os.getenv("LIGHTRAG_MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("LIGHTRAG_MCP_PORT", "8765")),
        )
