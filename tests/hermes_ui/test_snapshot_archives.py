from pathlib import Path

import pytest

from hermes_ui.snapshot_archives import (
    delete_snapshot_archive,
    list_snapshot_archives,
)


def test_list_snapshot_archives_returns_direct_child_directories(tmp_path: Path):
    archive_root = tmp_path / "archives"
    first = archive_root / "hermes_snapshot_20260620_010101"
    second = archive_root / "hermes_snapshot_20260620_020202"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (archive_root / "loose-file.txt").write_text("not an archive", encoding="utf-8")
    (first / "rag_storage").mkdir()

    result = list_snapshot_archives(archive_root)

    assert [archive["name"] for archive in result["archives"]] == [
        "hermes_snapshot_20260620_020202",
        "hermes_snapshot_20260620_010101",
    ]
    assert result["archives"][0]["kind"] == "directory"
    assert result["archives"][0]["size_bytes"] == 0
    assert "modified_at" in result["archives"][0]


def test_delete_snapshot_archive_requires_exact_confirmation(tmp_path: Path):
    archive_root = tmp_path / "archives"
    target = archive_root / "hermes_snapshot_20260620_010101"
    target.mkdir(parents=True)

    with pytest.raises(ValueError, match="confirmation must match archive name"):
        delete_snapshot_archive(
            archive_root,
            "hermes_snapshot_20260620_010101",
            confirmation="wrong",
        )

    assert target.exists()


def test_delete_snapshot_archive_removes_direct_child_directory(tmp_path: Path):
    archive_root = tmp_path / "archives"
    target = archive_root / "hermes_snapshot_20260620_010101"
    target.mkdir(parents=True)
    (target / "data.txt").write_text("old index", encoding="utf-8")

    result = delete_snapshot_archive(
        archive_root,
        "hermes_snapshot_20260620_010101",
        confirmation="hermes_snapshot_20260620_010101",
    )

    assert result == {
        "status": "deleted",
        "archive_name": "hermes_snapshot_20260620_010101",
    }
    assert not target.exists()
    assert archive_root.exists()


@pytest.mark.parametrize(
    "archive_name",
    [
        "../outside",
        "..\\outside",
        "nested/archive",
        "nested\\archive",
        "",
    ],
)
def test_delete_snapshot_archive_rejects_unsafe_names(
    tmp_path: Path, archive_name: str
):
    archive_root = tmp_path / "archives"
    archive_root.mkdir()

    with pytest.raises(ValueError, match="archive_name"):
        delete_snapshot_archive(archive_root, archive_name, confirmation=archive_name)
