from pathlib import Path

import pytest
import yaml

from hermes_ui.config import HermesUISettings
from hermes_ui.hermes_config import ensure_hermes_home


def test_settings_defaults_are_container_safe_and_env_driven(monkeypatch):
    env_names = [
        "HERMES_UI_HOST",
        "HERMES_UI_PORT",
        "HERMES_HOME",
        "HERMES_MODEL",
        "HERMES_PROVIDER",
        "HERMES_BASE_URL",
        "LIGHTRAG_MCP_URL",
        "HERMES_UI_HERMES_TIMEOUT",
    ]
    for env_name in env_names:
        monkeypatch.delenv(env_name, raising=False)

    defaults = HermesUISettings()

    assert defaults.host == "0.0.0.0"
    assert defaults.port == 8787
    assert defaults.hermes_home == Path("/app/hermes_home")
    assert defaults.hermes_model == "gpt-5.4-mini"
    assert defaults.hermes_provider == "openai-api"
    assert defaults.hermes_base_url == "https://api.openai.com/v1"
    assert defaults.mcp_url == "http://lightrag-mcp:8765/mcp"
    assert defaults.hermes_timeout_seconds == 120

    monkeypatch.setenv("HERMES_UI_HOST", "127.0.0.1")
    monkeypatch.setenv("HERMES_UI_PORT", "9999")
    monkeypatch.setenv("HERMES_HOME", "/tmp/hermes-test")
    monkeypatch.setenv("HERMES_MODEL", "custom-model")
    monkeypatch.setenv("HERMES_PROVIDER", "custom-provider")
    monkeypatch.setenv("HERMES_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LIGHTRAG_MCP_URL", "http://localhost:8765/mcp")
    monkeypatch.setenv("HERMES_UI_HERMES_TIMEOUT", "45")

    patched = HermesUISettings()

    assert patched.host == "127.0.0.1"
    assert patched.port == 9999
    assert patched.hermes_home == Path("/tmp/hermes-test")
    assert patched.hermes_model == "custom-model"
    assert patched.hermes_provider == "custom-provider"
    assert patched.hermes_base_url == "http://localhost:11434/v1"
    assert patched.mcp_url == "http://localhost:8765/mcp"
    assert patched.hermes_timeout_seconds == 45


def test_ensure_hermes_home_writes_openai_key_and_mcp_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    settings = HermesUISettings(
        hermes_home=tmp_path / "hermes",
        mcp_url="http://mcp.local:8765/mcp",
    )

    ensure_hermes_home(settings)

    assert (settings.hermes_home / ".env").read_text(encoding="utf-8") == (
        "OPENAI_API_KEY=sk-test-key\n"
    )

    config = yaml.safe_load(
        (settings.hermes_home / "config.yaml").read_text(encoding="utf-8")
    )
    assert config["model"]["provider"] == "openai-api"
    assert config["model"]["model"] == "gpt-5.4-mini"
    assert config["model"]["base_url"] == "https://api.openai.com/v1"
    assert config["terminal"]["backend"] == "docker"

    mcp_server = config["mcp_servers"]["lightrag-hermes"]
    assert mcp_server["url"] == "http://mcp.local:8765/mcp"
    assert mcp_server["resources"] is False
    assert mcp_server["prompts"] is False
    assert mcp_server["tools"] == [
        "adapter_status",
        "list_documents",
        "ingest_text_version",
        "query_latest_all",
        "query_latest_documents",
        "build_latest_snapshot",
        "get_pipeline_status",
    ]


def test_ensure_hermes_home_requires_openai_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ensure_hermes_home(settings)
