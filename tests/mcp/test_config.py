from pathlib import Path

from lightrag_mcp.config import MCPConfig


def test_config_reads_container_defaults(monkeypatch):
    monkeypatch.delenv("LIGHTRAG_MCP_BASE_URL", raising=False)
    monkeypatch.delenv("LIGHTRAG_MCP_SNAPSHOT_BASE_URL", raising=False)
    monkeypatch.delenv("LIGHTRAG_MCP_SOURCE_DIR", raising=False)
    monkeypatch.delenv("LIGHTRAG_MCP_SNAPSHOT_DIR", raising=False)

    config = MCPConfig.from_env()

    assert config.base_url == "http://lightrag-api:9621"
    assert config.snapshot_base_url == "http://lightrag-snapshot:9621"
    assert config.source_dir == Path("/app/data/hermes_sources")
    assert config.snapshot_dir == Path("/app/data/hermes_snapshots")
    assert config.active_snapshot_file == Path(
        "/app/data/hermes_snapshots/active.json"
    )


def test_config_allows_host_overrides(monkeypatch, tmp_path):
    source_dir = tmp_path / "sources"
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setenv("LIGHTRAG_MCP_BASE_URL", "http://127.0.0.1:9621")
    monkeypatch.setenv("LIGHTRAG_MCP_SNAPSHOT_BASE_URL", "http://127.0.0.1:9721")
    monkeypatch.setenv("LIGHTRAG_MCP_API_KEY", "secret")
    monkeypatch.setenv("LIGHTRAG_MCP_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("LIGHTRAG_MCP_SNAPSHOT_DIR", str(snapshot_dir))

    config = MCPConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9621"
    assert config.snapshot_base_url == "http://127.0.0.1:9721"
    assert config.api_key == "secret"
    assert config.source_dir == source_dir
    assert config.snapshot_dir == snapshot_dir
