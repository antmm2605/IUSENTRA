"""Fonti e citazioni per atti generati nell'editor."""

from __future__ import annotations

from .models import AttoAISource, new_id
from .validators import EditorAIValidationError, clean_text


MAX_QUOTE_CHARS = 360


def build_atto_source(
    *,
    atto_ai_id: str,
    source_type: str,
    source_id: str,
    document_id: str | None = None,
    page_number: int | None = None,
    quote: str = "",
    sha256: str = "",
    reason: str = "",
) -> AttoAISource:
    if not clean_text(atto_ai_id):
        raise EditorAIValidationError("Atto AI mancante per la fonte.")
    if not clean_text(source_type):
        raise EditorAIValidationError("Tipo fonte mancante.")
    clean_quote = clean_text(quote)
    if len(clean_quote) > MAX_QUOTE_CHARS:
        clean_quote = clean_quote[: MAX_QUOTE_CHARS - 1].rstrip() + "..."
    return AttoAISource(
        id=new_id("fonteatto"),
        atto_ai_id=clean_text(atto_ai_id),
        source_type=clean_text(source_type),
        source_id=clean_text(source_id),
        document_id=clean_text(document_id) or None,
        page_number=page_number,
        quote=clean_quote,
        sha256=clean_text(sha256),
        reason=clean_text(reason) or "Fonte considerata nella bozza atto.",
    )
