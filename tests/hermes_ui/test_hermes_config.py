from pathlib import Path
import tomllib

from dotenv import dotenv_values
import pytest
import yaml

from hermes_ui.config import HermesUISettings
from hermes_ui.hermes_config import ensure_hermes_home


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_settings_defaults_are_container_safe_and_env_driven(monkeypatch):
    env_names = [
        "HERMES_UI_HOST",
        "HERMES_UI_PORT",
        "HERMES_HOME",
        "HERMES_MODEL",
        "HERMES_PROVIDER",
        "HERMES_BASE_URL",
        "LIGHTRAG_MCP_URL",
        "HERMES_SOUL_FILE",
        "HERMES_SNAPSHOT_ARCHIVE_DIR",
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
    assert defaults.soul_file.name == "soul.md"
    assert defaults.snapshot_archive_dir == Path("/app/data/hermes_snapshot_archive")
    assert defaults.hermes_timeout_seconds == 120

    soul_file = Path("/tmp/custom-soul.md")
    archive_dir = Path("/tmp/snapshot-archives")
    monkeypatch.setenv("HERMES_UI_HOST", "127.0.0.1")
    monkeypatch.setenv("HERMES_UI_PORT", "9999")
    monkeypatch.setenv("HERMES_HOME", "/tmp/hermes-test")
    monkeypatch.setenv("HERMES_MODEL", "custom-model")
    monkeypatch.setenv("HERMES_PROVIDER", "custom-provider")
    monkeypatch.setenv("HERMES_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LIGHTRAG_MCP_URL", "http://localhost:8765/mcp")
    monkeypatch.setenv("HERMES_SOUL_FILE", str(soul_file))
    monkeypatch.setenv("HERMES_SNAPSHOT_ARCHIVE_DIR", str(archive_dir))
    monkeypatch.setenv("HERMES_UI_HERMES_TIMEOUT", "45")

    patched = HermesUISettings()

    assert patched.host == "127.0.0.1"
    assert patched.port == 9999
    assert patched.hermes_home == Path("/tmp/hermes-test")
    assert patched.hermes_model == "custom-model"
    assert patched.hermes_provider == "custom-provider"
    assert patched.hermes_base_url == "http://localhost:11434/v1"
    assert patched.mcp_url == "http://localhost:8765/mcp"
    assert patched.soul_file == soul_file
    assert patched.snapshot_archive_dir == archive_dir
    assert patched.hermes_timeout_seconds == 45


def test_ensure_hermes_home_writes_openai_key_and_mcp_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    settings = HermesUISettings(
        hermes_home=tmp_path / "hermes",
        mcp_url="http://mcp.local:8765/mcp",
    )

    ensure_hermes_home(settings)

    assert (
        dotenv_values(settings.hermes_home / ".env")["OPENAI_API_KEY"]
        == "sk-test-key"
    )

    config = yaml.safe_load(
        (settings.hermes_home / "config.yaml").read_text(encoding="utf-8")
    )
    assert config["model"]["provider"] == "openai-api"
    assert config["model"]["default"] == "gpt-5.4-mini"
    assert config["model"]["base_url"] == "https://api.openai.com/v1"
    assert config["terminal"]["backend"] == "docker"

    mcp_server = config["mcp_servers"]["lightrag-hermes"]
    assert mcp_server["enabled"] is True
    assert mcp_server["url"] == "http://mcp.local:8765/mcp"
    assert mcp_server["tools"]["resources"] is False
    assert mcp_server["tools"]["prompts"] is False
    assert mcp_server["tools"]["include"] == [
        "adapter_status",
        "list_documents",
        "search_documents",
        "get_document_state",
        "list_unsearchable_latest",
        "ingest_file_version",
        "ingest_text_version",
        "query_latest_all",
        "query_latest_documents",
        "build_latest_snapshot",
        "snapshot_status",
        "get_pipeline_status",
    ]


def test_ensure_hermes_home_requires_openai_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ensure_hermes_home(settings)


def test_ensure_hermes_home_quotes_openai_api_key_for_dotenv(
    tmp_path, monkeypatch
):
    api_key = "sk test#value$with'quotes\"and spaces"
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")

    ensure_hermes_home(settings)

    env_path = settings.hermes_home / ".env"
    assert dotenv_values(env_path)["OPENAI_API_KEY"] == api_key
    assert env_path.read_text(encoding="utf-8").startswith("OPENAI_API_KEY='")


def test_ensure_hermes_home_chmods_env_file_owner_only(tmp_path, monkeypatch):
    chmod_calls = []
    original_chmod = Path.chmod

    def record_chmod(path, mode, *args, **kwargs):
        chmod_calls.append((path, mode))
        return original_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", record_chmod)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")

    ensure_hermes_home(settings)

    assert (settings.hermes_home / ".env", 0o600) in chmod_calls


def test_package_discovery_includes_hermes_ui():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())

    package_includes = pyproject["tool"]["setuptools"]["packages"]["find"][
        "include"
    ]

    assert "hermes_ui*" in package_includes
