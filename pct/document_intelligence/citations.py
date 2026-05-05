"""Citazioni verificabili dei Documenti AI Fascicolo."""

from __future__ import annotations

from .models import DocumentAICitation, DocumentAIRecord, DocumentAIVersion
from .security import DocumentAIValidationError


MAX_CITATION_QUOTE_CHARS = 500


def build_document_citation(
    document: DocumentAIRecord,
    version: DocumentAIVersion,
    page_number: int | None,
    quote: str,
) -> DocumentAICitation:
    clean_quote = str(quote or "").strip()
    if not clean_quote:
        raise DocumentAIValidationError("Citazione vuota.")
    if len(clean_quote) > MAX_CITATION_QUOTE_CHARS:
        clean_quote = clean_quote[:MAX_CITATION_QUOTE_CHARS].rstrip()
    return DocumentAICitation(
        document_id=document.id,
        version_id=version.id,
        page_number=page_number,
        quote=clean_quote,
        sha256=version.sha256 or document.sha256,
    )
