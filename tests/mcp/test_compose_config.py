from pathlib import Path

import yaml


def test_hermes_compose_declares_expected_services():
    compose = yaml.safe_load(Path("docker-compose.hermes.yml").read_text())

    assert set(compose["services"]) >= {
        "lightrag-api",
        "lightrag-mcp",
        "lightrag-snapshot",
    }
    assert "hermes-net" in compose["networks"]


def test_mcp_service_uses_internal_lightrag_url():
    compose = yaml.safe_load(Path("docker-compose.hermes.yml").read_text())
    environment = compose["services"]["lightrag-mcp"]["environment"]

    assert environment["LIGHTRAG_MCP_BASE_URL"] == "http://lightrag-api:9621"
    assert environment["LIGHTRAG_MCP_SNAPSHOT_BASE_URL"] == (
        "http://lightrag-snapshot:9621"
    )
    assert environment["LIGHTRAG_MCP_SOURCE_DIR"] == "/app/data/hermes_sources"
    assert environment["LIGHTRAG_MCP_SNAPSHOT_DIR"] == "/app/data/hermes_snapshots"


def test_snapshot_service_is_internal_and_has_dedicated_storage():
    compose = yaml.safe_load(Path("docker-compose.hermes.yml").read_text())
    service = compose["services"]["lightrag-snapshot"]

    assert "ports" not in service
    assert service["environment"]["WORKING_DIR"] == "/app/data/snapshot_rag_storage"
    assert service["environment"]["INPUT_DIR"] == "/app/data/snapshot_inputs"
    assert "./data/hermes_snapshot/rag_storage:/app/data/snapshot_rag_storage" in (
        service["volumes"]
    )
