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


def test_lightrag_services_use_openai_embeddings_from_shared_env():
    compose = yaml.safe_load(Path("docker-compose.hermes.yml").read_text())

    for service_name in ("lightrag-api", "lightrag-snapshot"):
        environment = compose["services"][service_name]["environment"]

        assert environment["OPENAI_API_KEY"] == "${OPENAI_API_KEY:-}"
        assert environment["LLM_BINDING"] == "${LLM_BINDING:-openai}"
        assert environment["LLM_BINDING_API_KEY"] == "${OPENAI_API_KEY:-}"
        assert environment["LLM_MODEL"] == "${LIGHTRAG_LLM_MODEL:-gpt-4o-mini}"
        assert environment["EXTRACT_LLM_MODEL"] == (
            "${LIGHTRAG_EXTRACT_LLM_MODEL:-gpt-4o-mini}"
        )
        assert environment["KEYWORD_LLM_MODEL"] == (
            "${LIGHTRAG_KEYWORD_LLM_MODEL:-gpt-4o-mini}"
        )
        assert environment["QUERY_LLM_MODEL"] == (
            "${LIGHTRAG_QUERY_LLM_MODEL:-gpt-4o-mini}"
        )
        assert environment["EMBEDDING_BINDING"] == "${EMBEDDING_BINDING:-openai}"
        assert environment["EMBEDDING_BINDING_API_KEY"] == "${OPENAI_API_KEY:-}"
        assert environment["EMBEDDING_MODEL"] == (
            "${EMBEDDING_MODEL:-text-embedding-3-large}"
        )
        assert environment["EMBEDDING_DIM"] == "${EMBEDDING_DIM:-3072}"


def test_hermes_ui_mounts_only_snapshot_archive_for_maintenance():
    compose = yaml.safe_load(Path("docker-compose.hermes.yml").read_text())
    service = compose["services"]["hermes-ui"]

    assert service["environment"]["HERMES_SNAPSHOT_ARCHIVE_DIR"] == (
        "/app/data/hermes_snapshot_archive"
    )
    assert (
        "./data/hermes_snapshot_archive:/app/data/hermes_snapshot_archive"
        in service["volumes"]
    )
    assert not any(
        volume.startswith("./data/hermes_snapshot:")
        or volume.startswith("./data/hermes_sources:")
        for volume in service["volumes"]
    )
