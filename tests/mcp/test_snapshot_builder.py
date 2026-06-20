import pytest

from lightrag_mcp.snapshots import (
    ActiveSnapshot,
    LatestSnapshotBuilder,
    SourceRegistry,
    read_active_snapshot,
    write_active_snapshot,
)


class FakeClient:
    def __init__(
        self,
        *,
        fail_on_file_source: str | None = None,
        existing_documents: list[dict[str, object]] | None = None,
        processed_documents: list[dict[str, object]] | None = None,
    ):
        self.fail_on_file_source = fail_on_file_source
        self.existing_documents = existing_documents or []
        self.processed_documents = processed_documents
        self.inserted: list[tuple[str, str]] = []
        self.uploaded: list[tuple[str, str]] = []

    async def documents(self):
        if self.existing_documents and not self.inserted and not self.uploaded:
            return {"documents": self.existing_documents}
        if self.processed_documents is not None and (self.inserted or self.uploaded):
            return {"documents": self.processed_documents}
        documents = [
            _processed_document(_canonical_source_name(file_source))
            for _, file_source in [*self.inserted, *self.uploaded]
        ]
        return {"documents": documents}

    async def pipeline_status(self):
        return {"busy": False}

    async def insert_text(self, text: str, *, file_source: str | None = None):
        if file_source == self.fail_on_file_source:
            raise RuntimeError(f"insert failed for {file_source}")
        self.inserted.append((text, file_source or ""))
        return {"status": "success", "track_id": f"track-{len(self.inserted)}"}

    async def insert_file(self, path, *, file_source: str | None = None):
        source = file_source or path.name
        if source == self.fail_on_file_source:
            raise RuntimeError(f"insert failed for {source}")
        self.uploaded.append((path.name, source))
        return {"status": "success", "track_id": f"upload-{len(self.uploaded)}"}


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
async def test_snapshot_builder_uploads_latest_binary_files(tmp_path):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_file_version(
        "contract",
        "2026-06-19-draft",
        "contract.pdf",
        b"%PDF-1.4\nold",
    )
    registry.write_file_version(
        "contract",
        "2026-07-01-final",
        "contract.pdf",
        b"%PDF-1.4\nnew",
    )
    active_path = tmp_path / "snapshots" / "active.json"
    client = FakeClient()

    result = await LatestSnapshotBuilder(registry, active_path).build_and_activate(
        snapshot_id="snapshot_20260701",
        base_url="http://lightrag-snapshot:9621",
        client=client,
    )

    assert client.inserted == []
    assert client.uploaded == [
        ("contract@2026-07-01-final.pdf", "contract@2026-07-01-final.[-!].pdf")
    ]
    assert result.indexed_sources == ["contract@2026-07-01-final.pdf"]
    assert result.snapshot.latest_versions == {"contract": "2026-07-01-final"}


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


@pytest.mark.asyncio
async def test_snapshot_builder_refuses_non_empty_target(tmp_path):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_text_version("handbook", "2026-07-01-final", "Handbook", "new")
    active_path = tmp_path / "snapshots" / "active.json"
    previous = ActiveSnapshot(
        snapshot_id="snapshot_old",
        base_url="http://old:9621",
        latest_versions={"handbook": "2026-06-19-review"},
    )
    write_active_snapshot(active_path, previous)
    client = FakeClient(
        existing_documents=[
            {
                "id": "old-doc",
                "file_path": "handbook@2026-06-19-review.md",
            }
        ]
    )

    builder = LatestSnapshotBuilder(registry, active_path)

    with pytest.raises(RuntimeError, match="snapshot endpoint is not empty"):
        await builder.build_and_activate(
            snapshot_id="snapshot_20260701",
            base_url="http://lightrag-snapshot:9621",
            client=client,
        )

    assert client.inserted == []
    assert read_active_snapshot(active_path) == previous


@pytest.mark.asyncio
async def test_snapshot_builder_preserves_active_snapshot_when_latest_fails_processing(
    tmp_path,
):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_file_version(
        "contract",
        "2026-07-01-final",
        "contract.pdf",
        b"%PDF-1.4\nnew",
    )
    active_path = tmp_path / "snapshots" / "active.json"
    previous = ActiveSnapshot(
        snapshot_id="snapshot_old",
        base_url="http://old:9621",
        latest_versions={"contract": "2026-06-19-review"},
    )
    write_active_snapshot(active_path, previous)
    client = FakeClient(
        processed_documents=[
            {
                "file_path": "contract@2026-07-01-final.pdf",
                "status": "failed",
                "chunks_count": None,
                "error_msg": "No module named 'fitz'",
            }
        ]
    )

    with pytest.raises(RuntimeError, match="failed to index"):
        await LatestSnapshotBuilder(registry, active_path).build_and_activate(
            snapshot_id="snapshot_20260701",
            base_url="http://lightrag-snapshot:9621",
            client=client,
        )

    assert read_active_snapshot(active_path) == previous


@pytest.mark.asyncio
async def test_snapshot_builder_activates_processed_latest_sources_and_reports_failures(
    tmp_path,
):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_file_version(
        "contract",
        "2026-07-01-final",
        "contract.pdf",
        b"%PDF-1.4\nnew",
    )
    registry.write_file_version(
        "empty-upload",
        "2026-07-01-final",
        "empty-upload.pdf",
        b"%PDF-1.4\n",
    )
    active_path = tmp_path / "snapshots" / "active.json"
    client = FakeClient(
        processed_documents=[
            {
                "file_path": "contract@2026-07-01-final.pdf",
                "status": "processed",
                "chunks_count": 8,
                "error_msg": None,
            },
            {
                "file_path": "empty-upload@2026-07-01-final.pdf",
                "status": "failed",
                "chunks_count": None,
                "error_msg": "extracted no usable text",
            },
        ]
    )

    result = await LatestSnapshotBuilder(registry, active_path).build_and_activate(
        snapshot_id="snapshot_20260701",
        base_url="http://lightrag-snapshot:9621",
        client=client,
    )

    assert result.snapshot.latest_versions == {"contract": "2026-07-01-final"}
    assert result.indexed_sources == ["contract@2026-07-01-final.pdf"]
    assert result.failed_sources == [
        {
            "source_name": "empty-upload@2026-07-01-final.pdf",
            "error": "extracted no usable text",
        }
    ]
    assert read_active_snapshot(active_path) == result.snapshot


@pytest.mark.asyncio
async def test_snapshot_builder_preserves_active_snapshot_when_latest_missing_chunks(
    tmp_path,
):
    registry = SourceRegistry(tmp_path / "sources")
    registry.write_text_version("handbook", "2026-07-01-final", "Handbook", "new")
    active_path = tmp_path / "snapshots" / "active.json"
    previous = ActiveSnapshot(
        snapshot_id="snapshot_old",
        base_url="http://old:9621",
        latest_versions={"handbook": "2026-06-19-review"},
    )
    write_active_snapshot(active_path, previous)
    client = FakeClient(processed_documents=[])

    with pytest.raises(RuntimeError, match="not indexed"):
        await LatestSnapshotBuilder(registry, active_path).build_and_activate(
            snapshot_id="snapshot_20260701",
            base_url="http://lightrag-snapshot:9621",
            client=client,
        )

    assert read_active_snapshot(active_path) == previous


def _processed_document(file_path: str) -> dict[str, object]:
    return {
        "file_path": file_path,
        "status": "processed",
        "chunks_count": 1,
        "error_msg": None,
    }


def _canonical_source_name(file_path: str) -> str:
    return file_path.replace(".[-!].", ".")
