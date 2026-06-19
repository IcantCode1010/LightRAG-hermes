from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from lightrag_mcp.versioning import (
    VersionedSource,
    build_source_name,
    latest_by_document_key,
    parse_source_name,
)


@dataclass(frozen=True)
class ActiveSnapshot:
    snapshot_id: str
    base_url: str
    latest_versions: dict[str, str]


@dataclass(frozen=True)
class SnapshotBuildResult:
    snapshot: ActiveSnapshot
    indexed_sources: list[str]
    insert_results: list[dict[str, object]]


class SourceRegistry:
    def __init__(self, source_dir: Path):
        self.source_dir = source_dir

    def _ensure_dir(self) -> None:
        self.source_dir.mkdir(parents=True, exist_ok=True)

    def write_text_version(
        self, document_key: str, version_label: str, title: str, text: str
    ) -> Path:
        self._ensure_dir()
        source_name = build_source_name(document_key, version_label, ".md")
        target = self.source_dir / source_name
        if target.exists():
            raise ValueError(f"document version already exists: {source_name}")
        body = f"# {title.strip() or document_key}\n\n{text}"
        target.write_text(body, encoding="utf-8")
        return target

    def list_sources(self) -> list[VersionedSource]:
        self._ensure_dir()
        sources: list[VersionedSource] = []
        for path in self.source_dir.iterdir():
            if path.is_file():
                try:
                    sources.append(parse_source_name(path.name))
                except ValueError:
                    continue
        return sources

    def latest_sources(self) -> dict[str, VersionedSource]:
        return latest_by_document_key(self.list_sources())

    def source_path(self, source: VersionedSource) -> Path:
        return self.source_dir / source.source_name


class LatestSnapshotBuilder:
    def __init__(self, registry: SourceRegistry, active_snapshot_file: Path):
        self.registry = registry
        self.active_snapshot_file = active_snapshot_file

    async def build_and_activate(
        self,
        *,
        snapshot_id: str,
        base_url: str,
        client,
    ) -> SnapshotBuildResult:
        latest = self.registry.latest_sources()
        latest_sources = [latest[key] for key in sorted(latest)]
        insert_results: list[dict[str, object]] = []
        indexed_sources: list[str] = []

        for source in latest_sources:
            source_path = self.registry.source_path(source)
            text = source_path.read_text(encoding="utf-8")
            insert_result = await client.insert_text(
                text,
                file_source=source.source_name,
            )
            insert_results.append(dict(insert_result))
            indexed_sources.append(source.source_name)

        snapshot = ActiveSnapshot(
            snapshot_id=snapshot_id,
            base_url=base_url,
            latest_versions={
                source.document_key: source.version_label for source in latest_sources
            },
        )
        write_active_snapshot(self.active_snapshot_file, snapshot)
        return SnapshotBuildResult(
            snapshot=snapshot,
            indexed_sources=indexed_sources,
            insert_results=insert_results,
        )


def write_active_snapshot(path: Path, snapshot: ActiveSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(asdict(snapshot), indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_active_snapshot(path: Path) -> ActiveSnapshot | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ActiveSnapshot(
        snapshot_id=str(data["snapshot_id"]),
        base_url=str(data["base_url"]),
        latest_versions=dict(data.get("latest_versions", {})),
    )
