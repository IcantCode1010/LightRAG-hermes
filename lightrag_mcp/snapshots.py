from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import time

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
    failed_sources: list[dict[str, str]]
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

    def write_file_version(
        self,
        document_key: str,
        version_label: str,
        filename: str,
        content: bytes,
    ) -> Path:
        self._ensure_dir()
        extension = Path(filename).suffix
        if not extension:
            raise ValueError("filename must include a file extension")
        source_name = build_source_name(document_key, version_label, extension)
        target = self.source_dir / source_name
        if target.exists():
            raise ValueError(f"document version already exists: {source_name}")
        target.write_bytes(content)
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
        validation_timeout_s: float = 900.0,
        validation_poll_s: float = 2.0,
    ) -> SnapshotBuildResult:
        target_documents = await client.documents()
        if target_documents.get("documents"):
            raise RuntimeError(
                "snapshot endpoint is not empty; rotate or archive the snapshot "
                "storage before building a new latest-only snapshot"
            )

        latest = self.registry.latest_sources()
        latest_sources = [latest[key] for key in sorted(latest)]
        insert_results: list[dict[str, object]] = []
        indexed_sources: list[str] = []

        for source in latest_sources:
            source_path = self.registry.source_path(source)
            if _should_insert_as_text(source.extension):
                text = source_path.read_text(encoding="utf-8")
                insert_result = await client.insert_text(
                    text,
                    file_source=source.source_name,
                )
            else:
                insert_result = await client.insert_file(
                    source_path,
                    file_source=_snapshot_upload_name(source.source_name),
                )
            insert_results.append(dict(insert_result))
            indexed_sources.append(source.source_name)

        indexed_sources, failed_sources = await _wait_for_indexed_sources(
            client,
            indexed_sources,
            timeout_s=validation_timeout_s,
            poll_s=validation_poll_s,
        )
        active_latest_sources = [
            source for source in latest_sources if source.source_name in indexed_sources
        ]

        snapshot = ActiveSnapshot(
            snapshot_id=snapshot_id,
            base_url=base_url,
            latest_versions={
                source.document_key: source.version_label
                for source in active_latest_sources
            },
        )
        write_active_snapshot(self.active_snapshot_file, snapshot)
        return SnapshotBuildResult(
            snapshot=snapshot,
            indexed_sources=indexed_sources,
            failed_sources=failed_sources,
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


async def _wait_for_indexed_sources(
    client,
    source_names: list[str],
    *,
    timeout_s: float,
    poll_s: float,
) -> tuple[list[str], list[dict[str, str]]]:
    expected = set(source_names)
    deadline = time.monotonic() + timeout_s
    last_error = ""

    while True:
        try:
            pipeline = await client.pipeline_status()
        except AttributeError:
            pipeline = {"busy": False}
        documents_response = await client.documents()
        documents = documents_response.get("documents") or []
        busy = bool(pipeline.get("busy"))
        indexed_sources, failed_sources, last_error = _validate_indexed_sources(
            expected, documents
        )
        if indexed_sources and (not failed_sources or not busy):
            return sorted(indexed_sources), failed_sources

        if not busy or time.monotonic() >= deadline:
            raise RuntimeError(last_error)
        await asyncio.sleep(max(0.1, poll_s))


def _validate_indexed_sources(
    expected: set[str],
    documents: list[dict[str, object]],
) -> tuple[set[str], list[dict[str, str]], str]:
    by_file_path = {
        str(document.get("file_path") or ""): document
        for document in documents
        if isinstance(document, dict)
    }
    missing = sorted(source for source in expected if source not in by_file_path)
    if missing:
        return set(), [], f"snapshot source not indexed: {', '.join(missing)}"

    indexed_sources: set[str] = set()
    failed_sources: list[dict[str, str]] = []
    unprocessed = []
    for source in sorted(expected):
        document = by_file_path[source]
        status = str(document.get("status") or "")
        chunks_count = document.get("chunks_count")
        if status == "failed":
            error = str(document.get("error_msg") or "unknown error")
            failed_sources.append({"source_name": source, "error": error})
        elif status != "processed" or not isinstance(chunks_count, int) or chunks_count < 1:
            unprocessed.append(f"{source}: status={status or 'unknown'}")
        else:
            indexed_sources.add(source)

    if failed_sources and not indexed_sources:
        failed = [
            f"{source['source_name']}: {source['error']}" for source in failed_sources
        ]
        return set(), failed_sources, f"snapshot source failed to index: {'; '.join(failed)}"
    if unprocessed:
        return set(), failed_sources, f"snapshot source not indexed: {'; '.join(unprocessed)}"
    return indexed_sources, failed_sources, ""


def _should_insert_as_text(extension: str) -> bool:
    return extension.lower() in {".md", ".markdown", ".txt", ".csv", ".json", ".log"}


def _snapshot_upload_name(source_name: str) -> str:
    path = Path(source_name)
    if not path.suffix:
        return source_name
    # LightRAG strips supported parser hints from stored file_path. The `!`
    # option keeps chunk vectors but skips expensive entity/relation extraction.
    return f"{path.stem}.[-!]{path.suffix}"
