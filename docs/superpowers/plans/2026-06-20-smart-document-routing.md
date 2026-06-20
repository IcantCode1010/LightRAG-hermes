# Smart Document Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route user questions to Hermes or LightRAG with deterministic document selection so document retrieval is reliable and latest-version-only.

**Architecture:** Add a small `hermes_ui.document_router` module that classifies a chat message as general chat, broad document search, or selected document search. The API will call this router before Hermes and execute LightRAG tools directly for document retrieval.

**Tech Stack:** Python, FastAPI, pytest, Ruff, existing LightRAG MCP tools.

---

### Task 1: Router Unit Tests

**Files:**
- Create: `tests/hermes_ui/test_document_router.py`

- [ ] **Step 1: Write failing tests**

```python
from hermes_ui.document_router import route_document_query


def test_general_chat_routes_to_hermes():
    route = route_document_query("hi", {"documents": []}, {})
    assert route.intent == "general"
    assert route.document_keys == []


def test_broad_document_question_routes_to_latest_all():
    route = route_document_query(
        "Summarize all indexed manuals",
        {"documents": [{"document_key": "boeing-manual", "latest_version_label": "2026-06-20-001"}]},
        {},
    )
    assert route.intent == "latest_all"
    assert route.document_keys == []


def test_specific_document_question_selects_matching_document():
    route = route_document_query(
        "What does the boeing b737 manual say about takeoff?",
        {
            "documents": [
                {"document_key": "boeing-b737-700-800-900-operations-manual", "latest_version_label": "2026-06-20-001"},
                {"document_key": "15-flight-controls", "latest_version_label": "2026-06-20-001"},
            ]
        },
        {},
    )
    assert route.intent == "latest_documents"
    assert route.document_keys == ["boeing-b737-700-800-900-operations-manual"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\hermes_ui\test_document_router.py -q`

Expected: fails because `hermes_ui.document_router` does not exist.

### Task 2: Router Implementation

**Files:**
- Create: `hermes_ui/document_router.py`
- Test: `tests/hermes_ui/test_document_router.py`

- [ ] **Step 1: Implement the router**

Create `RouteDecision` with `intent`, `document_keys`, `confidence`, and `reason`. Normalize text into tokens, score document keys by exact phrase and token overlap, and return:
- `general` for non-document messages
- `latest_documents` for confident document matches
- `latest_all` for document-related messages without a confident match

- [ ] **Step 2: Run router tests**

Run: `python -m pytest tests\hermes_ui\test_document_router.py -q`

Expected: all router tests pass.

### Task 3: API Integration Tests

**Files:**
- Modify: `tests/hermes_ui/test_api.py`

- [ ] **Step 1: Add tests for API routing**

Add tests proving:
- a specific Boeing question calls `query_latest_documents`
- a broad document question calls `query_latest_all`
- a greeting still calls Hermes and no LightRAG query

- [ ] **Step 2: Run focused tests to verify failures or regressions**

Run: `python -m pytest tests\hermes_ui\test_api.py -k "document_question or latest_all or greeting" -q`

Expected: tests fail until API imports and uses the router.

### Task 4: API Integration Implementation

**Files:**
- Modify: `hermes_ui/api.py`

- [ ] **Step 1: Replace local document matching with router**

Import `route_document_query`. In `/api/chat`, preserve inventory and availability direct responses, preserve explicit route handling, then use the router to decide whether to call Hermes, `query_latest_all`, or `query_latest_documents`.

- [ ] **Step 2: Preserve sanitized errors**

Keep `_normalize_chat_response(_normalize_lightrag_query_response(...))` around direct LightRAG calls.

- [ ] **Step 3: Run API and router tests**

Run: `python -m pytest tests\hermes_ui\test_document_router.py tests\hermes_ui\test_api.py -q`

Expected: all tests pass.

### Task 5: Verification and Delivery

**Files:**
- Existing Docker compose and UI container.

- [ ] **Step 1: Run full relevant tests**

Run: `python -m pytest tests\mcp tests\hermes_ui -q`

Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run: `python -m ruff check lightrag_mcp hermes_ui tests\mcp tests\hermes_ui`

Expected: no lint errors.

- [ ] **Step 3: Rebuild and restart UI**

Run:

```powershell
$env:LIGHTRAG_MCP_PORT='18765'
$env:PORT='19621'
docker compose --env-file C:\projects\LightRAG-hermes\.env -p lightrag-hermes-ui-test -f docker-compose.hermes.yml build hermes-ui
docker compose --env-file C:\projects\LightRAG-hermes\.env -p lightrag-hermes-ui-test -f docker-compose.hermes.yml up -d --no-deps hermes-ui
```

- [ ] **Step 4: Live verify**

POST `What does the Boeing B737 manual say about takeoff?` to `http://127.0.0.1:8787/api/chat` and verify the MCP logs show `/query`.

- [ ] **Step 5: Commit and push**

Run:

```powershell
git add hermes_ui/document_router.py hermes_ui/api.py tests/hermes_ui/test_document_router.py tests/hermes_ui/test_api.py docs/superpowers/plans/2026-06-20-smart-document-routing.md
git commit -m "feat: add smart document routing"
git push origin codex/hermes-local-web-ui
```
