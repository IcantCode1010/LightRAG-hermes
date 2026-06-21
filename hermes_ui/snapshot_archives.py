from __future__ import annotations

import shutil
from pathlib import Path


def list_snapshot_archives(archive_root: Path) -> dict[str, list[dict[str, object]]]:
    archive_root.mkdir(parents=True, exist_ok=True)
    archives = []
    for path in archive_root.iterdir():
        if not path.is_dir():
            continue
        stat = path.stat()
        archives.append(
            {
                "name": path.name,
                "kind": "directory",
                "size_bytes": _directory_size(path),
                "modified_at": stat.st_mtime,
            }
        )
    archives.sort(key=lambda archive: str(archive["name"]), reverse=True)
    return {"archives": archives}


def delete_snapshot_archive(
    archive_root: Path,
    archive_name: str,
    *,
    confirmation: str,
) -> dict[str, str]:
    safe_name = _validate_archive_name(archive_name)
    if str(confirmation or "").strip() != safe_name:
        raise ValueError("confirmation must match archive name")

    archive_root.mkdir(parents=True, exist_ok=True)
    target = _resolve_direct_child(archive_root, safe_name)
    if not target.exists():
        raise FileNotFoundError(f"snapshot archive not found: {safe_name}")
    if not target.is_dir():
        raise ValueError("snapshot archive must be a directory")

    shutil.rmtree(target)
    return {"status": "deleted", "archive_name": safe_name}


def _validate_archive_name(archive_name: str) -> str:
    name = str(archive_name or "").strip()
    if not name:
        raise ValueError("archive_name cannot be empty")
    if "/" in name or "\\" in name or name in {".", ".."} or ".." in name:
        raise ValueError("archive_name must be a direct archive folder name")
    return name


def _resolve_direct_child(root: Path, child_name: str) -> Path:
    resolved_root = root.resolve()
    target = (resolved_root / child_name).resolve()
    if target.parent != resolved_root:
        raise ValueError("archive_name must resolve under the archive directory")
    return target


def _directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total
