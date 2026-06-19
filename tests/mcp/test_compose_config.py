from pathlib import Path

import yaml


def test_hermes_compose_declares_expected_services():
    compose = yaml.safe_load(Path("docker-compose.hermes.yml").read_text())

    assert set(compose["services"]) >= {"lightrag-api", "lightrag-mcp"}
    assert "hermes-net" in compose["networks"]


def test_mcp_service_uses_internal_lightrag_url():
    compose = yaml.safe_load(Path("docker-compose.hermes.yml").read_text())
    environment = compose["services"]["lightrag-mcp"]["environment"]

    assert environment["LIGHTRAG_MCP_BASE_URL"] == "http://lightrag-api:9621"
    assert environment["LIGHTRAG_MCP_SOURCE_DIR"] == "/app/data/hermes_sources"
    assert environment["LIGHTRAG_MCP_SNAPSHOT_DIR"] == "/app/data/hermes_snapshots"
