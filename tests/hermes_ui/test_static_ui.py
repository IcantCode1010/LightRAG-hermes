from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[2] / "hermes_ui" / "static"


def test_documents_panel_exposes_file_loader_for_ingest_form() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="document-file"' in html
    assert ".pdf" in html
    assert ".docx" in html
    assert "Choose file" in html
    assert "loadDocumentFile" in js
    assert "/api/ingest-file" in js
    assert "FormData" in js
    assert "readAsText" in js


def test_snapshot_panel_exposes_readiness_status() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="snapshot-status"' in html
    assert "/api/snapshots/status" in js
    assert "renderSnapshotStatus" in js


def test_maintenance_panel_exposes_snapshot_archive_cleanup() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'data-tab="maintenance"' in html
    assert 'id="maintenance-tab"' in html
    assert 'id="snapshot-archives"' in html
    assert "/api/maintenance/snapshot-archives" in js
    assert "deleteSnapshotArchive" in js
    assert "confirmation" in js


def test_chat_flow_exposes_activity_indicator_and_scheduled_scroll() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'id="chat-activity"' in html
    assert 'aria-live="polite"' in html
    assert "setChatActivity" in js
    assert "scrollMessagesToBottom" in js
    assert "requestAnimationFrame" in js
    assert ".chat-activity" in css
    assert "typing-dots" in html
    assert "typing-dot" in html
    assert "@keyframes typingPulse" in css
