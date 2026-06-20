# Hermes Agent Integration

This repository exposes LightRAG to Nous Hermes Agent through a Dockerized MCP
adapter.

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

The Compose stack also starts an internal-only `lightrag-snapshot` service at:

```text
http://lightrag-snapshot:9621
```

That service is not published to the host. The MCP adapter uses it as the
default `build_latest_snapshot` target.

## Local Hermes Web UI

Start the Hermes Web UI stack with:

```bash
docker compose -f docker-compose.hermes.yml up -d --build
```

Open the UI at:

```text
http://127.0.0.1:8787
```

The browser talks to Hermes inside the `hermes-ui` container. That container
uses `OPENAI_API_KEY` from `.env` and connects to the internal MCP endpoint at:

```text
http://lightrag-mcp:8765/mcp
```

The Web UI does not provide delete, clear, reset, or raw LightRAG query
controls. Ingest creates archived document versions, and search runs through
the latest-only snapshot workflow described below.

The agent identity is stored in the bundled soul file:

```text
hermes_ui/soul.md
```

The `hermes-ui` service loads that file into chat prompts before per-request
routing instructions. Override it with `HERMES_SOUL_FILE` if you want to mount a
custom local soul file. Do not put secrets or unstable runtime state in this
file.

By default, the UI is bound to localhost only at `127.0.0.1:8787`. Its persisted
Hermes UI home is stored under:

```text
./data/hermes_ui_home
```

## Safety Boundary

The MCP adapter runs in a container and talks to LightRAG over the Docker Compose
network. It mounts only these repo-local data directories:

```text
./data/hermes_sources
./data/hermes_snapshots
./data/hermes_snapshot
```

Do not mount broad home directories into the MCP container. File ingestion should
copy specific files into the controlled source archive before indexing.

## Version Convention

Document versions are stored as:

```text
{document_key}@{YYYY-MM-DD-label}.{extension}
```

Examples:

```text
handbook@2026-06-19-review.md
handbook@2026-07-01-final.md
```

The latest version is selected by sortable `version_label` order. Older versions
remain in the source archive, but search workflows should target the active
latest-version snapshot only.

## Ingestion and Query Contract

`ingest_text_version` and `ingest_file_version` archive new versions under
`./data/hermes_sources` and reject duplicate
`{document_key}@{version_label}` files. They do not insert the content into the
live LightRAG index immediately, because indexing every historical version would
make old versions searchable.

Text-like latest sources (`.md`, `.txt`, `.csv`, `.json`, `.log`) are inserted
through LightRAG text ingestion when a latest snapshot is built. PDF and Office
latest sources remain as files in the archive and are sent to LightRAG through
`/documents/upload`, so LightRAG performs the document processing.

Latest-only query tools require an active snapshot pointer at:

```text
./data/hermes_snapshots/active.json
```

That file points the adapter to the LightRAG endpoint that contains only the
latest versions. Until a latest-only snapshot has been built and activated,
`query_latest_all` and `query_latest_documents` will refuse to run.

Use `build_latest_snapshot` to index the latest archived version for every
document key into a clean LightRAG snapshot endpoint. The tool activates the
snapshot only after every latest source has been accepted by that endpoint. If
any insert fails, the previous `active.json` pointer is left unchanged.

Use `snapshot_status` or the Web UI Snapshot tab before building. It reports the
number of archived latest document keys, the active snapshot pointer, and whether
the target snapshot endpoint is empty enough to build safely. The Web UI disables
the build action while the target contains indexed documents.

Before inserting, the adapter checks the target snapshot endpoint for existing
documents. If any are present, `build_latest_snapshot` refuses to run. This
prevents accidentally mixing a new latest-only generation with a previous
snapshot. The adapter does not clear or delete snapshot storage.

The target `snapshot_base_url` must point to a fresh or otherwise latest-only
LightRAG storage workspace. Do not point it at an index that already contains
historical versions.

The bundled `lightrag-snapshot` service uses separate repo-local storage under:

```text
./data/hermes_snapshot/rag_storage
./data/hermes_snapshot/inputs
```

To preserve latest-only search, use that service as a clean snapshot target. If
you intentionally rebuild the active snapshot from scratch, stop the stack first
and rotate or archive `./data/hermes_snapshot` outside the MCP tools before
starting a new clean snapshot service.

Use the bundled PowerShell helper to rotate snapshot storage without deleting it:

```powershell
docker compose -f docker-compose.hermes.yml down
powershell -ExecutionPolicy Bypass -File scripts\rotate-hermes-snapshot.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File scripts\rotate-hermes-snapshot.ps1
docker compose -f docker-compose.hermes.yml up --build
```

The helper moves `./data/hermes_snapshot` into
`./data/hermes_snapshot_archive/hermes_snapshot_<timestamp>` and recreates empty
`rag_storage` and `inputs` directories.

## Tools

The initial adapter exposes:

- `adapter_status`
- `list_documents`
- `get_pipeline_status`
- `ingest_file_version`
- `ingest_text_version`
- `build_latest_snapshot`
- `snapshot_status`
- `query_latest_all`
- `query_latest_documents`

Document deletion, data clearing, and cache clearing are not exposed.

## Hermes Agent Configuration

Configure Hermes Agent to connect to the MCP adapter at:

```text
http://127.0.0.1:8765/mcp
```

Use the Hermes Agent MCP UI or configuration file for your installed Hermes
version.
