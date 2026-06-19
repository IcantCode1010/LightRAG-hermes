import pytest

from lightrag_mcp.snapshots import (
    ActiveSnapshot,
    LatestSnapshotBuilder,
    SourceRegistry,
    read_active_snapshot,
    write_active_snapshot,
)


class FakeClient:
    def __init__(self, *, fail_on_file_source: str | None = None):
        self.fail_on_file_source = fail_on_file_source
        self.inserted: list[tuple[str, str]] = []

    async def insert_text(self, text: str, *, file_source: str | None = None):
        if file_source == self.fail_on_file_source:
            raise RuntimeError(f"insert failed for {file_source}")
        self.inserted.append((text, file_source or ""))
        return {"status": "success", "track_id": f"track-{len(self.inserted)}"}


@pytest.mark.asyncio
async def test_snapshot_builder_indexes_only_latest_versions(tmp_path):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_text_version("handbook", "2026-06-19-review", "Handbook", "old")
    registry.write_text_version("handbook", "2026-07-01-final", "Handbook", "new")
    registry.write_text_version("policy", "2026-06-20-draft", "Policy", "policy")
    active_path = tmp_path / "snapshots" / "active.json"
    client = FakeClient()

    builder = LatestSnapshotBuilder(registry, active_path)
    result = await builder.build_and_activate(
        snapshot_id="snapshot_20260701",
        base_url="http://lightrag-snapshot:9621",
        client=client,
    )

    assert result.snapshot == ActiveSnapshot(
        snapshot_id="snapshot_20260701",
        base_url="http://lightrag-snapshot:9621",
        latest_versions={
            "handbook": "2026-07-01-final",
            "policy": "2026-06-20-draft",
        },
    )
    assert [file_source for _, file_source in client.inserted] == [
        "handbook@2026-07-01-final.md",
        "policy@2026-06-20-draft.md",
    ]
    assert read_active_snapshot(active_path) == result.snapshot


@pytest.mark.asyncio
async def test_snapshot_builder_preserves_active_snapshot_on_failure(tmp_path):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_text_version("handbook", "2026-07-01-final", "Handbook", "new")
    active_path = tmp_path / "snapshots" / "active.json"
    previous = ActiveSnapshot(
        snapshot_id="snapshot_old",
        base_url="http://old:9621",
        latest_versions={"handbook": "2026-06-19-review"},
    )
    write_active_snapshot(active_path, previous)
    client = FakeClient(fail_on_file_source="handbook@2026-07-01-final.md")

    builder = LatestSnapshotBuilder(registry, active_path)

    with pytest.raises(RuntimeError, match="insert failed"):
        await builder.build_and_activate(
            snapshot_id="snapshot_20260701",
            base_url="http://lightrag-snapshot:9621",
            client=client,
        )

    assert read_active_snapshot(active_path) == previous
