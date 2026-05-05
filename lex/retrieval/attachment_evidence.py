"""Evidenze governate derivate dagli allegati caricati nel widget Lex."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lex.contracts import EvidenceItem


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _attachment_id(item: dict[str, Any], index: int) -> str:
    return _clean(item.get("id")) or f"attachment-{index}"


def build_attachment_evidence(
    attachments: list[dict[str, Any]] | None,
    request: Any,
    context: dict[str, Any] | None = None,
) -> list[EvidenceItem]:
    """Converte gli allegati gia' parsati in EvidenceItem citabili.

    Gli allegati arrivano qui solo dopo il parsing governato del server o del
    companion locale. Se manca testo estraibile, non viene costruita evidenza:
    il workflow chiamante dovra' fermarsi o chiedere indicizzazione/lettura.
    """

    items: list[EvidenceItem] = []
    tenant_id = _clean(getattr(request, "tenant_id", ""))
    session_id = _clean(getattr(request, "session_id", ""))
    fascicolo_id = _clean(getattr(request, "fascicolo_id", ""))
    context_payload = dict(context or {})

    for index, raw in enumerate(list(attachments or []), start=1):
        if not isinstance(raw, dict):
            continue
        text = _clean(raw.get("text_excerpt") or raw.get("content") or raw.get("text"))
        if not text:
            continue
        name = _clean(raw.get("name")) or f"Documento {index}"
        attachment_id = _attachment_id(raw, index)
        metadata = {
            "origin": "user_attachment",
            "attachment_id": attachment_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "fascicolo_id": fascicolo_id,
            "name": name,
            "mime_type": _clean(raw.get("mime_type") or raw.get("type")),
            "size_bytes": int(raw.get("size_bytes") or 0),
            "page_count": raw.get("page_count"),
            "text_chars": int(raw.get("text_chars") or len(text)),
            "truncated": bool(raw.get("truncated")),
            "parser": _clean(raw.get("parser")) or "lex_attachment_parser",
            "parser_version": _clean(raw.get("parser_version")),
            "authority": "user_attachment",
            "source_context": {
                "focus_topic": _clean(context_payload.get("focus_topic")),
                "focus_label": _clean(context_payload.get("focus_label")),
            },
        }
        items.append(
            EvidenceItem(
                source_type="documento",
                source_id=f"attachment:{attachment_id}",
                title=f"Allegato caricato: {name}",
                content=text,
                score=0.76,
                metadata=metadata,
                trust_class="B",
                source_level=3,
                authority="user_attachment",
                verified_reference=False,
            )
        )
    return items


def attachment_evidence_source_rows(items: list[EvidenceItem]) -> list[dict[str, Any]]:
    """Serializza EvidenceItem in righe compatibili con lo studio context seed."""

    rows: list[dict[str, Any]] = []
    for item in list(items or []):
        payload = asdict(item)
        payload["type"] = payload.pop("source_type", "documento")
        payload["id"] = payload.pop("source_id", "")
        payload["excerpt"] = payload.pop("content", "")
        rows.append(payload)
    return rows


__all__ = ["attachment_evidence_source_rows", "build_attachment_evidence"]
