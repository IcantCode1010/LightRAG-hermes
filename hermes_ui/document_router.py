from dataclasses import dataclass
import re
from typing import Any, Literal


RouteIntent = Literal["general", "latest_all", "latest_documents"]


@dataclass(frozen=True)
class RouteDecision:
    intent: RouteIntent
    document_keys: list[str]
    confidence: float
    reason: str


_DOCUMENT_RELATED_PATTERN = re.compile(
    r"\b("
    r"document|documents|doc|docs|file|files|pdf|indexed|index|snapshot|"
    r"source|sources|cite|citation|citations|summarize|summary|compare|"
    r"extract|find|search|lookup|look up|according to|based on|what changed|"
    r"policy|manual|report|contract|version"
    r")\b",
    re.IGNORECASE,
)

_STOPWORDS = {
    "a",
    "about",
    "all",
    "an",
    "and",
    "are",
    "book",
    "can",
    "compare",
    "does",
    "document",
    "documents",
    "file",
    "files",
    "for",
    "from",
    "how",
    "indexed",
    "is",
    "latest",
    "manual",
    "manuals",
    "me",
    "of",
    "on",
    "pdf",
    "report",
    "say",
    "student",
    "summarize",
    "summary",
    "tell",
    "the",
    "these",
    "this",
    "to",
    "training",
    "version",
    "what",
    "which",
    "with",
    "you",
}


def route_document_query(
    message: str,
    documents: dict[str, Any],
    snapshot: dict[str, Any],
) -> RouteDecision:
    records = _searchable_document_records(documents, snapshot)
    document_related = _looks_document_related(message)
    ranked = _rank_documents(message, records)

    if ranked and ranked[0][1] >= 2.0:
        best_score = ranked[0][1]
        selected = [key for key, score in ranked if score >= best_score - 0.5]
        return RouteDecision(
            intent="latest_documents",
            document_keys=selected,
            confidence=min(1.0, best_score / 5.0),
            reason="matched_document_terms",
        )

    if document_related and _has_registered_documents(documents):
        return RouteDecision(
            intent="latest_all",
            document_keys=[],
            confidence=0.5,
            reason="document_intent_without_confident_match",
        )

    return RouteDecision(
        intent="general",
        document_keys=[],
        confidence=0.0,
        reason="no_document_intent",
    )


def _looks_document_related(message: str) -> bool:
    return bool(_DOCUMENT_RELATED_PATTERN.search(message))


def _has_registered_documents(documents: dict[str, Any]) -> bool:
    records = documents.get("documents")
    return isinstance(records, list) and any(isinstance(record, dict) for record in records)


def _searchable_document_records(
    documents: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    records = documents.get("documents")
    if not isinstance(records, list):
        return []

    active_versions = _active_snapshot_versions(snapshot)
    if not active_versions:
        return [record for record in records if isinstance(record, dict)]

    searchable = []
    for record in records:
        if not isinstance(record, dict):
            continue
        key = str(record.get("document_key") or "")
        latest = str(record.get("latest_version_label") or "")
        if key and latest and active_versions.get(key) == latest:
            searchable.append(record)
    return searchable


def _active_snapshot_versions(snapshot: dict[str, Any]) -> dict[str, str]:
    active = snapshot.get("active_snapshot") if isinstance(snapshot, dict) else None
    versions = active.get("latest_versions") if isinstance(active, dict) else {}
    if not isinstance(versions, dict):
        return {}
    return {str(key): str(value) for key, value in versions.items()}


def _rank_documents(
    message: str,
    records: list[dict[str, Any]],
) -> list[tuple[str, float]]:
    message_terms = _terms(message)
    message_text = _normalized_text(message)
    ranked = []

    for record in records:
        key = str(record.get("document_key") or "")
        if not key:
            continue
        key_terms = _terms(key)
        overlap = message_terms & key_terms
        score = float(len(overlap))

        phrase = " ".join(key_terms)
        if phrase and phrase in message_text:
            score += 2.0
        if _normalized_text(key).replace(" ", "") in message_text.replace(" ", ""):
            score += 3.0

        if score > 0:
            ranked.append((key, score))

    return sorted(ranked, key=lambda item: (-item[1], item[0]))


def _terms(text: str) -> set[str]:
    terms = set()
    for raw_term in re.split(r"[^a-z0-9]+", text.lower()):
        if not raw_term or raw_term in _STOPWORDS:
            continue
        term = raw_term[:-1] if raw_term.endswith("s") and len(raw_term) > 3 else raw_term
        if term and term not in _STOPWORDS:
            terms.add(term)
    return terms


def _normalized_text(text: str) -> str:
    return " ".join(re.split(r"[^a-z0-9]+", text.lower())).strip()
