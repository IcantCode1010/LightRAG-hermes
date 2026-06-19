# Hermes Agent LightRAG MCP Integration Design

## Goal

Integrate Nous Hermes Agent with LightRAG so Hermes can use LightRAG as a grounded knowledge backend. Hermes should be able to ingest new document versions, query the latest document set, inspect available documents, and check processing status. Hermes must not expose delete or clear operations.

## Requirements

- Hermes Agent integrates through MCP.
- The MCP server talks to the running LightRAG REST API rather than importing LightRAG in-process.
- The MCP server lives in this repository as a companion component, separate from the core `lightrag` package.
- Ingestion supports raw text and local files.
- Every ingested item requires a caller-provided `document_key`.
- Every version requires a caller-provided semantic `version_label`.
- `version_label` must be sortable by string comparison and begin with `YYYY-MM-DD-`.
- Duplicate `document_key + version_label` pairs are rejected.
- Queries must search only latest document versions.
- Previous versions may be stored, but normal Hermes queries must never search them.
- No user-facing MCP tool may delete documents, clear data, or clear caches.

## Non-Goals

- Do not build a full Hermes plugin in the first phase.
- Do not add a Hermes agent loop inside LightRAG.
- Do not expose archive or historical-version search in the first phase.
- Do not rely on post-filtering old versions out of query results after retrieval.
- Do not add destructive replacement behavior to the MCP server in the first phase.

## Architecture

The integration uses a small MCP adapter that sits between Hermes Agent and the existing LightRAG API server:

```text
Hermes Agent
  -> LightRAG MCP Server
    -> LightRAG REST API
      -> LightRAG pipeline, graph, vector, and document-status storage
```

The MCP server should be added as a companion package:

```text
lightrag_mcp/
  __init__.py
  server.py
  client.py
  config.py
  versioning.py
  snapshots.py
tests/
  mcp/
docs/
  HermesAgentIntegration.md
```

`client.py` owns the typed REST API client. `versioning.py` owns validation and filename parsing. `snapshots.py` owns latest-version source selection and active snapshot metadata. `server.py` exposes MCP tools and maps MCP inputs to client/snapshot operations.

LightRAG's current API server uses one configured workspace per running instance. Snapshot workspaces therefore cannot be selected per request through the existing API. The first implementation should treat each snapshot as a separately configured LightRAG API instance or add an explicit workspace-management API before attempting dynamic snapshot creation. The MCP server's active snapshot pointer should store the active LightRAG base URL as well as the snapshot identity.

## Version Identity

Every source version is identified by:

```text
document_key
version_label
```

The source name encodes both fields:

```text
{document_key}@{version_label}.{ext}
```

Examples:

```text
handbook@2026-06-19-legal-review.md
contract-alpha@2026-07-02-vendor-redline.pdf
research-notes@2026-07-15-post-demo-cleanup.txt
```

`document_key` and `version_label` must reject path separators, `@`, path traversal, control characters, and empty values. Allowed characters are letters, numbers, `_`, `-`, and `.`. `version_label` must start with a date prefix matching `YYYY-MM-DD-`.

Latest version selection is done by sorting `version_label` values for a given `document_key` and selecting the maximum string value.

## Latest-Only Search

Old versions must not influence retrieval. The design uses latest-only snapshot workspaces rather than post-filtering results from a mixed-version index.

When a new version is ingested:

1. Validate `document_key`, `version_label`, and input source.
2. Reject the request if the exact `document_key + version_label` already exists in source storage or inferred document status.
3. Store the new source version in source/archive storage.
4. Determine the latest source version for every `document_key`.
5. Build a new LightRAG workspace snapshot containing only those latest versions. With the existing API, this means indexing into a dedicated LightRAG server instance configured for that snapshot workspace or working directory.
6. Mark the completed snapshot as active by recording its snapshot ID and query base URL.
7. Route all normal query tools to the active snapshot's base URL.

The snapshot build may be slower than incremental replacement, but it satisfies strict latest-only retrieval without hidden delete or destructive replacement operations.

Snapshot activation must be atomic from the MCP server's point of view. If a snapshot build fails, the previous active snapshot remains active.

## MCP Tools

### `ingest_text_version`

Inputs:

- `document_key`
- `version_label`
- `title`
- `text`
- optional metadata

Behavior:

- Writes a text source file using the versioned source-name convention.
- Triggers latest-only snapshot rebuild.
- Returns version identity, build status, and active snapshot information.

### `ingest_file_version`

Inputs:

- `document_key`
- `version_label`
- `file_path`
- optional metadata

Behavior:

- Validates that the file path is local and readable.
- Copies the file into source/archive storage using the versioned source-name convention.
- Triggers latest-only snapshot rebuild.
- Returns version identity, build status, and active snapshot information.

### `query_documents`

Inputs:

- `query`
- `scope`
- optional `document_keys`
- optional query parameters such as mode, top-k, and include references

Supported scopes:

- `global_latest`: query the latest version of every document key.
- `document_latest`: query latest versions for selected document keys.

The first implementation should avoid archive query scopes. If selected-document filtering cannot be enforced inside LightRAG retrieval, the MCP server should build/query a selected latest-only snapshot or reject the scoped query with a clear unsupported-scope error rather than searching old or unrelated documents.

### `list_documents`

Returns:

- document keys
- latest version label
- available version labels
- active snapshot membership
- status summary

### `list_document_versions`

Inputs:

- `document_key`

Returns all known version labels for that document key and marks the latest label.

### `get_pipeline_status`

Returns current LightRAG pipeline and snapshot build state.

## Data Flow

### Text Ingest

```text
Hermes tool call
  -> validate document key and version label
  -> write source archive file
  -> build latest-only source set
  -> create or target a dedicated LightRAG snapshot API instance
  -> upload latest sources to that snapshot instance
  -> wait/poll until documents are processed or return track IDs
  -> activate snapshot after success by recording its query base URL
```

### Query

```text
Hermes tool call
  -> read active snapshot pointer
  -> route query to active latest-only LightRAG base URL
  -> return response, references, and snapshot metadata
```

## Configuration

The MCP server uses environment variables:

```text
LIGHTRAG_MCP_BASE_URL=http://localhost:9621
LIGHTRAG_MCP_API_KEY=
LIGHTRAG_MCP_SOURCE_DIR=./hermes_sources
LIGHTRAG_MCP_SNAPSHOT_DIR=./hermes_snapshots
LIGHTRAG_MCP_ACTIVE_SNAPSHOT_FILE=./hermes_snapshots/active.json
LIGHTRAG_MCP_DEFAULT_QUERY_MODE=mix
```

The first implementation may use filesystem source/snapshot metadata. It should not require a separate database. `active.json` should include at least the active snapshot ID, active LightRAG query base URL, and the latest `document_key -> version_label` map.

## Error Handling

- Duplicate `document_key + version_label`: reject with a clear duplicate error.
- Invalid key or label: reject before writing files.
- LightRAG unavailable: return an MCP tool error with base URL and operation context.
- Snapshot build failure: keep previous active snapshot unchanged.
- Query requested before any active snapshot exists: return a clear "no active snapshot" error.
- Unsupported scoped query: reject rather than broadening search silently.

## Testing

Backend tests should cover:

- document key validation
- version label validation
- duplicate detection
- filename parsing and latest-version selection
- active snapshot pointer behavior
- REST client request construction
- snapshot base URL selection
- MCP tool schemas and non-destructive tool list
- query behavior when no active snapshot exists
- failure behavior that preserves the previous active snapshot

Integration tests can use a fake LightRAG REST server first. End-to-end tests against a real local LightRAG server can be added after the adapter shape is stable.

## Documentation

Add `docs/HermesAgentIntegration.md` with:

- how to run the LightRAG API server
- how to run the MCP server
- how to configure Hermes Agent to use the MCP server
- examples for text ingest, file ingest, list documents, and latest-only query
- explicit note that delete, clear, and historical search are not exposed
