# Hermes Snapshot Archive Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe Hermes UI maintenance surface for listing and deleting archived snapshot folders only.

**Architecture:** The Hermes UI backend owns this maintenance feature because it already serves local UI controls and can be given a narrow Docker volume. The backend exposes list/delete endpoints constrained to direct child directories under `HERMES_SNAPSHOT_ARCHIVE_DIR`; the frontend adds a Maintenance tab with exact-name confirmation.

**Tech Stack:** Python FastAPI, pathlib/shutil filesystem operations, Docker Compose bind mounts, static HTML/CSS/JS, pytest, ruff.

---

### Task 1: Backend Archive Store

**Files:**
- Modify: `hermes_ui/config.py`
- Create: `hermes_ui/snapshot_archives.py`
- Test: `tests/hermes_ui/test_snapshot_archives.py`

- [ ] **Step 1: Write failing tests**

Add tests that create archive folders under a temp archive root, assert they are listed with name/path metadata, assert direct child deletion removes only the requested archive, and assert path traversal names are rejected.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests\hermes_ui\test_snapshot_archives.py`
Expected: fail because `hermes_ui.snapshot_archives` does not exist.

- [ ] **Step 3: Implement archive store**

Add `snapshot_archive_dir` to `HermesUISettings`. Create `list_snapshot_archives(root)` and `delete_snapshot_archive(root, archive_name, confirmation)` with direct-child path validation, exact-name confirmation, and `shutil.rmtree` for directories only.

- [ ] **Step 4: Verify backend store**

Run: `python -m pytest tests\hermes_ui\test_snapshot_archives.py`
Expected: pass.

### Task 2: Maintenance API and Docker Mount

**Files:**
- Modify: `hermes_ui/api.py`
- Modify: `docker-compose.hermes.yml`
- Test: `tests/hermes_ui/test_api.py`
- Test: `tests/mcp/test_compose_config.py`

- [ ] **Step 1: Write failing tests**

Add API tests for `GET /api/maintenance/snapshot-archives` and `DELETE /api/maintenance/snapshot-archives/{archive_name}`. Add a compose test that `hermes-ui` only mounts `./data/hermes_snapshot_archive` to `/app/data/hermes_snapshot_archive`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests\hermes_ui\test_api.py tests\mcp\test_compose_config.py`
Expected: fail because the routes and mount do not exist.

- [ ] **Step 3: Implement API and Compose mount**

Wire the routes to the archive store. Configure `HERMES_SNAPSHOT_ARCHIVE_DIR=/app/data/hermes_snapshot_archive` and mount only `./data/hermes_snapshot_archive:/app/data/hermes_snapshot_archive`.

- [ ] **Step 4: Verify API and mount**

Run: `python -m pytest tests\hermes_ui\test_api.py tests\mcp\test_compose_config.py`
Expected: pass.

### Task 3: Maintenance UI

**Files:**
- Modify: `hermes_ui/static/index.html`
- Modify: `hermes_ui/static/app.js`
- Modify: `hermes_ui/static/styles.css`
- Test: `tests/hermes_ui/test_static_ui.py`

- [ ] **Step 1: Write failing static UI test**

Assert a Maintenance tab exists, calls `/api/maintenance/snapshot-archives`, and includes exact-name confirmation behavior.

- [ ] **Step 2: Run static UI test to verify failure**

Run: `python -m pytest tests\hermes_ui\test_static_ui.py`
Expected: fail because the Maintenance tab does not exist.

- [ ] **Step 3: Implement UI**

Add a Maintenance tab. Render archived snapshot rows with delete controls. Require typing the exact archive name before enabling delete. Refresh the list after deletion.

- [ ] **Step 4: Verify UI test**

Run: `python -m pytest tests\hermes_ui\test_static_ui.py`
Expected: pass.

### Task 4: Full Verification and Commit

**Files:**
- Modify: `docs/HermesAgentIntegration.md`

- [ ] **Step 1: Update docs**

Document that the Maintenance tab deletes archived snapshot folders only and cannot delete active snapshots or source archives.

- [ ] **Step 2: Run full verification**

Run: `python -m pytest tests\mcp tests\hermes_ui`
Expected: all pass.

Run: `python -m ruff check hermes_ui tests\hermes_ui tests\mcp`
Expected: all pass.

- [ ] **Step 3: Docker and browser verification**

Run the Hermes compose stack with build and verify the Maintenance tab can list and delete a test archive folder created under `data/hermes_snapshot_archive`.

- [ ] **Step 4: Commit and push**

Commit message: `feat: add snapshot archive maintenance UI`.
