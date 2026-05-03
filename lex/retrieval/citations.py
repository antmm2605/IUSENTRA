"""Conversione evidenze -> citazioni Lex."""

from __future__ import annotations

from lex.contracts import Citation


def _int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_citations(items):
    citations: list[Citation] = []
    for item in list(items or []):
        metadata = dict(getattr(item, "metadata", {}) or {})
        page_no = _int_or_none(
            metadata.get("page_no")
            or metadata.get("page_from")
            or metadata.get("page")
            or metadata.get("pagina")
        )
        chunk_index = _int_or_none(metadata.get("chunk_index"))
        citations.append(
            Citation(
                source_type=item.source_type,
                source_id=item.source_id,
                title=item.title,
                excerpt=item.content[:240],
                confidence=float(item.score),
                authority=str(getattr(item, "authority", "") or metadata.get("authority") or ""),
                url=getattr(item, "official_url", None) or metadata.get("official_url") or metadata.get("url"),
                trust_class=str(getattr(item, "trust_class", "") or metadata.get("trust_class") or ""),
                source_level=int(getattr(item, "source_level", 0) or metadata.get("source_level") or 0),
                verified_reference=bool(getattr(item, "verified_reference", False) or metadata.get("verified_reference")),
                published_at=getattr(item, "published_at", None) or metadata.get("published_at"),
                freshness_score=float(getattr(item, "freshness_score", 0.0) or metadata.get("freshness_score") or 0.0),
                page_no=page_no,
                section_path=str(metadata.get("section_path") or ""),
                chunk_index=chunk_index,
            )
        )
    return citations
