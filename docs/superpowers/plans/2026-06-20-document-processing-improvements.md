# Document Processing Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hermes UI the clear frontend for document ingestion while LightRAG remains the backend processing and retrieval engine, with better validation, status visibility, automatic snapshot flow, and failed-document recovery.

**Architecture:** Keep the current versioned source registry and latest-only LightRAG snapshot model. Add a document processing status layer in MCP/Hermes UI that reports registry state, active snapshot state, failed processing reasons, chunk counts, and rebuild readiness without exposing native LightRAG UI as a user workflow.

**Tech Stack:** Python FastAPI, MCP tool server, LightRAG HTTP API, React/Vite TypeScript frontend, pytest, Ruff.

---

## File Structure

- Modify `lightrag_mcp/server.py`: add a richer `document_processing_status` tool and expose processing metadata through `list_documents`.
- Modify `lightrag_mcp/snapshots.py`: preserve failed-source details and make snapshot build results easier for the UI to render.
- Modify `hermes_ui/mcp_client.py`: normalize processing-status payloads.
- Modify `hermes_ui/api.py`: add `/api/documents/status`, optional auto-build endpoint behavior, and clearer ingest responses.
- Modify `hermes_ui/frontend/src/types.ts`: add document processing status types.
- Modify `hermes_ui/frontend/src/components/DocumentsPanel.tsx`: show upload validation, processing status, failed reasons, and replacement-version action.
- Modify `hermes_ui/frontend/src/components/SnapshotPanel.tsx`: show degraded/current/ready states clearly and list failed sources.
- Modify `hermes_ui/frontend/src/App.tsx`: fetch processing status with the existing refresh loop.
- Modify `tests/mcp/test_server_tools.py`, `tests/mcp/test_snapshot_builder.py`, `tests/hermes_ui/test_api.py`, `tests/hermes_ui/test_mcp_client.py`, and `tests/hermes_ui/test_static_ui.py`: cover the new behavior.

---

## Task 1: Backend Processing Status Tool

**Files:**
- Modify: `lightrag_mcp/server.py`
- Test: `tests/mcp/test_server_tools.py`

- [ ] **Step 1: Write failing tests for processing status**

Add tests that create three registry documents: one searchable latest, one failed latest, and one archived old version. Assert a new helper `build_document_processing_status(...)` returns counts and per-document status.

```python
def test_build_document_processing_status_reports_searchable_failed_and_archived(tmp_path: Path):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_file_version("airbus", "2026-06-20-001", "airbus.pdf", b"x")
    registry.write_file_version("boeing", "2026-06-20-001", "boeing.pdf", b"x")
    registry.write_file_version("boeing", "2026-06-19-001", "boeing.pdf", b"x")
    active = ActiveSnapshot(
        snapshot_id="snapshot-2026-06-20.openai-006",
        base_url="http://snapshot-api:9621",
        latest_versions={"airbus": "2026-06-20-001"},
    )
    target_documents = [
        {"file_path": "airbus@2026-06-20-001.pdf", "status": "processed", "chunks_count": 42},
        {
            "file_path": "boeing@2026-06-20-001.pdf",
            "status": "failed",
            "chunks_count": None,
            "error_msg": "extracted no usable text",
        },
    ]

    result = build_document_processing_status(
        registry,
        active_snapshot=active,
        target_documents=target_documents,
    )

    assert result["summary"] == {
        "registered_document_count": 2,
        "registered_version_count": 3,
        "searchable_latest_count": 1,
        "failed_latest_count": 1,
        "unsearchable_latest_count": 1,
    }
    assert result["documents"][0]["document_key"] == "airbus"
    assert result["documents"][0]["latest"]["state"] == "searchable"
    assert result["documents"][0]["latest"]["chunks_count"] == 42
    assert result["documents"][1]["document_key"] == "boeing"
    assert result["documents"][1]["latest"]["state"] == "failed"
    assert result["documents"][1]["latest"]["error"] == "extracted no usable text"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
python -m pytest tests\mcp\test_server_tools.py::test_build_document_processing_status_reports_searchable_failed_and_archived -q
```

Expected: fail because `build_document_processing_status` does not exist.

- [ ] **Step 3: Implement status helper and MCP tool**

Add `build_document_processing_status(registry, active_snapshot, target_documents)` to `lightrag_mcp/server.py`. It should parse `target_documents[*].file_path` with `parse_source_name`, join by document key/version label, and produce states:

```python
state = "searchable" if active_version == source.version_label and processed else "failed" if failed else "registered"
```

Add MCP tool:

```python
@mcp.tool()
async def document_processing_status() -> dict[str, object]:
    """Return registry, snapshot, and LightRAG processing state for Hermes UI."""
    client = LightRAGClient(config.snapshot_base_url, config.api_key)
    target_documents = (await client.documents()).get("documents") or []
    return build_document_processing_status(
        SourceRegistry(config.source_dir),
        active_snapshot=read_active_snapshot(config.active_snapshot_file),
        target_documents=target_documents,
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests\mcp\test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add lightrag_mcp/server.py tests/mcp/test_server_tools.py
git commit -m "feat: expose document processing status"
```

---

## Task 2: Hermes API Status Endpoint

**Files:**
- Modify: `hermes_ui/mcp_client.py`
- Modify: `hermes_ui/api.py`
- Test: `tests/hermes_ui/test_mcp_client.py`
- Test: `tests/hermes_ui/test_api.py`

- [ ] **Step 1: Write failing MCP client normalization test**

Add a test for `normalize_document_processing_status(...)` that preserves `summary`, `documents`, `state`, `chunks_count`, and `error`, while defaulting missing arrays safely.

```python
def test_normalize_document_processing_status_preserves_status_payload() -> None:
    result = normalize_document_processing_status(
        {
            "summary": {"searchable_latest_count": 1, "failed_latest_count": 1},
            "documents": [
                {
                    "document_key": "boeing",
                    "latest": {
                        "version_label": "2026-06-20-001",
                        "state": "failed",
                        "chunks_count": None,
                        "error": "extracted no usable text",
                    },
                    "versions": [],
                }
            ],
        }
    )

    assert result["summary"]["failed_latest_count"] == 1
    assert result["documents"][0]["latest"]["state"] == "failed"
```

- [ ] **Step 2: Write failing API endpoint test**

Add a test that `/api/documents/status` calls `document_processing_status`.

```python
def test_documents_status_returns_processing_status(tmp_path, monkeypatch):
    calls = []

    async def fake_call_tool(mcp_url, tool_name, args=None):
        calls.append((mcp_url, tool_name, args))
        return {"summary": {"searchable_latest_count": 2}, "documents": []}

    monkeypatch.setattr(hermes_ui.api, "call_tool", fake_call_tool)
    client = _client(tmp_path)

    response = client.get("/api/documents/status")

    assert response.status_code == 200
    assert response.json()["summary"]["searchable_latest_count"] == 2
    assert calls == [("http://mcp.local:8765/mcp", "document_processing_status", None)]
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\hermes_ui\test_mcp_client.py tests\hermes_ui\test_api.py::test_documents_status_returns_processing_status -q
```

Expected: fail because endpoint and normalizer do not exist.

- [ ] **Step 4: Implement normalizer and endpoint**

In `hermes_ui/mcp_client.py`, add `normalize_document_processing_status(payload)`. In `hermes_ui/api.py`, add:

```python
@app.get("/api/documents/status")
async def api_documents_status() -> dict[str, Any]:
    return await call_tool(settings.mcp_url, "document_processing_status")
```

- [ ] **Step 5: Run focused tests**

```powershell
python -m pytest tests\hermes_ui\test_mcp_client.py tests\hermes_ui\test_api.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add hermes_ui/mcp_client.py hermes_ui/api.py tests/hermes_ui/test_mcp_client.py tests/hermes_ui/test_api.py
git commit -m "feat: add document processing status api"
```

---

## Task 3: Safer Upload Validation and Response

**Files:**
- Modify: `hermes_ui/api.py`
- Modify: `lightrag_mcp/server.py`
- Test: `tests/hermes_ui/test_api.py`
- Test: `tests/mcp/test_server_tools.py`

- [ ] **Step 1: Write failing tests for empty and tiny PDFs**

Add API tests that reject obviously invalid uploads before they enter the registry:

```python
def test_ingest_file_rejects_tiny_pdf(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/api/ingest-file",
        data={"document_key": "upload-check", "version_label": "2026-06-20-001"},
        files={"file": ("upload-check.pdf", b"%PDF-1.4\n", "application/pdf")},
    )

    assert response.status_code == 422
    assert "PDF is too small" in response.json()["detail"]
```

- [ ] **Step 2: Run test and verify failure**

```powershell
python -m pytest tests\hermes_ui\test_api.py::test_ingest_file_rejects_tiny_pdf -q
```

Expected: fail because the current route accepts tiny PDFs.

- [ ] **Step 3: Implement conservative validation**

In `hermes_ui/api.py`, before calling `ingest_file_version`, reject:
- empty content
- `.pdf` uploads under 1 KB
- filenames without extensions

Keep this conservative. Do not parse PDFs in the UI API.

- [ ] **Step 4: Improve ingest response shape**

Return a clear response from `/api/ingest-file`:

```python
{
    "status": "stored",
    "source_name": "...",
    "searchable": False,
    "next_step": "Build the latest snapshot to process this version."
}
```

- [ ] **Step 5: Run focused tests**

```powershell
python -m pytest tests\hermes_ui\test_api.py tests\mcp\test_server_tools.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add hermes_ui/api.py lightrag_mcp/server.py tests/hermes_ui/test_api.py tests/mcp/test_server_tools.py
git commit -m "feat: validate document uploads before registry storage"
```

---

## Task 4: Auto-Build Latest Snapshot After Upload

**Files:**
- Modify: `hermes_ui/api.py`
- Modify: `hermes_ui/frontend/src/components/DocumentsPanel.tsx`
- Test: `tests/hermes_ui/test_api.py`
- Test: `tests/hermes_ui/test_static_ui.py`

- [ ] **Step 1: Write failing API test for optional auto-build**

Add support for a form field `build_snapshot=true`.

```python
def test_ingest_file_can_trigger_snapshot_build(tmp_path, monkeypatch):
    calls = []

    async def fake_call_tool(mcp_url, tool_name, args=None):
        calls.append((tool_name, args))
        if tool_name == "ingest_file_version":
            return {"status": "stored", "source_name": "manual@2026-06-20-001.pdf"}
        return {"status": "active", "indexed_sources": ["manual@2026-06-20-001.pdf"]}

    monkeypatch.setattr(hermes_ui.api, "call_tool", fake_call_tool)
    client = _client(tmp_path)

    response = client.post(
        "/api/ingest-file",
        data={
            "document_key": "manual",
            "version_label": "2026-06-20-001",
            "build_snapshot": "true",
        },
        files={"file": ("manual.pdf", b"%PDF-1.4\n" + b"x" * 2048, "application/pdf")},
    )

    assert response.status_code == 200
    assert calls[0][0] == "ingest_file_version"
    assert calls[1][0] == "build_latest_snapshot"
```

- [ ] **Step 2: Run test and verify failure**

```powershell
python -m pytest tests\hermes_ui\test_api.py::test_ingest_file_can_trigger_snapshot_build -q
```

Expected: fail because `build_snapshot` is ignored.

- [ ] **Step 3: Implement backend auto-build option**

In `/api/ingest-file`, add `build_snapshot: bool = Form(False)`. If true, call `build_latest_snapshot` after storage with an ID like:

```python
snapshot_id = f"snapshot-{datetime.now(timezone.utc).strftime('%Y-%m-%d.%H%M%S')}"
```

If build fails because target needs rotation, return a response with `snapshot_build.status = "blocked"` and the error text.

- [ ] **Step 4: Add UI checkbox**

In `DocumentsPanel.tsx`, add a checkbox:

```tsx
<label className="inline-option">
  <input checked={buildSnapshot} onChange={(event) => setBuildSnapshot(event.target.checked)} type="checkbox" />
  <span>Build searchable snapshot after upload</span>
</label>
```

Pass `build_snapshot` in `FormData`.

- [ ] **Step 5: Run frontend static test**

Add a static UI test asserting `build_snapshot` and “Build searchable snapshot after upload” exist.

Run:

```powershell
python -m pytest tests\hermes_ui\test_static_ui.py tests\hermes_ui\test_api.py -q
```

- [ ] **Step 6: Commit**

```powershell
git add hermes_ui/api.py hermes_ui/frontend/src/components/DocumentsPanel.tsx tests/hermes_ui/test_api.py tests/hermes_ui/test_static_ui.py
git commit -m "feat: optionally build snapshot after upload"
```

---

## Task 5: Processing Status UI

**Files:**
- Modify: `hermes_ui/frontend/src/types.ts`
- Modify: `hermes_ui/frontend/src/App.tsx`
- Modify: `hermes_ui/frontend/src/components/DocumentsPanel.tsx`
- Test: `tests/hermes_ui/test_static_ui.py`

- [ ] **Step 1: Add TypeScript types**

In `types.ts`, add:

```ts
export type DocumentProcessingStatus = {
  summary?: {
    registered_document_count?: number;
    registered_version_count?: number;
    searchable_latest_count?: number;
    failed_latest_count?: number;
    unsearchable_latest_count?: number;
  };
  documents?: Array<{
    document_key?: string;
    latest?: {
      version_label?: string;
      state?: "searchable" | "failed" | "registered" | "archived";
      chunks_count?: number | null;
      error?: string;
    };
  }>;
};
```

- [ ] **Step 2: Fetch status in App**

In `App.tsx`, fetch `/api/documents/status` in `refresh()` and pass the payload to `DocumentsPanel`.

- [ ] **Step 3: Render status summary and failed reasons**

In `DocumentsPanel.tsx`, add summary badges:
- Registered
- Searchable
- Failed
- Needs snapshot

For failed documents, render:

```tsx
<Badge tone="error">failed</Badge>
<p className="note">{latest.error}</p>
```

- [ ] **Step 4: Add replacement-version affordance**

For failed latest documents, add a button that fills the form:

```tsx
<Button type="button" onClick={() => prepareReplacement(documentKey)}>
  Upload replacement version
</Button>
```

`prepareReplacement` should set `documentKey`, clear selected file/text, and set a new sortable version label using `nextPatchLabel`.

- [ ] **Step 5: Static UI tests**

Add tests for:
- `/api/documents/status`
- `Upload replacement version`
- `failed`
- `searchable`

Run:

```powershell
python -m pytest tests\hermes_ui\test_static_ui.py -q
```

- [ ] **Step 6: Commit**

```powershell
git add hermes_ui/frontend/src/types.ts hermes_ui/frontend/src/App.tsx hermes_ui/frontend/src/components/DocumentsPanel.tsx tests/hermes_ui/test_static_ui.py
git commit -m "feat: show document processing status in ui"
```

---

## Task 6: Snapshot Panel Clarity

**Files:**
- Modify: `hermes_ui/frontend/src/types.ts`
- Modify: `hermes_ui/frontend/src/components/SnapshotPanel.tsx`
- Test: `tests/hermes_ui/test_static_ui.py`

- [ ] **Step 1: Expand snapshot types**

In `types.ts`, add fields:

```ts
latest_versions?: Record<string, string>;
active_snapshot?: { snapshot_id?: string; latest_versions?: Record<string, string> } | null;
```

- [ ] **Step 2: Make degraded state explicit**

In `SnapshotPanel.tsx`, set tone:

```ts
const targetTone: Tone = snapshot?.state === "current" ? "ok" : snapshot?.state === "degraded" ? "warn" : canBuild ? "ok" : "warn";
```

Render a concise explanation for `degraded`:

```tsx
{snapshot?.state === "degraded" && (
  <p className="note">Some latest documents are searchable. Failed documents need a replacement version.</p>
)}
```

- [ ] **Step 3: Static UI test**

Assert the panel contains `degraded` handling text.

Run:

```powershell
python -m pytest tests\hermes_ui\test_static_ui.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add hermes_ui/frontend/src/types.ts hermes_ui/frontend/src/components/SnapshotPanel.tsx tests/hermes_ui/test_static_ui.py
git commit -m "feat: clarify degraded snapshot state"
```

---

## Task 7: End-to-End Docker Verification

**Files:**
- No code files unless verification exposes a bug.

- [ ] **Step 1: Rebuild services**

Run:

```powershell
$env:LIGHTRAG_MCP_PORT='18765'
$env:PORT='19621'
docker compose --env-file C:\projects\LightRAG-hermes\.env -p lightrag-hermes-ui-test -f docker-compose.hermes.yml up -d --build
```

- [ ] **Step 2: Verify API state**

Run:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8787/api/documents/status' | ConvertTo-Json -Depth 20
Invoke-RestMethod -Uri 'http://127.0.0.1:8787/api/snapshots/status' | ConvertTo-Json -Depth 20
```

Expected:
- document processing status returns a summary and documents array
- snapshot status returns `current`, `degraded`, or `ready` with a clear reason

- [ ] **Step 3: Verify upload validation**

Run a tiny PDF upload and confirm HTTP 422:

```powershell
# Use TestClient coverage as primary verification; manual curl is optional if needed.
```

- [ ] **Step 4: Verify real query still works**

Run:

```powershell
$body = @{ message = 'What does the Boeing B737 manual say about takeoff?' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8787/api/chat' -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 20
```

Expected: response includes a Boeing manual reference.

- [ ] **Step 5: Run full tests and lint**

```powershell
python -m pytest tests\mcp tests\hermes_ui -q
python -m ruff check lightrag_mcp hermes_ui tests\mcp tests\hermes_ui
```

- [ ] **Step 6: Commit verification fixes if any**

Only commit if code changed during verification.

---

## Self-Review

**Spec coverage:** The plan keeps Hermes/Hermes UI as the frontend, LightRAG as the backend engine, and improves document processing through validation, processing status, optional auto-build, degraded state visibility, and failed-document recovery.

**Placeholder scan:** No task depends on unspecified behavior. Each task names files, tests, commands, and expected outcomes.

**Type consistency:** Backend status names use `summary`, `documents`, `latest`, `state`, `chunks_count`, and `error`; frontend types mirror those names.

