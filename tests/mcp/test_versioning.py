import pytest

from lightrag_mcp.versioning import (
    VersionedSource,
    build_source_name,
    latest_by_document_key,
    parse_source_name,
    validate_document_key,
    validate_version_label,
)


def test_validate_document_key_allows_safe_key():
    assert validate_document_key("contract-alpha_1.2") == "contract-alpha_1.2"


@pytest.mark.parametrize("value", ["", "../x", "a/b", "a@b", "two words"])
def test_validate_document_key_rejects_unsafe_values(value):
    with pytest.raises(ValueError):
        validate_document_key(value)


def test_validate_version_label_requires_sortable_date_prefix():
    assert validate_version_label("2026-06-19-legal-review") == (
        "2026-06-19-legal-review"
    )


@pytest.mark.parametrize("value", ["legal-review", "2026/06/19-x", "2026-06-19 x"])
def test_validate_version_label_rejects_unsortable_or_unsafe_values(value):
    with pytest.raises(ValueError):
        validate_version_label(value)


def test_build_and_parse_source_name():
    name = build_source_name("handbook", "2026-06-19-legal-review", ".md")

    assert name == "handbook@2026-06-19-legal-review.md"
    assert parse_source_name(name) == VersionedSource(
        document_key="handbook",
        version_label="2026-06-19-legal-review",
        extension=".md",
        source_name=name,
    )


def test_latest_by_document_key_uses_string_sorting():
    sources = [
        parse_source_name("handbook@2026-06-19-review.md"),
        parse_source_name("handbook@2026-07-01-final.md"),
        parse_source_name("policy@2026-06-01-draft.txt"),
    ]

    latest = latest_by_document_key(sources)

    assert latest["handbook"].version_label == "2026-07-01-final"
    assert latest["policy"].version_label == "2026-06-01-draft"
