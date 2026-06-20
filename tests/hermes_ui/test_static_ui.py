from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[2] / "hermes_ui" / "static"


def test_documents_panel_exposes_file_loader_for_ingest_form() -> None:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="document-file"' in html
    assert 'accept=".txt,.md,.markdown,.csv,.json,.log,text/*"' in html
    assert "Load text file" in html
    assert "loadDocumentFile" in js
    assert "readAsText" in js

