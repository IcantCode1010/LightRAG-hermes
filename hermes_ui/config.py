from dataclasses import dataclass, field
import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if value is None:
        return default
    return Path(value)


def _default_soul_file() -> Path:
    return Path(__file__).resolve().parent / "soul.md"


@dataclass(slots=True)
class HermesUISettings:
    host: str = field(default_factory=lambda: os.getenv("HERMES_UI_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("HERMES_UI_PORT", 8787))
    hermes_home: Path = field(
        default_factory=lambda: _env_path("HERMES_HOME", Path("/app/hermes_home"))
    )
    hermes_model: str = field(
        default_factory=lambda: os.getenv("HERMES_MODEL", "gpt-5.4-mini")
    )
    hermes_provider: str = field(
        default_factory=lambda: os.getenv("HERMES_PROVIDER", "openai-api")
    )
    hermes_base_url: str = field(
        default_factory=lambda: os.getenv(
            "HERMES_BASE_URL",
            "https://api.openai.com/v1",
        )
    )
    mcp_url: str = field(
        default_factory=lambda: os.getenv(
            "LIGHTRAG_MCP_URL",
            "http://lightrag-mcp:8765/mcp",
        )
    )
    soul_file: Path = field(
        default_factory=lambda: _env_path("HERMES_SOUL_FILE", _default_soul_file())
    )
    hermes_timeout_seconds: int = field(
        default_factory=lambda: _env_int("HERMES_UI_HERMES_TIMEOUT", 120)
    )
