# Hermes Local Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized local web UI that lets a user chat with Hermes, ingest document versions, build latest-only snapshots, and inspect registry/status without using the raw LightRAG WebUI.

**Architecture:** Add a new `hermes-ui` service that serves a FastAPI backend plus static frontend. The container provisions Hermes inside `/app/hermes_home`, uses the OpenAI key from `.env`, points Hermes at the internal `http://lightrag-mcp:8765/mcp` MCP endpoint, and runs Hermes non-interactively for agent actions.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, httpx, pydantic, MCP Python client, Hermes CLI installed from `https://github.com/NousResearch/hermes-agent`, vanilla TypeScript/HTML/CSS frontend, Docker Compose.

---

## File Structure

- Create `hermes_ui/__init__.py`: package marker.
- Create `hermes_ui/config.py`: reads runtime env vars and exposes typed settings.
- Create `hermes_ui/hermes_config.py`: writes container-local Hermes config and `.env`.
- Create `hermes_ui/hermes_runner.py`: validates prompts and runs `hermes chat --quiet`.
- Create `hermes_ui/mcp_client.py`: reads safe structured status from `lightrag-mcp`.
- Create `hermes_ui/api.py`: FastAPI app and API routes.
- Create `hermes_ui/static/index.html`: app shell.
- Create `hermes_ui/static/styles.css`: operational dashboard styling.
- Create `hermes_ui/static/app.js`: frontend state, API calls, and UI rendering.
- Create `tests/hermes_ui/test_hermes_runner.py`: command/prompt tests.
- Create `tests/hermes_ui/test_api.py`: route smoke tests with mocked adapters.
- Create `Dockerfile.hermes-ui`: builds the UI service image.
- Modify `docker-compose.hermes.yml`: add `hermes-ui` service bound to `127.0.0.1:8787`.
- Modify `.gitignore`: ignore `data/hermes_ui_home/`.
- Modify `docs/HermesAgentIntegration.md`: add UI run instructions.

---

### Task 1: Backend Settings And Hermes Config Writer

**Files:**
- Create: `hermes_ui/__init__.py`
- Create: `hermes_ui/config.py`
- Create: `hermes_ui/hermes_config.py`
- Test: `tests/hermes_ui/test_hermes_config.py`

- [ ] **Step 1: Write failing tests for settings and config rendering**

Create `tests/hermes_ui/test_hermes_config.py`:

```python
from pathlib import Path

from hermes_ui.config import HermesUISettings
from hermes_ui.hermes_config import ensure_hermes_home


def test_settings_defaults_are_container_safe(monkeypatch):
    monkeypatch.delenv("HERMES_UI_HOST", raising=False)
    monkeypatch.delenv("HERMES_UI_PORT", raising=False)
    monkeypatch.delenv("LIGHTRAG_MCP_URL", raising=False)

    settings = HermesUISettings()

    assert settings.host == "0.0.0.0"
    assert settings.port == 8787
    assert settings.mcp_url == "http://lightrag-mcp:8765/mcp"
    assert settings.hermes_model == "gpt-5.4-mini"
    assert settings.hermes_provider == "openai-api"


def test_ensure_hermes_home_writes_openai_and_mcp_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = HermesUISettings(hermes_home=tmp_path)

    ensure_hermes_home(settings)

    config_text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")

    assert "provider: openai-api" in config_text
    assert "default: gpt-5.4-mini" in config_text
    assert "url: http://lightrag-mcp:8765/mcp" in config_text
    assert "resources: false" in config_text
    assert "prompts: false" in config_text
    assert "OPENAI_API_KEY=sk-test" in env_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/hermes_ui/test_hermes_config.py -q
```

Expected: FAIL because `hermes_ui.config` and `hermes_ui.hermes_config` do not exist.

- [ ] **Step 3: Implement settings and config writer**

Create `hermes_ui/__init__.py`:

```python
"""Local Hermes web UI package."""
```

Create `hermes_ui/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HermesUISettings:
    host: str = field(default_factory=lambda: os.getenv("HERMES_UI_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("HERMES_UI_PORT", "8787")))
    hermes_home: Path = field(default_factory=lambda: Path(os.getenv("HERMES_HOME", "/app/hermes_home")))
    hermes_model: str = field(default_factory=lambda: os.getenv("HERMES_MODEL", "gpt-5.4-mini"))
    hermes_provider: str = field(default_factory=lambda: os.getenv("HERMES_PROVIDER", "openai-api"))
    hermes_base_url: str = field(default_factory=lambda: os.getenv("HERMES_BASE_URL", "https://api.openai.com/v1"))
    mcp_url: str = field(default_factory=lambda: os.getenv("LIGHTRAG_MCP_URL", "http://lightrag-mcp:8765/mcp"))
    hermes_timeout_seconds: int = field(default_factory=lambda: int(os.getenv("HERMES_UI_HERMES_TIMEOUT", "120")))
```

Create `hermes_ui/hermes_config.py`:

```python
from __future__ import annotations

import os

from hermes_ui.config import HermesUISettings


TOOLS = [
    "adapter_status",
    "list_documents",
    "ingest_text_version",
    "query_latest_all",
    "query_latest_documents",
    "build_latest_snapshot",
    "get_pipeline_status",
]


def ensure_hermes_home(settings: HermesUISettings) -> None:
    settings.hermes_home.mkdir(parents=True, exist_ok=True)
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY is required for the Hermes UI service")

    config = _render_config(settings)
    (settings.hermes_home / "config.yaml").write_text(config, encoding="utf-8")
    (settings.hermes_home / ".env").write_text(
        f"OPENAI_API_KEY={openai_key}\n",
        encoding="utf-8",
    )


def _render_config(settings: HermesUISettings) -> str:
    tool_lines = "\n".join(f"      - {tool}" for tool in TOOLS)
    return f"""model:
  default: {settings.hermes_model}
  provider: {settings.hermes_provider}
  base_url: {settings.hermes_base_url}
terminal:
  backend: docker
  cwd: .
mcp_servers:
  lightrag-hermes:
    url: {settings.mcp_url}
    enabled: true
    tools:
      include:
{tool_lines}
      resources: false
      prompts: false
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/hermes_ui/test_hermes_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add hermes_ui tests/hermes_ui/test_hermes_config.py
git commit -m "feat: add Hermes UI runtime config"
```

---

### Task 2: Hermes Runner And Prompt Builders

**Files:**
- Create: `hermes_ui/hermes_runner.py`
- Test: `tests/hermes_ui/test_hermes_runner.py`

- [ ] **Step 1: Write failing tests for command construction and prompts**

Create `tests/hermes_ui/test_hermes_runner.py`:

```python
import asyncio

import pytest

from hermes_ui.config import HermesUISettings
from hermes_ui.hermes_runner import (
    build_chat_command,
    build_ingest_prompt,
    build_snapshot_prompt,
    run_hermes_query,
)


def test_build_chat_command_sets_home_and_quiet_mode(tmp_path):
    settings = HermesUISettings(hermes_home=tmp_path)

    command, env = build_chat_command("hello", settings)

    assert command == [
        "hermes",
        "chat",
        "--query",
        "hello",
        "--quiet",
        "--max-turns",
        "8",
    ]
    assert env["HERMES_HOME"] == str(tmp_path)


def test_ingest_prompt_mentions_no_delete_or_overwrite():
    prompt = build_ingest_prompt(
        document_key="policy",
        version_label="v2026.06.20.001",
        title="Policy",
        text="Body",
    )

    assert "ingest_text_version" in prompt
    assert "Never delete" in prompt
    assert "document_key: policy" in prompt
    assert "version_label: v2026.06.20.001" in prompt


def test_snapshot_prompt_warns_latest_only():
    prompt = build_snapshot_prompt("snapshot-2026.06.20.001")

    assert "build_latest_snapshot" in prompt
    assert "latest archived document versions only" in prompt


def test_run_hermes_query_returns_stdout(tmp_path):
    async def fake_exec(*args, **kwargs):
        return 0, "answer", ""

    result = asyncio.run(
        run_hermes_query(
            "hello",
            HermesUISettings(hermes_home=tmp_path),
            executor=fake_exec,
        )
    )

    assert result == {"state": "ok", "text": "answer"}


def test_run_hermes_query_reports_errors(tmp_path):
    async def fake_exec(*args, **kwargs):
        return 1, "", "bad model"

    result = asyncio.run(
        run_hermes_query(
            "hello",
            HermesUISettings(hermes_home=tmp_path),
            executor=fake_exec,
        )
    )

    assert result == {"state": "error", "message": "bad model"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/hermes_ui/test_hermes_runner.py -q
```

Expected: FAIL because `hermes_ui.hermes_runner` does not exist.

- [ ] **Step 3: Implement Hermes runner**

Create `hermes_ui/hermes_runner.py`:

```python
from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

from hermes_ui.config import HermesUISettings

Executor = Callable[[list[str], dict[str, str], int], Awaitable[tuple[int, str, str]]]


def build_chat_command(prompt: str, settings: HermesUISettings) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(settings.hermes_home)
    return (
        [
            "hermes",
            "chat",
            "--query",
            prompt,
            "--quiet",
            "--max-turns",
            "8",
        ],
        env,
    )


def build_ingest_prompt(
    *,
    document_key: str,
    version_label: str,
    title: str,
    text: str,
) -> str:
    return (
        "Use the lightrag-hermes MCP server's ingest_text_version tool. "
        "Never delete, clear, overwrite, or replace existing documents. "
        "Reject duplicate document/version pairs if the tool reports a duplicate.\n\n"
        f"document_key: {document_key}\n"
        f"version_label: {version_label}\n"
        f"title: {title}\n"
        f"text:\n{text}"
    )


def build_snapshot_prompt(snapshot_id: str) -> str:
    return (
        "Use the lightrag-hermes MCP server's build_latest_snapshot tool. "
        "Build the snapshot from latest archived document versions only. "
        "Do not clear, delete, or rotate any storage.\n\n"
        f"snapshot_id: {snapshot_id}"
    )


async def run_hermes_query(
    prompt: str,
    settings: HermesUISettings,
    *,
    executor: Executor | None = None,
) -> dict[str, str]:
    command, env = build_chat_command(prompt, settings)
    run = executor or _exec
    code, stdout, stderr = await run(command, env, settings.hermes_timeout_seconds)
    if code != 0:
        return {"state": "error", "message": (stderr or stdout).strip()}
    return {"state": "ok", "text": stdout.strip()}


async def _exec(command: list[str], env: dict[str, str], timeout: int) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.communicate()
        return 124, "", "Hermes request timed out"
    return (
        process.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/hermes_ui/test_hermes_runner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add hermes_ui/hermes_runner.py tests/hermes_ui/test_hermes_runner.py
git commit -m "feat: add Hermes UI command runner"
```

---

### Task 3: MCP Structured Status Client

**Files:**
- Create: `hermes_ui/mcp_client.py`
- Test: `tests/hermes_ui/test_mcp_client.py`

- [ ] **Step 1: Write failing tests for response normalization**

Create `tests/hermes_ui/test_mcp_client.py`:

```python
import asyncio

from hermes_ui.mcp_client import normalize_documents, normalize_status


def test_normalize_documents_marks_latest_version():
    payload = {
        "documents": [
            {
                "document_key": "policy",
                "versions": ["v2026.06.19.001", "v2026.06.20.001"],
                "latest_version_label": "v2026.06.20.001",
            }
        ]
    }

    result = normalize_documents(payload)

    assert result["documents"][0]["document_key"] == "policy"
    assert result["documents"][0]["latest_version_label"] == "v2026.06.20.001"
    assert result["documents"][0]["versions"][0]["searchable"] is False
    assert result["documents"][0]["versions"][1]["searchable"] is True


def test_normalize_status_redacts_adapter_paths():
    result = normalize_status(
        adapter={"status": "ok", "base_url": "http://lightrag-api:9621"},
        pipeline={"busy": False, "docs": 2},
    )

    assert result == {
        "state": "ok",
        "mcp": {"status": "ok", "base_url": "http://lightrag-api:9621"},
        "pipeline": {"busy": False, "docs": 2},
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/hermes_ui/test_mcp_client.py -q
```

Expected: FAIL because `hermes_ui.mcp_client` does not exist.

- [ ] **Step 3: Implement normalization and direct MCP calls**

Create `hermes_ui/mcp_client.py`:

```python
from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def normalize_documents(payload: dict[str, Any]) -> dict[str, Any]:
    documents = []
    for document in payload.get("documents", []):
        latest = document.get("latest_version_label")
        versions = [
            {"label": version, "searchable": version == latest}
            for version in document.get("versions", [])
        ]
        documents.append(
            {
                "document_key": document.get("document_key"),
                "latest_version_label": latest,
                "versions": versions,
            }
        )
    return {"documents": documents}


def normalize_status(adapter: dict[str, Any], pipeline: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": "ok",
        "mcp": {
            "status": adapter.get("status"),
            "base_url": adapter.get("base_url"),
        },
        "pipeline": {
            "busy": bool(pipeline.get("busy", False)),
            "docs": int(pipeline.get("docs", 0)),
        },
    }


async def call_tool(mcp_url: str, tool_name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args or {})
            text = getattr(result.content[0], "text", "{}")
            return json.loads(text)


async def get_documents(mcp_url: str) -> dict[str, Any]:
    return normalize_documents(await call_tool(mcp_url, "list_documents"))


async def get_status(mcp_url: str) -> dict[str, Any]:
    adapter = await call_tool(mcp_url, "adapter_status")
    pipeline = await call_tool(mcp_url, "get_pipeline_status")
    return normalize_status(adapter, pipeline)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/hermes_ui/test_mcp_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add hermes_ui/mcp_client.py tests/hermes_ui/test_mcp_client.py
git commit -m "feat: add Hermes UI MCP status client"
```

---

### Task 4: FastAPI Backend

**Files:**
- Create: `hermes_ui/api.py`
- Test: `tests/hermes_ui/test_api.py`

- [ ] **Step 1: Write failing API tests with dependency overrides**

Create `tests/hermes_ui/test_api.py`:

```python
from fastapi.testclient import TestClient

from hermes_ui.api import create_app
from hermes_ui.config import HermesUISettings


def test_status_route_returns_structured_state(tmp_path):
    async def fake_status(_mcp_url):
        return {"state": "ok", "mcp": {"status": "ok"}, "pipeline": {"docs": 0}}

    app = create_app(
        HermesUISettings(hermes_home=tmp_path),
        status_reader=fake_status,
        provision_hermes=False,
    )
    client = TestClient(app)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["state"] == "ok"


def test_chat_route_runs_hermes(tmp_path):
    async def fake_runner(prompt, settings):
        assert prompt == "hello"
        assert settings.hermes_home == tmp_path
        return {"state": "ok", "text": "world"}

    app = create_app(
        HermesUISettings(hermes_home=tmp_path),
        hermes_runner=fake_runner,
        provision_hermes=False,
    )
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"state": "ok", "text": "world"}


def test_ingest_requires_version_label(tmp_path):
    app = create_app(HermesUISettings(hermes_home=tmp_path), provision_hermes=False)
    client = TestClient(app)

    response = client.post(
        "/api/ingest",
        json={"document_key": "policy", "version_label": "", "title": "Policy", "text": "Body"},
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/hermes_ui/test_api.py -q
```

Expected: FAIL because `hermes_ui.api` does not exist.

- [ ] **Step 3: Implement FastAPI app**

Create `hermes_ui/api.py`:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from hermes_ui.config import HermesUISettings
from hermes_ui.hermes_config import ensure_hermes_home
from hermes_ui.hermes_runner import build_ingest_prompt, build_snapshot_prompt, run_hermes_query
from hermes_ui.mcp_client import get_documents, get_status

HermesRunner = Callable[[str, HermesUISettings], Awaitable[dict[str, str]]]
StatusReader = Callable[[str], Awaitable[dict]]
DocumentReader = Callable[[str], Awaitable[dict]]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    document_keys: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    document_key: str = Field(min_length=1)
    version_label: str = Field(pattern=r"^v\d{4}\.\d{2}\.\d{2}\.\d{3}$")
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)


class SnapshotRequest(BaseModel):
    snapshot_id: str = Field(min_length=1)


def create_app(
    settings: HermesUISettings | None = None,
    *,
    hermes_runner: HermesRunner = run_hermes_query,
    status_reader: StatusReader = get_status,
    document_reader: DocumentReader = get_documents,
    provision_hermes: bool = True,
) -> FastAPI:
    app_settings = settings or HermesUISettings()
    if provision_hermes:
        ensure_hermes_home(app_settings)
    app = FastAPI(title="Hermes LightRAG UI")

    @app.get("/api/status")
    async def status() -> dict:
        return await status_reader(app_settings.mcp_url)

    @app.get("/api/documents")
    async def documents() -> dict:
        return await document_reader(app_settings.mcp_url)

    @app.post("/api/chat")
    async def chat(request: ChatRequest) -> dict:
        if request.document_keys:
            keys = ", ".join(request.document_keys)
            prompt = (
                "Use the lightrag-hermes MCP server's query_latest_documents tool "
                f"for document keys [{keys}] to answer: {request.message}"
            )
        else:
            prompt = (
                "Use the lightrag-hermes MCP server's query_latest_all tool to answer: "
                f"{request.message}"
            )
        return await hermes_runner(prompt, app_settings)

    @app.post("/api/ingest")
    async def ingest(request: IngestRequest) -> dict:
        prompt = build_ingest_prompt(**request.model_dump())
        return await hermes_runner(prompt, app_settings)

    @app.post("/api/snapshots/build")
    async def build_snapshot(request: SnapshotRequest) -> dict:
        return await hermes_runner(build_snapshot_prompt(request.snapshot_id), app_settings)

    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
    return app


app = create_app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
python -m pytest tests/hermes_ui/test_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add hermes_ui/api.py tests/hermes_ui/test_api.py
git commit -m "feat: add Hermes UI backend API"
```

---

### Task 5: Local Web UI Frontend

**Files:**
- Create: `hermes_ui/static/index.html`
- Create: `hermes_ui/static/styles.css`
- Create: `hermes_ui/static/app.js`

- [ ] **Step 1: Create app shell HTML**

Create `hermes_ui/static/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Hermes LightRAG</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body>
    <main class="app">
      <aside class="sidebar">
        <div>
          <p class="eyebrow">Hermes LightRAG</p>
          <h1>Latest document agent</h1>
        </div>
        <section class="status-list" id="status"></section>
      </aside>

      <section class="chat-panel">
        <header class="panel-header">
          <div>
            <p class="eyebrow">Agent Chat</p>
            <h2>Ask latest documents</h2>
          </div>
          <button id="refresh" type="button">Refresh</button>
        </header>
        <div class="messages" id="messages"></div>
        <form class="composer" id="chat-form">
          <textarea id="chat-message" placeholder="Ask Hermes a question..." required></textarea>
          <button type="submit">Send</button>
        </form>
      </section>

      <aside class="tools-panel">
        <nav class="tabs" aria-label="Tools">
          <button class="tab active" data-tab="documents" type="button">Documents</button>
          <button class="tab" data-tab="snapshot" type="button">Snapshot</button>
        </nav>

        <section id="documents-tab">
          <form class="tool-form" id="ingest-form">
            <label>Document key<input id="document-key" required /></label>
            <label>Version label<input id="version-label" pattern="^v\\d{4}\\.\\d{2}\\.\\d{2}\\.\\d{3}$" required /></label>
            <label>Title<input id="title" required /></label>
            <label>Text<textarea id="document-text" required></textarea></label>
            <button type="submit">Ingest version</button>
          </form>
          <div class="registry" id="documents"></div>
        </section>

        <section id="snapshot-tab" hidden>
          <form class="tool-form" id="snapshot-form">
            <label>Snapshot ID<input id="snapshot-id" required /></label>
            <p class="note">Building a snapshot may use embedding/model API credits.</p>
            <button type="submit">Build latest snapshot</button>
          </form>
        </section>
      </aside>
    </main>
    <script src="/app.js" type="module"></script>
  </body>
</html>
```

- [ ] **Step 2: Add operational CSS**

Create `hermes_ui/static/styles.css` with stable dimensions and no decorative hero:

```css
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --panel: #ffffff;
  --line: #d9dee7;
  --text: #172033;
  --muted: #687386;
  --accent: #0f766e;
  --accent-strong: #0b5f59;
  --danger: #b42318;
  --ok: #147a3f;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  letter-spacing: 0;
}

button,
input,
textarea {
  font: inherit;
}

button {
  border: 1px solid var(--accent);
  background: var(--accent);
  color: white;
  border-radius: 6px;
  min-height: 36px;
  padding: 0 12px;
  cursor: pointer;
}

button:hover {
  background: var(--accent-strong);
}

.app {
  display: grid;
  grid-template-columns: 280px minmax(420px, 1fr) 380px;
  min-height: 100vh;
}

.sidebar,
.chat-panel,
.tools-panel {
  border-right: 1px solid var(--line);
  background: var(--panel);
}

.sidebar,
.tools-panel {
  padding: 18px;
}

.chat-panel {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 18px;
  border-bottom: 1px solid var(--line);
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
}

h1,
h2 {
  margin: 0;
  font-size: 20px;
}

.status-list,
.registry,
.messages {
  display: grid;
  gap: 10px;
}

.status-item,
.doc-row,
.message {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.messages {
  overflow: auto;
  padding: 18px;
  align-content: start;
}

.message.user {
  border-color: #b9c7e6;
  background: #f4f7ff;
}

.message.agent {
  border-color: #bddbd7;
  background: #f2fbf9;
}

.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  padding: 18px;
  border-top: 1px solid var(--line);
}

textarea {
  min-height: 88px;
  resize: vertical;
}

input,
textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 9px 10px;
}

.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
}

.tab {
  background: #eef2f7;
  color: var(--text);
  border-color: var(--line);
}

.tab.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.tool-form {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
}

label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 13px;
}

.note {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.4;
}

.pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: 999px;
  padding: 0 8px;
  font-size: 12px;
  background: #eef2f7;
}

.pill.ok {
  color: var(--ok);
}

.pill.error {
  color: var(--danger);
}

@media (max-width: 1100px) {
  .app {
    grid-template-columns: 1fr;
  }

  .sidebar,
  .tools-panel {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
}
```

- [ ] **Step 3: Add frontend behavior**

Create `hermes_ui/static/app.js`:

```javascript
const state = {
  documents: [],
};

const statusEl = document.querySelector("#status");
const documentsEl = document.querySelector("#documents");
const messagesEl = document.querySelector("#messages");

document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#chat-form").addEventListener("submit", sendChat);
document.querySelector("#ingest-form").addEventListener("submit", ingestDocument);
document.querySelector("#snapshot-form").addEventListener("submit", buildSnapshot);

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector("#documents-tab").hidden = tab.dataset.tab !== "documents";
    document.querySelector("#snapshot-tab").hidden = tab.dataset.tab !== "snapshot";
  });
}

document.querySelector("#version-label").value = nextVersionLabel();
document.querySelector("#snapshot-id").value = `snapshot-${datePart()}.001`;

async function refresh() {
  const [status, docs] = await Promise.all([api("/api/status"), api("/api/documents")]);
  renderStatus(status);
  state.documents = docs.documents || [];
  renderDocuments();
}

async function sendChat(event) {
  event.preventDefault();
  const input = document.querySelector("#chat-message");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMessage("user", message);
  const response = await api("/api/chat", { method: "POST", body: { message } });
  addMessage("agent", response.text || response.message || "No response");
}

async function ingestDocument(event) {
  event.preventDefault();
  const body = {
    document_key: document.querySelector("#document-key").value.trim(),
    version_label: document.querySelector("#version-label").value.trim(),
    title: document.querySelector("#title").value.trim(),
    text: document.querySelector("#document-text").value,
  };
  const response = await api("/api/ingest", { method: "POST", body });
  addMessage("agent", response.text || response.message || "Ingest request complete");
  await refresh();
}

async function buildSnapshot(event) {
  event.preventDefault();
  const snapshot_id = document.querySelector("#snapshot-id").value.trim();
  const response = await api("/api/snapshots/build", { method: "POST", body: { snapshot_id } });
  addMessage("agent", response.text || response.message || "Snapshot request complete");
  await refresh();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text);
  }
  return response.json();
}

function renderStatus(status) {
  const mcp = status.mcp || {};
  const pipeline = status.pipeline || {};
  statusEl.innerHTML = `
    <div class="status-item"><strong>MCP</strong><br><span class="pill ok">${mcp.status || "unknown"}</span></div>
    <div class="status-item"><strong>Pipeline</strong><br>${pipeline.busy ? "Busy" : "Idle"}</div>
    <div class="status-item"><strong>Indexed docs</strong><br>${pipeline.docs ?? 0}</div>
  `;
}

function renderDocuments() {
  if (!state.documents.length) {
    documentsEl.innerHTML = `<div class="doc-row">No archived documents yet.</div>`;
    return;
  }
  documentsEl.innerHTML = state.documents
    .map((doc) => {
      const versions = doc.versions
        .map((version) => `<span class="pill ${version.searchable ? "ok" : ""}">${version.label}${version.searchable ? " latest" : ""}</span>`)
        .join(" ");
      return `<div class="doc-row"><strong>${doc.document_key}</strong><br>${versions}</div>`;
    })
    .join("");
}

function addMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function datePart() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}.${m}.${d}`;
}

function nextVersionLabel() {
  return `v${datePart()}.001`;
}

refresh().catch((error) => addMessage("agent", error.message));
```

- [ ] **Step 4: Run static sanity checks**

Run:

```powershell
python -m compileall hermes_ui
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add hermes_ui/static
git commit -m "feat: add Hermes local web UI frontend"
```

---

### Task 6: Docker Image And Compose Service

**Files:**
- Create: `Dockerfile.hermes-ui`
- Modify: `docker-compose.hermes.yml`
- Modify: `.gitignore`

- [ ] **Step 1: Create Dockerfile for UI service**

Create `Dockerfile.hermes-ui`:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HERMES_HOME=/app/hermes_home

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic>=2.8" \
    "httpx>=0.28" \
    "mcp>=1.7.1,<2.0.0" \
    "git+https://github.com/NousResearch/hermes-agent.git"

COPY hermes_ui/ ./hermes_ui/

EXPOSE 8787

CMD ["uvicorn", "hermes_ui.api:app", "--host", "0.0.0.0", "--port", "8787"]
```

- [ ] **Step 2: Add compose service**

Modify `docker-compose.hermes.yml` by adding this service after `lightrag-mcp`:

```yaml
  hermes-ui:
    build:
      context: .
      dockerfile: Dockerfile.hermes-ui
    image: lightrag-hermes-ui:local
    env_file:
      - path: .env
        required: false
    ports:
      - "${HERMES_UI_HOST_BIND:-127.0.0.1}:${HERMES_UI_PORT:-8787}:8787"
    volumes:
      - ./data/hermes_ui_home:/app/hermes_home
    environment:
      HERMES_HOME: "/app/hermes_home"
      HERMES_UI_HOST: "0.0.0.0"
      HERMES_UI_PORT: "8787"
      HERMES_MODEL: "${HERMES_MODEL:-gpt-5.4-mini}"
      HERMES_PROVIDER: "openai-api"
      HERMES_BASE_URL: "https://api.openai.com/v1"
      LIGHTRAG_MCP_URL: "http://lightrag-mcp:8765/mcp"
    depends_on:
      - lightrag-mcp
    networks:
      - hermes-net
    restart: unless-stopped
```

- [ ] **Step 3: Ignore generated Hermes UI home**

Modify `.gitignore`:

```gitignore
data/hermes_ui_home/
```

- [ ] **Step 4: Verify compose config**

Run:

```powershell
docker compose -f docker-compose.hermes.yml config --quiet
```

Expected: command exits 0.

- [ ] **Step 5: Commit**

```powershell
git add Dockerfile.hermes-ui docker-compose.hermes.yml .gitignore
git commit -m "feat: dockerize Hermes local web UI"
```

---

### Task 7: Documentation

**Files:**
- Modify: `docs/HermesAgentIntegration.md`

- [ ] **Step 1: Add UI usage section**

Append this section to `docs/HermesAgentIntegration.md`:

```markdown
## Local Hermes Web UI

The Docker compose file includes a local Hermes-backed browser UI.

Start the stack:

```powershell
docker compose -f docker-compose.hermes.yml up -d --build
```

Open:

```text
http://127.0.0.1:8787
```

The UI talks to Hermes inside the `hermes-ui` container. Hermes uses the OpenAI API key from `.env` and the internal MCP endpoint `http://lightrag-mcp:8765/mcp`.

The UI does not expose delete, clear, reset, or raw LightRAG query controls. Document ingest creates archived versions, and search goes through the latest-only snapshot workflow.
```

- [ ] **Step 2: Check docs diff**

Run:

```powershell
git diff -- docs/HermesAgentIntegration.md
```

Expected: diff only contains the new local UI section.

- [ ] **Step 3: Commit**

```powershell
git add docs/HermesAgentIntegration.md
git commit -m "docs: document Hermes local web UI"
```

---

### Task 8: Full Verification

**Files:**
- No code changes unless a verification failure identifies a bug.

- [ ] **Step 1: Run focused Python tests**

Run:

```powershell
python -m pytest tests/hermes_ui tests/mcp -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint on new backend**

Run:

```powershell
python -m ruff check hermes_ui tests/hermes_ui
```

Expected: no lint errors.

- [ ] **Step 3: Build and start Docker stack**

Run:

```powershell
docker compose -f docker-compose.hermes.yml up -d --build
```

Expected: `lightrag-api`, `lightrag-snapshot`, `lightrag-mcp`, and `hermes-ui` are running.

- [ ] **Step 4: Verify UI health through HTTP**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8787/api/status | Select-Object -ExpandProperty Content
```

Expected: JSON with `"state":"ok"` and MCP status.

- [ ] **Step 5: Verify browser loads**

Open `http://127.0.0.1:8787` and confirm:

- The page loads without blank screen.
- Status panel shows MCP state.
- Documents panel shows empty registry or stored versions.
- Chat composer is visible.
- No delete, clear, reset, or raw LightRAG query controls appear.

- [ ] **Step 6: Verify agent-to-MCP path**

Run:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8787/api/chat -ContentType application/json -Body '{"message":"Use lightrag-hermes to list the documents and report the count."}'
```

Expected: JSON with `state` set to `ok` and text reporting the current document count.

- [ ] **Step 7: Final git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree, branch ahead by the implementation commits.

---

## Self-Review

- Spec coverage: The plan covers Docker-local UI, Hermes-backed chat, document ingestion, latest snapshot build, status/registry views, localhost binding, no delete controls, and verification.
- Placeholder scan: No TBD/TODO/fill-in placeholders remain.
- Type consistency: `HermesUISettings`, route models, prompt builders, and MCP normalization names are consistent across tasks.
