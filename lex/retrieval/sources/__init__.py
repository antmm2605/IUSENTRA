"""Adapter sorgente per il retrieval applicativo di Lex."""

from __future__ import annotations

from lex.contracts import EvidenceItem


def row_to_evidence(row, default_source_type: str) -> EvidenceItem:
    payload = row.to_dict() if hasattr(row, "to_dict") else dict(row or {})
    source_type = str(payload.get("type") or payload.get("source_type") or default_source_type)
    source_id = str(payload.get("id") or payload.get("source_id") or payload.get("source_id") or "")
    title = str(payload.get("title") or "Fonte")
    content = str(payload.get("excerpt") or payload.get("content") or "").strip()
    score = float(payload.get("score") or 0.0)
    metadata = {key: value for key, value in payload.items() if key not in {"type", "source_type", "id", "source_id", "title", "excerpt", "content", "score"}}
    return EvidenceItem(
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        score=score,
        metadata=metadata,
    )
