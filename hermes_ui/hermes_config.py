import os

import yaml

from hermes_ui.config import HermesUISettings


HERMES_TOOLS = [
    "adapter_status",
    "list_documents",
    "ingest_text_version",
    "query_latest_all",
    "query_latest_documents",
    "build_latest_snapshot",
    "get_pipeline_status",
]


def ensure_hermes_home(settings: HermesUISettings) -> None:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY must be set before starting Hermes UI")

    settings.hermes_home.mkdir(parents=True, exist_ok=True)
    (settings.hermes_home / ".env").write_text(
        f"OPENAI_API_KEY={openai_api_key}\n",
        encoding="utf-8",
    )
    (settings.hermes_home / "config.yaml").write_text(
        yaml.safe_dump(_build_config(settings), sort_keys=False),
        encoding="utf-8",
    )


def _build_config(settings: HermesUISettings) -> dict[str, object]:
    return {
        "model": {
            "provider": settings.hermes_provider,
            "model": settings.hermes_model,
            "base_url": settings.hermes_base_url,
        },
        "terminal": {
            "backend": "docker",
        },
        "mcp_servers": {
            "lightrag-hermes": {
                "url": settings.mcp_url,
                "tools": HERMES_TOOLS,
                "resources": False,
                "prompts": False,
            },
        },
    }
