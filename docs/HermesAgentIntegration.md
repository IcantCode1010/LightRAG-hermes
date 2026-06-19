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

`ingest_text_version` archives a new version under `./data/hermes_sources` and
rejects duplicate `{document_key}@{version_label}` files. It does not insert the
text into the live LightRAG index immediately, because indexing every historical
version would make old versions searchable.

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

## Tools

The initial adapter exposes:

- `adapter_status`
- `list_documents`
- `get_pipeline_status`
- `ingest_text_version`
- `build_latest_snapshot`
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
