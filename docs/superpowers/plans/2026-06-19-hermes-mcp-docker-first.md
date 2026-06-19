# Hermes MCP Docker-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized Hermes Agent MCP adapter that talks to LightRAG through REST and keeps local-machine exposure constrained by Docker Compose.

**Architecture:** Start with a Docker Compose deployment boundary, then add a small `lightrag_mcp` Python package. The MCP adapter runs in its own container, stores version/source metadata in mounted repo-local data volumes, and calls LightRAG API containers over the internal Compose network.

**Tech Stack:** Python 3.12, official MCP Python SDK `mcp.server.fastmcp`, httpx, pytest, Docker, Docker Compose, existing LightRAG API Dockerfile.

---

## File Structure

- Create `lightrag_mcp/__init__.py`
  - Package marker and version export.
- Create `lightrag_mcp/config.py`
  - Environment parsing for MCP host/port, LightRAG base URL, API key, and mounted data paths.
- Create `lightrag_mcp/versioning.py`
  - Validation and parsing for `document_key`, `version_label`, and `{document_key}@{version_label}.{ext}` source names.
- Create `lightrag_mcp/client.py`
  - Typed async REST client for LightRAG health, pipeline status, text insert, file upload, and query calls.
- Create `lightrag_mcp/snapshots.py`
  - Filesystem source registry, latest-version selection, and active snapshot pointer handling.
- Create `lightrag_mcp/server.py`
  - FastMCP server and tool registration.
- Create `Dockerfile.mcp`
  - Container image for the MCP adapter.
- Create `docker-compose.hermes.yml`
  - Dockerized local deployment with `lightrag-api` and `lightrag-mcp`.
- Create `docs/HermesAgentIntegration.md`
  - Local Docker deployment and Hermes Agent configuration instructions.
- Add tests under `tests/mcp/`
  - Unit tests for config, versioning, snapshots, client request construction, and tool registration.

## Task 1: Add Docker MCP Skeleton

**Files:**
- Create: `lightrag_mcp/__init__.py`
- Create: `lightrag_mcp/config.py`
- Create: `lightrag_mcp/server.py`
- Create: `Dockerfile.mcp`
- Modify: `pyproject.toml`
- Test: `tests/mcp/test_config.py`
- Test: `tests/mcp/test_server_import.py`

- [ ] **Step 1: Write config tests**

Create `tests/mcp/test_config.py`:

```python
from pathlib import Path

from lightrag_mcp.config import MCPConfig


def test_config_reads_container_defaults(monkeypatch):
    monkeypatch.delenv("LIGHTRAG_MCP_BASE_URL", raising=False)
    monkeypatch.delenv("LIGHTRAG_MCP_SOURCE_DIR", raising=False)
    monkeypatch.delenv("LIGHTRAG_MCP_SNAPSHOT_DIR", raising=False)

    config = MCPConfig.from_env()

    assert config.base_url == "http://lightrag-api:9621"
    assert config.source_dir == Path("/app/data/hermes_sources")
    assert config.snapshot_dir == Path("/app/data/hermes_snapshots")
    assert config.active_snapshot_file == Path(
        "/app/data/hermes_snapshots/active.json"
    )


def test_config_allows_host_overrides(monkeypatch, tmp_path):
    source_dir = tmp_path / "sources"
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setenv("LIGHTRAG_MCP_BASE_URL", "http://127.0.0.1:9621")
    monkeypatch.setenv("LIGHTRAG_MCP_API_KEY", "secret")
    monkeypatch.setenv("LIGHTRAG_MCP_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("LIGHTRAG_MCP_SNAPSHOT_DIR", str(snapshot_dir))

    config = MCPConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9621"
    assert config.api_key == "secret"
    assert config.source_dir == source_dir
    assert config.snapshot_dir == snapshot_dir
```

- [ ] **Step 2: Write server import test**

Create `tests/mcp/test_server_import.py`:

```python
from lightrag_mcp.server import mcp


def test_server_declares_expected_name():
    assert mcp.name == "lightrag-hermes"
```

- [ ] **Step 3: Run tests to confirm failure**

Run:

```bash
python -m pytest tests/mcp/test_config.py tests/mcp/test_server_import.py -q
```

Expected: fails because `lightrag_mcp` does not exist.

- [ ] **Step 4: Add MCP dependencies**

In `pyproject.toml`, add a new optional dependency group:

```toml
mcp = [
    "mcp>=1.7.1,<2.0.0",
    "httpx>=0.28.1",
]
```

Add MCP to the test extra:

```toml
test = [
    "lightrag-hku[api,mcp]",
    "pytest>=8.4.2",
    "pytest-asyncio>=1.2.0",
    "pre-commit",
    "ruff",
]
```

- [ ] **Step 5: Create package and config**

Create `lightrag_mcp/__init__.py`:

```python
"""Hermes Agent MCP adapter for LightRAG."""

__version__ = "0.1.0"
```

Create `lightrag_mcp/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MCPConfig:
    base_url: str
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
```

- [ ] **Step 6: Create minimal MCP server**

Create `lightrag_mcp/server.py`:

```python
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lightrag_mcp.config import MCPConfig


config = MCPConfig.from_env()
mcp = FastMCP("lightrag-hermes", host=config.host, port=config.port)


@mcp.tool()
def adapter_status() -> dict[str, str]:
    """Return adapter configuration that is safe to expose to Hermes."""
    return {
        "status": "ok",
        "base_url": config.base_url,
        "source_dir": str(config.source_dir),
        "snapshot_dir": str(config.snapshot_dir),
    }


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Add MCP Dockerfile**

Create `Dockerfile.mcp`:

```dockerfile
# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml setup.py uv.lock ./
COPY lightrag/ ./lightrag/
COPY lightrag_mcp/ ./lightrag_mcp/

RUN --mount=type=cache,target=/root/.local/share/uv \
    uv sync --frozen --no-dev --extra mcp --no-editable

ENV PATH=/app/.venv/bin:$PATH
ENV LIGHTRAG_MCP_HOST=0.0.0.0
ENV LIGHTRAG_MCP_PORT=8765

EXPOSE 8765

ENTRYPOINT ["python", "-m", "lightrag_mcp.server"]
```

- [ ] **Step 8: Run tests**

Run:

```bash
python -m pytest tests/mcp/test_config.py tests/mcp/test_server_import.py -q
python -m ruff check lightrag_mcp tests/mcp
```

Expected: both commands pass.

- [ ] **Step 9: Commit**

Run:

```bash
git add pyproject.toml Dockerfile.mcp lightrag_mcp tests/mcp
git commit -m "feat: add Hermes MCP container skeleton"
```

## Task 2: Add Docker Compose Deployment Boundary

**Files:**
- Create: `docker-compose.hermes.yml`
- Create: `env.hermes.example`
- Modify: `.gitignore`
- Test: `tests/mcp/test_compose_config.py`

- [ ] **Step 1: Write Compose tests**

Create `tests/mcp/test_compose_config.py`:

```python
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
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
python -m pytest tests/mcp/test_compose_config.py -q
```

Expected: fails because `docker-compose.hermes.yml` does not exist.

- [ ] **Step 3: Add Compose file**

Create `docker-compose.hermes.yml`:

```yaml
services:
  lightrag-api:
    build:
      context: .
      dockerfile: Dockerfile
    image: lightrag-hermes-api:local
    env_file:
      - .env
    ports:
      - "${LIGHTRAG_HOST_BIND:-127.0.0.1}:${PORT:-9621}:9621"
    volumes:
      - ./data/rag_storage:/app/data/rag_storage
      - ./data/inputs:/app/data/inputs
      - ./data/prompts:/app/data/prompts
      - ./.env:/app/.env:ro
    environment:
      HOST: "0.0.0.0"
      PORT: "9621"
      WORKING_DIR: "/app/data/rag_storage"
      INPUT_DIR: "/app/data/inputs"
      PROMPT_DIR: "/app/data/prompts"
    networks:
      - hermes-net
    restart: unless-stopped

  lightrag-mcp:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    image: lightrag-hermes-mcp:local
    env_file:
      - env.hermes
    ports:
      - "${LIGHTRAG_MCP_HOST_BIND:-127.0.0.1}:${LIGHTRAG_MCP_PORT:-8765}:8765"
    volumes:
      - ./data/hermes_sources:/app/data/hermes_sources
      - ./data/hermes_snapshots:/app/data/hermes_snapshots
    environment:
      LIGHTRAG_MCP_BASE_URL: "http://lightrag-api:9621"
      LIGHTRAG_MCP_SOURCE_DIR: "/app/data/hermes_sources"
      LIGHTRAG_MCP_SNAPSHOT_DIR: "/app/data/hermes_snapshots"
      LIGHTRAG_MCP_ACTIVE_SNAPSHOT_FILE: "/app/data/hermes_snapshots/active.json"
      LIGHTRAG_MCP_HOST: "0.0.0.0"
      LIGHTRAG_MCP_PORT: "8765"
    depends_on:
      - lightrag-api
    networks:
      - hermes-net
    restart: unless-stopped

networks:
  hermes-net:
    driver: bridge
```

- [ ] **Step 4: Add env example**

Create `env.hermes.example`:

```env
LIGHTRAG_MCP_API_KEY=
LIGHTRAG_MCP_DEFAULT_QUERY_MODE=mix
LIGHTRAG_MCP_HOST_BIND=127.0.0.1
LIGHTRAG_MCP_PORT=8765
LIGHTRAG_HOST_BIND=127.0.0.1
```

- [ ] **Step 5: Ignore local Hermes env**

Add this line to `.gitignore`:

```gitignore
env.hermes
```

- [ ] **Step 6: Run Compose and test checks**

Run:

```bash
python -m pytest tests/mcp/test_compose_config.py -q
docker compose -f docker-compose.hermes.yml config
```

Expected: pytest passes, and Docker Compose prints the resolved config with no errors.

- [ ] **Step 7: Commit**

Run:

```bash
git add docker-compose.hermes.yml env.hermes.example .gitignore tests/mcp/test_compose_config.py
git commit -m "feat: add Docker Compose boundary for Hermes MCP"
```

## Task 3: Implement Version Validation

**Files:**
- Create: `lightrag_mcp/versioning.py`
- Test: `tests/mcp/test_versioning.py`

- [ ] **Step 1: Write versioning tests**

Create `tests/mcp/test_versioning.py`:

```python
import pytest

from lightrag_mcp.versioning import (
    VersionedSource,
    build_source_name,
    latest_by_document_key,
    parse_source_name,
    validate_document_key,
    validate_version_label,
)


def test_validate_document_key_allows_safe_key():
    assert validate_document_key("contract-alpha_1.2") == "contract-alpha_1.2"


@pytest.mark.parametrize("value", ["", "../x", "a/b", "a@b", "two words"])
def test_validate_document_key_rejects_unsafe_values(value):
    with pytest.raises(ValueError):
        validate_document_key(value)


def test_validate_version_label_requires_sortable_date_prefix():
    assert validate_version_label("2026-06-19-legal-review") == (
        "2026-06-19-legal-review"
    )


@pytest.mark.parametrize("value", ["legal-review", "2026/06/19-x", "2026-06-19 x"])
def test_validate_version_label_rejects_unsortable_or_unsafe_values(value):
    with pytest.raises(ValueError):
        validate_version_label(value)


def test_build_and_parse_source_name():
    name = build_source_name("handbook", "2026-06-19-legal-review", ".md")

    assert name == "handbook@2026-06-19-legal-review.md"
    assert parse_source_name(name) == VersionedSource(
        document_key="handbook",
        version_label="2026-06-19-legal-review",
        extension=".md",
        source_name=name,
    )


def test_latest_by_document_key_uses_string_sorting():
    sources = [
        parse_source_name("handbook@2026-06-19-review.md"),
        parse_source_name("handbook@2026-07-01-final.md"),
        parse_source_name("policy@2026-06-01-draft.txt"),
    ]

    latest = latest_by_document_key(sources)

    assert latest["handbook"].version_label == "2026-07-01-final"
    assert latest["policy"].version_label == "2026-06-01-draft"
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
python -m pytest tests/mcp/test_versioning.py -q
```

Expected: fails because `lightrag_mcp.versioning` does not exist.

- [ ] **Step 3: Implement versioning**

Create `lightrag_mcp/versioning.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass


SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class VersionedSource:
    document_key: str
    version_label: str
    extension: str
    source_name: str


def _validate_safe_token(value: str, field_name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    if "@" in value or "/" in value or "\\" in value or ".." in value:
        raise ValueError(f"{field_name} contains unsafe path characters")
    if not SAFE_TOKEN_RE.fullmatch(value):
        raise ValueError(
            f"{field_name} may only contain letters, numbers, '.', '_', and '-'"
        )
    return value


def validate_document_key(value: str) -> str:
    return _validate_safe_token(value, "document_key")


def validate_version_label(value: str) -> str:
    value = _validate_safe_token(value, "version_label")
    if not VERSION_RE.fullmatch(value):
        raise ValueError("version_label must start with YYYY-MM-DD-")
    return value


def build_source_name(document_key: str, version_label: str, extension: str) -> str:
    key = validate_document_key(document_key)
    label = validate_version_label(version_label)
    ext = extension if extension.startswith(".") else f".{extension}"
    ext_token = _validate_safe_token(ext.lstrip("."), "extension")
    return f"{key}@{label}.{ext_token}"


def parse_source_name(source_name: str) -> VersionedSource:
    if "@" not in source_name:
        raise ValueError("source name must contain '@'")
    document_key, rest = source_name.split("@", 1)
    if "." not in rest:
        raise ValueError("source name must include a file extension")
    version_label, extension = rest.rsplit(".", 1)
    normalized = build_source_name(document_key, version_label, extension)
    return VersionedSource(
        document_key=document_key,
        version_label=version_label,
        extension=f".{extension}",
        source_name=normalized,
    )


def latest_by_document_key(
    sources: list[VersionedSource],
) -> dict[str, VersionedSource]:
    latest: dict[str, VersionedSource] = {}
    for source in sources:
        current = latest.get(source.document_key)
        if current is None or source.version_label > current.version_label:
            latest[source.document_key] = source
    return latest
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/mcp/test_versioning.py -q
python -m ruff check lightrag_mcp/versioning.py tests/mcp/test_versioning.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lightrag_mcp/versioning.py tests/mcp/test_versioning.py
git commit -m "feat: validate Hermes document versions"
```

## Task 4: Implement Source Registry and Active Snapshot Metadata

**Files:**
- Create: `lightrag_mcp/snapshots.py`
- Test: `tests/mcp/test_snapshots.py`

- [ ] **Step 1: Write snapshot tests**

Create `tests/mcp/test_snapshots.py`:

```python
import json

import pytest

from lightrag_mcp.snapshots import (
    ActiveSnapshot,
    SourceRegistry,
    read_active_snapshot,
    write_active_snapshot,
)


def test_registry_rejects_duplicate_version(tmp_path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "Title", "one")

    with pytest.raises(ValueError, match="already exists"):
        registry.write_text_version("handbook", "2026-06-19-review", "Title", "two")


def test_registry_lists_latest_versions(tmp_path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "Title", "one")
    registry.write_text_version("handbook", "2026-07-01-final", "Title", "two")
    registry.write_text_version("policy", "2026-06-20-draft", "Title", "three")

    latest = registry.latest_sources()

    assert latest["handbook"].version_label == "2026-07-01-final"
    assert latest["policy"].version_label == "2026-06-20-draft"


def test_active_snapshot_round_trip(tmp_path):
    path = tmp_path / "active.json"
    snapshot = ActiveSnapshot(
        snapshot_id="snapshot-20260619",
        base_url="http://lightrag-snapshot-20260619:9621",
        latest_versions={"handbook": "2026-07-01-final"},
    )

    write_active_snapshot(path, snapshot)

    assert json.loads(path.read_text())["snapshot_id"] == "snapshot-20260619"
    assert read_active_snapshot(path) == snapshot
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
python -m pytest tests/mcp/test_snapshots.py -q
```

Expected: fails because `lightrag_mcp.snapshots` does not exist.

- [ ] **Step 3: Implement snapshots**

Create `lightrag_mcp/snapshots.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from lightrag_mcp.versioning import (
    VersionedSource,
    build_source_name,
    latest_by_document_key,
    parse_source_name,
)


@dataclass(frozen=True)
class ActiveSnapshot:
    snapshot_id: str
    base_url: str
    latest_versions: dict[str, str]


class SourceRegistry:
    def __init__(self, source_dir: Path):
        self.source_dir = source_dir

    def _ensure_dir(self) -> None:
        self.source_dir.mkdir(parents=True, exist_ok=True)

    def write_text_version(
        self, document_key: str, version_label: str, title: str, text: str
    ) -> Path:
        self._ensure_dir()
        source_name = build_source_name(document_key, version_label, ".md")
        target = self.source_dir / source_name
        if target.exists():
            raise ValueError(f"document version already exists: {source_name}")
        body = f"# {title.strip() or document_key}\n\n{text}"
        target.write_text(body, encoding="utf-8")
        return target

    def list_sources(self) -> list[VersionedSource]:
        self._ensure_dir()
        sources: list[VersionedSource] = []
        for path in self.source_dir.iterdir():
            if path.is_file():
                try:
                    sources.append(parse_source_name(path.name))
                except ValueError:
                    continue
        return sources

    def latest_sources(self) -> dict[str, VersionedSource]:
        return latest_by_document_key(self.list_sources())


def write_active_snapshot(path: Path, snapshot: ActiveSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(asdict(snapshot), indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_active_snapshot(path: Path) -> ActiveSnapshot | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ActiveSnapshot(
        snapshot_id=str(data["snapshot_id"]),
        base_url=str(data["base_url"]),
        latest_versions=dict(data.get("latest_versions", {})),
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/mcp/test_snapshots.py -q
python -m ruff check lightrag_mcp/snapshots.py tests/mcp/test_snapshots.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lightrag_mcp/snapshots.py tests/mcp/test_snapshots.py
git commit -m "feat: track Hermes source snapshots"
```

## Task 5: Implement LightRAG REST Client

**Files:**
- Create: `lightrag_mcp/client.py`
- Test: `tests/mcp/test_client.py`

- [ ] **Step 1: Write REST client tests**

Create `tests/mcp/test_client.py`:

```python
import httpx
import pytest

from lightrag_mcp.client import LightRAGClient


@pytest.mark.asyncio
async def test_client_sends_api_key_header():
    seen_headers = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = LightRAGClient("http://lightrag-api:9621", "secret", http=http)
        result = await client.health()

    assert result == {"status": "ok"}
    assert seen_headers["x-api-key"] == "secret"


@pytest.mark.asyncio
async def test_query_posts_expected_payload():
    seen_json = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_json.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"response": "answer", "references": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = LightRAGClient("http://lightrag-api:9621", "", http=http)
        result = await client.query("What changed?", mode="mix")

    assert seen_json["query"] == "What changed?"
    assert seen_json["mode"] == "mix"
    assert result["response"] == "answer"
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
python -m pytest tests/mcp/test_client.py -q
```

Expected: fails because `lightrag_mcp.client` does not exist.

- [ ] **Step 3: Implement REST client**

Create `lightrag_mcp/client.py`:

```python
from __future__ import annotations

from typing import Any

import httpx


class LightRAGClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        *,
        http: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = http

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        close_client = self._http is None
        http = self._http or httpx.AsyncClient(timeout=60)
        try:
            response = await http.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        finally:
            if close_client:
                await http.aclose()

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def pipeline_status(self) -> dict[str, Any]:
        return await self._request("GET", "/documents/pipeline_status")

    async def query(self, query: str, *, mode: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/query",
            json={"query": query, "mode": mode, "include_references": True},
        )

    async def insert_text(self, text: str) -> dict[str, Any]:
        return await self._request("POST", "/documents/text", json={"text": text})
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/mcp/test_client.py -q
python -m ruff check lightrag_mcp/client.py tests/mcp/test_client.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lightrag_mcp/client.py tests/mcp/test_client.py
git commit -m "feat: add LightRAG REST client for MCP"
```

## Task 6: Add First MCP Tools

**Files:**
- Modify: `lightrag_mcp/server.py`
- Test: `tests/mcp/test_server_tools.py`

- [ ] **Step 1: Write tool tests**

Create `tests/mcp/test_server_tools.py`:

```python
from pathlib import Path

from lightrag_mcp.server import build_adapter_status, build_list_documents
from lightrag_mcp.snapshots import SourceRegistry


def test_build_adapter_status_exposes_safe_paths(tmp_path):
    result = build_adapter_status(
        base_url="http://lightrag-api:9621",
        source_dir=tmp_path / "sources",
        snapshot_dir=tmp_path / "snapshots",
    )

    assert result["status"] == "ok"
    assert result["base_url"] == "http://lightrag-api:9621"


def test_build_list_documents_marks_latest_versions(tmp_path: Path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "A", "one")
    registry.write_text_version("handbook", "2026-07-01-final", "A", "two")

    result = build_list_documents(registry)

    assert result["documents"][0]["document_key"] == "handbook"
    assert result["documents"][0]["latest_version_label"] == "2026-07-01-final"
    assert result["documents"][0]["versions"] == [
        "2026-06-19-review",
        "2026-07-01-final",
    ]
```

- [ ] **Step 2: Run test to confirm failure**

Run:

```bash
python -m pytest tests/mcp/test_server_tools.py -q
```

Expected: fails because helper functions are not defined.

- [ ] **Step 3: Implement tool helpers and tools**

Replace `lightrag_mcp/server.py` with:

```python
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from lightrag_mcp.client import LightRAGClient
from lightrag_mcp.config import MCPConfig
from lightrag_mcp.snapshots import SourceRegistry, read_active_snapshot


config = MCPConfig.from_env()
mcp = FastMCP("lightrag-hermes", host=config.host, port=config.port)


def build_adapter_status(
    *, base_url: str, source_dir: Path, snapshot_dir: Path
) -> dict[str, str]:
    return {
        "status": "ok",
        "base_url": base_url,
        "source_dir": str(source_dir),
        "snapshot_dir": str(snapshot_dir),
    }


def build_list_documents(registry: SourceRegistry) -> dict[str, list[dict[str, object]]]:
    sources = registry.list_sources()
    latest = registry.latest_sources()
    document_keys = sorted({source.document_key for source in sources})
    documents: list[dict[str, object]] = []
    for key in document_keys:
        versions = sorted(
            source.version_label for source in sources if source.document_key == key
        )
        documents.append(
            {
                "document_key": key,
                "latest_version_label": latest[key].version_label,
                "versions": versions,
            }
        )
    return {"documents": documents}


@mcp.tool()
def adapter_status() -> dict[str, str]:
    """Return adapter configuration that is safe to expose to Hermes."""
    return build_adapter_status(
        base_url=config.base_url,
        source_dir=config.source_dir,
        snapshot_dir=config.snapshot_dir,
    )


@mcp.tool()
def list_documents() -> dict[str, list[dict[str, object]]]:
    """List known document keys and their stored version labels."""
    return build_list_documents(SourceRegistry(config.source_dir))


@mcp.tool()
async def get_pipeline_status() -> dict[str, object]:
    """Return pipeline status from the active LightRAG endpoint."""
    active = read_active_snapshot(config.active_snapshot_file)
    base_url = active.base_url if active else config.base_url
    return await LightRAGClient(base_url, config.api_key).pipeline_status()


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/mcp/test_server_import.py tests/mcp/test_server_tools.py -q
python -m ruff check lightrag_mcp/server.py tests/mcp/test_server_tools.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lightrag_mcp/server.py tests/mcp/test_server_tools.py
git commit -m "feat: expose initial Hermes MCP tools"
```

## Task 7: Add Docker Usage Documentation

**Files:**
- Create: `docs/HermesAgentIntegration.md`
- Test: manual docs review

- [ ] **Step 1: Add integration guide**

Create `docs/HermesAgentIntegration.md`:

```markdown
# Hermes Agent Integration

This repository exposes LightRAG to Nous Hermes Agent through a Dockerized MCP adapter.

## Local Docker Deployment

Copy the Hermes MCP environment template:

```bash
cp env.hermes.example env.hermes
```

Start the local services:

```bash
docker compose -f docker-compose.hermes.yml up --build
```

The default host bindings are:

- LightRAG API/WebUI: `http://127.0.0.1:9621`
- LightRAG MCP adapter: `http://127.0.0.1:8765`

## Safety Boundary

The MCP adapter runs in a container and talks to LightRAG over the Docker Compose network. It mounts only these repo-local data directories:

```text
./data/hermes_sources
./data/hermes_snapshots
```

Do not mount broad home directories into the MCP container. File ingestion should copy specific files into the controlled source archive before indexing.

## Tools

The initial adapter exposes:

- `adapter_status`
- `list_documents`
- `get_pipeline_status`

Document deletion, data clearing, and cache clearing are not exposed.

## Hermes Agent Configuration

Configure Hermes Agent to connect to the MCP adapter at:

```text
http://127.0.0.1:8765/mcp
```

Use the Hermes Agent MCP UI or configuration file for your installed Hermes version.
```

- [ ] **Step 2: Verify docs and status**

Run:

```bash
python -m pytest tests/mcp -q
docker compose -f docker-compose.hermes.yml config
git status --short
```

Expected: pytest and Compose config pass; git status shows only the docs file as unstaged before staging.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/HermesAgentIntegration.md
git commit -m "docs: document Dockerized Hermes MCP setup"
```

## Task 8: End-to-End Container Smoke Test

**Files:**
- No source files required.

- [ ] **Step 1: Build images**

Run:

```bash
docker compose -f docker-compose.hermes.yml build lightrag-mcp
```

Expected: image `lightrag-hermes-mcp:local` builds successfully.

- [ ] **Step 2: Start MCP service**

Run:

```bash
docker compose -f docker-compose.hermes.yml up -d lightrag-mcp
```

Expected: `lightrag-mcp` starts. If `lightrag-api` is also started because of `depends_on`, that is acceptable.

- [ ] **Step 3: Inspect logs**

Run:

```bash
docker compose -f docker-compose.hermes.yml logs --tail=100 lightrag-mcp
```

Expected: logs show the MCP server listening on port `8765` and no Python tracebacks.

- [ ] **Step 4: Stop services**

Run:

```bash
docker compose -f docker-compose.hermes.yml down
```

Expected: containers stop without removing mounted data directories.

- [ ] **Step 5: Commit smoke-test note**

If the smoke test required no source changes, do not create an empty commit. Record the commands and outcomes in the final handoff instead.

