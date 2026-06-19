import json

import pytest

from lightrag_mcp.snapshots import (
    ActiveSnapshot,
    SourceRegistry,
    read_active_snapshot,
    write_active_snapshot,
)


def test_registry_rejects_duplicate_version(tmp_path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "Title", "one")

    with pytest.raises(ValueError, match="already exists"):
        registry.write_text_version("handbook", "2026-06-19-review", "Title", "two")


def test_registry_lists_latest_versions(tmp_path):
    registry = SourceRegistry(tmp_path)
    registry.write_text_version("handbook", "2026-06-19-review", "Title", "one")
    registry.write_text_version("handbook", "2026-07-01-final", "Title", "two")
    registry.write_text_version("policy", "2026-06-20-draft", "Title", "three")

    latest = registry.latest_sources()

    assert latest["handbook"].version_label == "2026-07-01-final"
    assert latest["policy"].version_label == "2026-06-20-draft"


def test_active_snapshot_round_trip(tmp_path):
    path = tmp_path / "active.json"
    snapshot = ActiveSnapshot(
        snapshot_id="snapshot-20260619",
        base_url="http://lightrag-snapshot-20260619:9621",
        latest_versions={"handbook": "2026-07-01-final"},
    )

    write_active_snapshot(path, snapshot)

    assert json.loads(path.read_text())["snapshot_id"] == "snapshot-20260619"
    assert read_active_snapshot(path) == snapshot
