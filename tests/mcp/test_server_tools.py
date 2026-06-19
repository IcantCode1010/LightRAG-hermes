from pathlib import Path

from lightrag_mcp.server import build_adapter_status, build_list_documents
from lightrag_mcp.snapshots import SourceRegistry


def test_build_adapter_status_exposes_safe_paths(tmp_path):
    result = build_adapter_status(
        base_url="http://lightrag-api:9621",
        source_dir=tmp_path / "sources",
        snapshot_dir=tmp_path / "snapshots",
    )

    assert result["status"] == "ok"
    assert result["base_url"] == "http://lightrag-api:9621"


def test_build_list_documents_marks_latest_versions(tmp_path: Path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "A", "one")
    registry.write_text_version("handbook", "2026-07-01-final", "A", "two")

    result = build_list_documents(registry)

    assert result["documents"][0]["document_key"] == "handbook"
    assert result["documents"][0]["latest_version_label"] == "2026-07-01-final"
    assert result["documents"][0]["versions"] == [
        "2026-06-19-review",
        "2026-07-01-final",
    ]
