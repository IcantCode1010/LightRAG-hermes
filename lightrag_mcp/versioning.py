from __future__ import annotations

import re
from dataclasses import dataclass


SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class VersionedSource:
    document_key: str
    version_label: str
    extension: str
    source_name: str


def _validate_safe_token(value: str, field_name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    if "@" in value or "/" in value or "\\" in value or ".." in value:
        raise ValueError(f"{field_name} contains unsafe path characters")
    if not SAFE_TOKEN_RE.fullmatch(value):
        raise ValueError(
            f"{field_name} may only contain letters, numbers, '.', '_', and '-'"
        )
    return value


def validate_document_key(value: str) -> str:
    return _validate_safe_token(value, "document_key")


def validate_version_label(value: str) -> str:
    value = _validate_safe_token(value, "version_label")
    if not VERSION_RE.fullmatch(value):
        raise ValueError("version_label must start with YYYY-MM-DD-")
    return value


def build_source_name(document_key: str, version_label: str, extension: str) -> str:
    key = validate_document_key(document_key)
    label = validate_version_label(version_label)
    ext = extension if extension.startswith(".") else f".{extension}"
    ext_token = _validate_safe_token(ext.lstrip("."), "extension")
    return f"{key}@{label}.{ext_token}"


def parse_source_name(source_name: str) -> VersionedSource:
    if "@" not in source_name:
        raise ValueError("source name must contain '@'")
    document_key, rest = source_name.split("@", 1)
    if "." not in rest:
        raise ValueError("source name must include a file extension")
    version_label, extension = rest.rsplit(".", 1)
    normalized = build_source_name(document_key, version_label, extension)
    return VersionedSource(
        document_key=document_key,
        version_label=version_label,
        extension=f".{extension}",
        source_name=normalized,
    )


def latest_by_document_key(
    sources: list[VersionedSource],
) -> dict[str, VersionedSource]:
    latest: dict[str, VersionedSource] = {}
    for source in sources:
        current = latest.get(source.document_key)
        if current is None or source.version_label > current.version_label:
            latest[source.document_key] = source
    return latest
