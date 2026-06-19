from pathlib import Path


SCRIPT = Path("scripts/rotate-hermes-snapshot.ps1")


def test_rotation_script_exists_and_supports_dry_run():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "[CmdletBinding(SupportsShouldProcess = $true)]" in text
    assert "Move-Item" in text
    assert "New-Item" in text


def test_rotation_script_archives_without_delete_or_clear():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "Remove-Item" not in text
    assert "/documents/clear" not in text
    assert "delete_document" not in text
    assert "hermes_snapshot_archive" in text
    assert "Move-Item -LiteralPath $snapshotPath -Destination $archivePath" in text


def test_rotation_script_recreates_expected_snapshot_directories():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "data\\hermes_snapshot" in text
    assert "rag_storage" in text
    assert "inputs" in text
