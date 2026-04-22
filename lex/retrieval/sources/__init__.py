"""Adapter sorgente per il retrieval applicativo di Lex."""

from __future__ import annotations

from lex.contracts import EvidenceItem


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "vero", "yes", "si"}


def _infer_official_profile(source_type: str, authority: str, official_url: str, verified_reference: bool) -> tuple[str, int]:
    source_type = str(source_type or "").strip().lower()
    authority = str(authority or "").strip().lower()
    official_url = str(official_url or "").strip().lower()

    if source_type == "web_ufficiale":
        return "A", 1
    if source_type == "normativa" and official_url:
        return "A", 1
    if source_type in {"giurisprudenza", "prassi"} and (verified_reference or official_url):
        return "B", 2
    if source_type in {"legal_intelligence", "telematico", "compliance"} and (official_url or "official" in authority or "istituz" in authority):
        return "B", 2
    return "", 0


def row_to_evidence(row, default_source_type: str) -> EvidenceItem:
    payload = row.to_dict() if hasattr(row, "to_dict") else dict(row or {})
    source_type = str(payload.get("type") or payload.get("source_type") or default_source_type)
    source_id = str(payload.get("id") or payload.get("source_id") or "")
    title = str(payload.get("title") or "Fonte")
    content = str(payload.get("excerpt") or payload.get("content") or "").strip()
    score = float(payload.get("score") or 0.0)
    metadata = {
        key: value
        for key, value in payload.items()
        if key not in {"type", "source_type", "id", "source_id", "title", "excerpt", "content", "score"}
    }
    authority = str(payload.get("authority") or metadata.get("authority") or "").strip()
    official_url = str(
        payload.get("official_url")
        or payload.get("url_pagina_ufficiale")
        or payload.get("url_pdf_ufficiale")
        or payload.get("url")
        or metadata.get("official_url")
        or metadata.get("url")
        or ""
    ).strip()
    trust_class = str(payload.get("trust_class") or metadata.get("trust_class") or "").strip().upper()
    source_level = int(payload.get("source_level") or metadata.get("source_level") or 0)
    verified_reference = _to_bool(payload.get("verified_reference") or metadata.get("verified_reference"))
    published_at = str(
        payload.get("published_at")
        or payload.get("data_pubblicazione")
        or metadata.get("published_at")
        or metadata.get("data_pubblicazione")
        or ""
    ).strip() or None
    if not trust_class and not source_level:
        trust_class, source_level = _infer_official_profile(
            source_type=source_type,
            authority=authority,
            official_url=official_url,
            verified_reference=verified_reference,
        )
    return EvidenceItem(
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        score=score,
        metadata=metadata,
        trust_class=trust_class,
        source_level=source_level,
        verified_reference=verified_reference,
        authority=authority,
        published_at=published_at,
        official_url=official_url or None,
    )
