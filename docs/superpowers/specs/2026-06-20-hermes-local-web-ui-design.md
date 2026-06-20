# Hermes Local Web UI Design

## Goal

Build a polished local browser UI for the Dockerized Hermes + LightRAG workflow in this repo. The UI should make document version ingestion, latest-only snapshot building, and agent querying accessible without sending users through the raw LightRAG WebUI.

The UI must preserve the project safety rules:

- Documents are added or versioned, never deleted.
- Duplicate `(document_key, version_label)` pairs are rejected.
- Queries go through Hermes and the `lightrag-hermes` MCP tools.
- Search targets only the latest-version snapshot, not archived older versions.
- Services bind to localhost only.

## Architecture

Add a new Docker service, `hermes-ui`, to the existing Hermes compose setup. It will serve a local web app and a small backend API.

```text
Browser
  -> hermes-ui container on 127.0.0.1:8787
      -> backend API
          -> Hermes CLI/session runtime
              -> lightrag-hermes MCP server
                  -> latest-only LightRAG snapshot service
```

The `hermes-ui` service should be part of `docker-compose.hermes.yml` and share only the minimum required configuration with the host and existing Docker network. It should not expose raw LightRAG query controls.

## Runtime Model

The backend adapter will call Hermes in non-interactive mode for chat turns:

```powershell
hermes chat --query "<message>" --quiet
```

Hermes remains responsible for model routing, tool calling, and MCP usage. The UI backend does not reimplement MCP protocol logic for normal user chat.

For status and document registry views, the backend may call low-risk MCP tools directly when that gives clearer structured data:

- `adapter_status`
- `list_documents`
- `get_pipeline_status`

All ingest, snapshot, and query actions visible to users should still be phrased and routed as Hermes tasks so the UI remains an agent UI rather than a direct LightRAG admin console.

## User Experience

The UI should be a practical work surface, not a marketing page. First screen should be the app itself.

Primary regions:

- Left sidebar: service status, active model, active snapshot status, document count.
- Main panel: Hermes chat with message history and tool/result states.
- Right panel or tabbed drawer: document ingestion and registry controls.

Core views:

- Chat
- Documents
- Snapshots
- Status

The design should be quiet, dense, and operational. Avoid decorative hero sections. Use compact cards only for repeated records or bounded tools.

## Document Ingestion

The document ingest form should collect:

- `document_key`
- `version_label`
- `title`
- `text`

The version label convention shown in the UI should be sortable:

```text
vYYYY.MM.DD.NNN
```

Example:

```text
v2026.06.20.001
```

The UI should make the rule obvious through labels and validation messages, not by offering delete or overwrite actions.

Expected behavior:

- Submit sends Hermes a task to call `ingest_text_version`.
- Duplicate versions surface as clear rejected states.
- Successful ingest updates the document registry.
- Old versions remain visible in the registry but are marked archived/non-searchable.

## Snapshot Workflow

The snapshot panel should provide:

- Build latest snapshot button.
- Snapshot ID input with a generated default such as `snapshot-YYYY.MM.DD.NNN`.
- Active snapshot summary.
- Latest versions included in the active snapshot.

Snapshot build should call Hermes with a task to run `build_latest_snapshot`. The UI should explain through concise status text that building a snapshot may use embedding/model API credits.

The UI must not provide any button that clears or deletes LightRAG storage. If rotation is needed later, keep it as an explicit maintenance command outside the primary user workflow.

## Query Workflow

All question answering goes through the Hermes chat panel.

Supported query intents:

- Ask across all latest documents.
- Ask against selected document keys.

For selected-document queries, the UI should let users select document keys from the registry and include that selection in the Hermes prompt so Hermes uses `query_latest_documents`.

The raw LightRAG WebUI remains useful for debugging but should not be linked as the main chat path.

## Backend API

The backend should expose a small internal API for the frontend:

- `GET /api/status`
- `GET /api/documents`
- `POST /api/chat`
- `POST /api/ingest`
- `POST /api/snapshots/build`

The backend owns process execution, timeout handling, and response normalization. The frontend should not shell out or know about host paths.

Responses should be JSON and include structured states:

- `ok`
- `pending`
- `rejected`
- `error`

## Safety

The UI service must bind only to localhost:

```text
127.0.0.1:8787
```

No delete, clear, reset, or destructive storage controls should be present.

Secrets must not be displayed. Status can show provider names and redacted key presence only.

The backend should apply timeouts to Hermes calls and show long-running state for snapshot builds.

## Testing

Minimum implementation checks:

- Unit tests for request validation and command construction.
- Backend smoke tests for `/api/status` and `/api/documents`.
- UI build check.
- Docker compose config check.
- Browser smoke test at `http://127.0.0.1:8787`.
- End-to-end test that Hermes can still call `list_documents` through the MCP server.

## Open Scope Boundaries

This design does not include:

- Remote hosting.
- Multi-user auth.
- Raw LightRAG querying.
- Deleting documents or old versions.
- A full replacement for Hermes' own dashboard.

Those can be revisited after the local workflow is stable.
