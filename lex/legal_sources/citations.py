"""Citation helpers for Legal Source Engine drafts."""

from __future__ import annotations

from typing import Iterable

from .models import LegalCitation, PolicyResult


REQUIRED_CITATION_FIELDS = (
    "source_id",
    "source_name",
    "source_category",
    "jurisdiction",
    "document_type",
    "title_or_locator",
    "date_or_retrieval",
)


def validate_citation(citation: LegalCitation) -> PolicyResult:
    result = PolicyResult()
    if not citation.source_id:
        result.add_error("citation_missing_source_id", "La citazione non indica l'ID fonte.")
    if not citation.source_name:
        result.add_error("citation_missing_source_name", "La citazione non indica il nome fonte.")
    if not citation.document_type:
        result.add_error("citation_missing_document_type", "La citazione non indica il tipo documento.")
    if not any((citation.title, citation.number, citation.url, citation.urn, citation.eli, citation.celex, citation.ecli, citation.hudoc_id)):
        result.add_error("citation_missing_locator", "La citazione non contiene titolo, numero, URL o identificativo stabile.")
    if not any((citation.date, citation.version_date, citation.retrieved_at)):
        result.add_error("citation_missing_date", "La citazione non contiene data, versione o timestamp di recupero.")
    return result


def citation_fingerprint(citation: LegalCitation) -> tuple[str, str, str, str]:
    stable = citation.urn or citation.eli or citation.celex or citation.ecli or citation.hudoc_id or citation.url
    return (
        citation.source_id.strip().lower(),
        citation.document_type.strip().lower(),
        (stable or citation.number or citation.title).strip().lower(),
        (citation.date or citation.version_date or citation.retrieved_at).strip().lower(),
    )


def deduplicate_citations(citations: Iterable[LegalCitation]) -> list[LegalCitation]:
    seen: set[tuple[str, str, str, str]] = set()
    rows: list[LegalCitation] = []
    for citation in citations:
        key = citation_fingerprint(citation)
        if key in seen:
            continue
        seen.add(key)
        rows.append(citation)
    return rows


__all__ = ["REQUIRED_CITATION_FIELDS", "citation_fingerprint", "deduplicate_citations", "validate_citation"]
