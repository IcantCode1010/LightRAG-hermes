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
