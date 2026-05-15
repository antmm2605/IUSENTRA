"""Normalization placeholders for legal source documents."""

from __future__ import annotations

from typing import Any

from .models import LegalCitation, NormalizedLegalDocument


def normalize_document(raw_document: Any, *, source_id: str = "", default_document_type: str = "") -> NormalizedLegalDocument:
    """Normalize a raw object without side effects.

    Future adapters will implement source-specific normalization. This fallback
    only accepts in-memory objects already provided by tests or controlled code.
    """

    data = dict(raw_document or {}) if isinstance(raw_document, dict) else {"text": str(raw_document or "")}
    citation = data.get("citation") if isinstance(data.get("citation"), LegalCitation) else None
    return NormalizedLegalDocument(
        document_id=str(data.get("document_id") or data.get("id") or ""),
        source_id=str(data.get("source_id") or source_id),
        title=str(data.get("title") or data.get("titolo") or ""),
        document_type=str(data.get("document_type") or data.get("tipo_documento") or default_document_type),
        text=str(data.get("text") or data.get("content") or ""),
        citation=citation,
        metadata=dict(data.get("metadata") or {}),
    )


__all__ = ["normalize_document"]
