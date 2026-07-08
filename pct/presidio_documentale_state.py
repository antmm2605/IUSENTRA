"""Stato idempotente dei presidi documentali.

Il modulo contiene solo helper puri: non legge file, non apre database e non
avvia OCR. I runner dei singoli presidi gli passano impronta, metadati ed
evidenze già calcolati, poi salvano l'esito nel proprio repository.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


def _text(value: Any, default: str = "") -> str:
    value = str(value or "").strip()
    return value or default


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_document_source(value: Any, *, default: str = "Documento indicizzato del fascicolo") -> str:
    source = _text(value)
    if not source:
        return default
    name = Path(source.replace("\\", "/")).name
    if not name:
        return default
    marker = source.casefold()
    stem = Path(name).stem.casefold()
    if marker.startswith(("document_id:", "documento_id:", "docai-", "docai_", "doc-", "doc_")):
        return default
    if stem.isdigit() and len(stem) >= 10:
        return default
    return source


def marker_is_current(marker: Mapping[str, Any] | None, fingerprint: str) -> bool:
    if not isinstance(marker, Mapping):
        return False
    status = _text(marker.get("status") or marker.get("stato")).casefold()
    cached = _text(marker.get("fingerprint") or marker.get("documentFingerprint"))
    return status == "aggiornato" and bool(cached) and cached == _text(fingerprint)


def marker_state(
    marker: Mapping[str, Any] | None,
    fingerprint: str,
    *,
    related_count: int = 0,
) -> dict[str, Any]:
    marker = marker if isinstance(marker, Mapping) else {}
    cached = _text(marker.get("fingerprint") or marker.get("documentFingerprint"))
    status_raw = _text(marker.get("status") or marker.get("stato")).casefold()
    unresolved_kinds = _normalise_unresolved_kinds(marker.get("unresolvedKinds") or marker.get("unresolved_kinds") or marker.get("da_verificare"))
    if status_raw == "stale":
        status = "da_rianalizzare"
        label = "Da rianalizzare"
        reason = _text(marker.get("reason"), "Sono entrati nuovi documenti o è cambiato il fascicolo.")
    elif cached and cached == _text(fingerprint) and unresolved_kinds:
        status = "aggiornato_con_rilievi"
        label = "Documenti controllati"
        reason = _unresolved_reason(marker, unresolved_kinds)
    elif cached and cached == _text(fingerprint):
        status = "aggiornato"
        label = "Aggiornato"
        reason = _text(marker.get("reason"), "Analisi allineata ai documenti presenti.")
    elif cached:
        status = "da_rianalizzare"
        label = "Da rianalizzare"
        reason = "Sono entrati nuovi documenti o è cambiato il fascicolo."
    else:
        status = "da_analizzare"
        label = "Da analizzare"
        reason = "Nessuna impronta di analisi consolidata sui documenti correnti."
    return {
        "status": status,
        "statusLabel": label,
        "tone": "warning" if status in {"da_rianalizzare", "da_analizzare", "aggiornato_con_rilievi"} else "success",
        "reason": reason,
        "fingerprint": _text(fingerprint),
        "lastAnalyzedAt": _text(marker.get("updated_at") or marker.get("updatedAt") or marker.get("lastAnalyzedAt")),
        "relatedDuplicateFascicoli": max(0, int(related_count or 0)),
        "unresolvedKinds": unresolved_kinds,
    }


def _normalise_unresolved_kinds(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item or "").strip() for item in value if str(item or "").strip()]
    else:
        values = []
    return sorted(dict.fromkeys(values))


def _unresolved_reason(marker: Mapping[str, Any], unresolved_kinds: list[str]) -> str:
    if "contributo_unificato" in unresolved_kinds:
        return (
            "Presidio documentale eseguito: nei documenti correnti non risulta una ricevuta, "
            "un'autocertificazione di esenzione o un invito al pagamento del contributo unificato leggibile."
        )
    return _text(
        marker.get("reason"),
        "Presidio documentale eseguito: alcuni dati non risultano dai documenti correnti.",
    )


def metadata_rule_hits(
    metadata_rows: Iterable[Mapping[str, Any]],
    *,
    readable_source: Callable[[Any], str] = default_document_source,
    limit: int = 60,
) -> list[dict[str, Any]]:
    try:
        from pct.presidio_processuale_ruleset import presidio_rule_hits
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for metadata in metadata_rows or []:
        document_id = _text(metadata.get("document_id") or metadata.get("documento_id"))
        if not document_id:
            continue
        for hit in presidio_rule_hits("", dict(metadata)):
            key = (document_id, _text(hit.get("code") or hit.get("classification")))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "documentId": document_id,
                    "documentoFonte": readable_source(metadata.get("filename") or document_id),
                    "code": _text(hit.get("code")),
                    "sector": _text(hit.get("sector")),
                    "label": _text(hit.get("label")),
                    "classification": _text(hit.get("classification")),
                    "legalBasis": list(hit.get("legalBasis") or []),
                    "parserFields": list(hit.get("parserFields") or []),
                    "source": "metadati_documento",
                }
            )
            if len(out) >= limit:
                return out
    return out


def automatic_economic_hits(
    automatic_sources: Mapping[str, Mapping[str, Any]] | None,
    *,
    readable_source: Callable[[Any], str] = default_document_source,
    normalise_kind: Callable[[Any], str] | None = None,
    normalise_status: Callable[[Any], str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(automatic_sources, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for kind, source in automatic_sources.items():
        if not isinstance(source, Mapping):
            continue
        normalized_kind = normalise_kind(kind) if callable(normalise_kind) else _text(kind)
        status = normalise_status(source.get("status") or source.get("stato")) if callable(normalise_status) else _text(source.get("status") or source.get("stato"))
        nature = _text(source.get("natura"))
        document_source = readable_source(source.get("documento_fonte") or source.get("document_id") or source.get("filename"))
        if normalized_kind == "contributo_unificato":
            if status == "non_previsto" or nature == "esenzione_contributo_unificato":
                code = "contributo_unificato_esenzione"
                classification = "contributo_unificato_esente"
                label = "Contributo unificato esente o non dovuto"
            elif status == "da_registrare":
                code = "contributo_unificato_invito"
                classification = "contributo_unificato_da_regolarizzare"
                label = "Contributo unificato da registrare o regolarizzare"
            else:
                code = "contributo_unificato_pagamento"
                classification = "contributo_unificato"
                label = "Contributo unificato pagato"
            rows.append(
                {
                    "documentoFonte": document_source,
                    "code": code,
                    "sector": "economico",
                    "label": label,
                    "classification": classification,
                    "legalBasis": ["D.P.R. 115/2002"],
                    "parserFields": ["amount", "iuv", "payment_date", "esito"],
                    "source": "parser_economico",
                }
            )
        elif normalized_kind in {"liquidazione_giudice", "spese_esborsi", "parcella"}:
            rows.append(
                {
                    "documentoFonte": document_source,
                    "code": "spese_liquidazione",
                    "sector": "economico",
                    "label": "Liquidazione spese e compensi",
                    "classification": "sentenza_economica",
                    "legalBasis": ["artt. 91-93 c.p.c.", "D.M. 55/2014"],
                    "parserFields": ["liquidazione", "compensi", "esborsi", "spese_generali"],
                    "source": "parser_economico",
                }
            )
    return rows


def build_marker(
    *,
    fingerprint: str,
    actor: str,
    document_count: int,
    metadata_rows: Iterable[Mapping[str, Any]] = (),
    automatic_sources: Mapping[str, Mapping[str, Any]] | None = None,
    readable_source: Callable[[Any], str] = default_document_source,
    normalise_kind: Callable[[Any], str] | None = None,
    normalise_status: Callable[[Any], str] | None = None,
    status: str = "aggiornato",
    reason: str = "Analisi documentale completata e salvata nel fascicolo.",
) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for hit in [
        *automatic_economic_hits(
            automatic_sources,
            readable_source=readable_source,
            normalise_kind=normalise_kind,
            normalise_status=normalise_status,
        ),
        *metadata_rule_hits(metadata_rows, readable_source=readable_source),
    ]:
        key = (_text(hit.get("documentId") or hit.get("documentoFonte")), _text(hit.get("code")), _text(hit.get("classification")))
        if key in seen:
            continue
        seen.add(key)
        hits.append(hit)
    return {
        "status": status,
        "fingerprint": _text(fingerprint),
        "updated_at": _now(),
        "updated_by": _text(actor, "IUSENTRA"),
        "reason": reason,
        "document_count": max(0, int(document_count or 0)),
        "classifications": hits[:80],
        "coverage": ["documenti_fascicolo", "economia", "contributo_unificato", "sentenze"],
    }


__all__ = [
    "automatic_economic_hits",
    "build_marker",
    "default_document_source",
    "marker_is_current",
    "marker_state",
    "metadata_rule_hits",
]
