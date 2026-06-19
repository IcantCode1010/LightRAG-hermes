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

## Safety Boundary

The MCP adapter runs in a container and talks to LightRAG over the Docker Compose
network. It mounts only these repo-local data directories:

```text
./data/hermes_sources
./data/hermes_snapshots
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

Use the Hermes Agent MCP UI or configuration file for your installed Hermes
version.
