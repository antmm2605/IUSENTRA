"""Riepilogo economico della regia del fascicolo (preventivo, conferimento, parcelle) e piccoli aiuti comuni.

Separato da ``evaluator.py`` per tenere i moduli del presidio entro le 650 righe.
"""
from __future__ import annotations
from typing import Any
from urllib.parse import urlencode
from pct.formatting import format_euro_it
from .repository import PracticeEngineRepository


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _euro(value: Any) -> str:
    return format_euro_it(value)


def _primary(rows: list[Any]) -> Any | None:
    return rows[0] if rows else None


def _query_url(path: str, **params: Any) -> str:
    cleaned = {key: _text(value) for key, value in params.items() if _text(value)}
    return f"{path}?{urlencode(cleaned)}" if cleaned else path


def _economic_summary(
    preventivo: Any | None,
    conferimento: Any | None,
    parcelle: list[Any],
    repository: PracticeEngineRepository,
    fascicolo_id: str,
    *,
    fascicolo: Any | None = None,
) -> dict[str, Any]:
    paid = [
        item
        for item in parcelle
        if _enum_value(getattr(item, "stato", "")).upper() in {"PAGATA", "SALDATA"} or _text(getattr(item, "data_pagamento", ""))
    ]
    paid_ids = {_text(getattr(item, "id", "")) for item in paid}
    primary_parcella = _primary(parcelle)
    unpaid_parcella = next((item for item in parcelle if _text(getattr(item, "id", "")) not in paid_ids), primary_parcella)
    preventivo_id = _text(getattr(preventivo, "id", ""))
    conferimento_id = _text(getattr(conferimento, "id", ""))
    parcella_id = _text(getattr(primary_parcella, "id", ""))
    payment_parcella_id = _text(getattr(unpaid_parcella, "id", ""))
    cliente_id = (
        _text(getattr(preventivo, "id_cliente", ""))
        or _text(getattr(conferimento, "id_cliente", ""))
        or _text(getattr(primary_parcella, "id_cliente", ""))
        or _text(getattr(fascicolo, "id_cliente", ""))
    )
    preventivo_href = f"/preventivi/p/{preventivo_id}" if preventivo_id else _query_url(
        "/preventivi/nuovo",
        id_fascicolo=fascicolo_id,
        id_cliente=cliente_id,
        from_page="fascicolo",
    )
    conferimento_href = f"/preventivi/conferimento/{conferimento_id}" if conferimento_id else _query_url(
        "/preventivi/conferimento/nuovo",
        id_preventivo=preventivo_id,
        id_fascicolo=fascicolo_id,
        id_cliente=cliente_id,
        from_page="fascicolo",
    )
    proforma_href = _query_url("/fatturazione", id_documento=parcella_id) if parcella_id else _query_url(
        "/fatturazione/nuova",
        id_fascicolo=fascicolo_id,
        id_cliente=cliente_id,
        id_preventivo=preventivo_id,
    )
    payment_href = _query_url(
        "/incassi-pagamenti",
        id_fascicolo=fascicolo_id,
        id_parcella=payment_parcella_id or parcella_id,
    ) if (payment_parcella_id or parcella_id) else proforma_href
    emitted = bool(parcelle)
    total = sum(float(getattr(item, "netto_a_pagare", 0.0) or getattr(item, "totale", 0.0) or 0.0) for item in parcelle)
    override = [event for event in repository.list_audit(fascicolo_id) if getattr(event, "event_type", "") == "ECONOMIC_OVERRIDE"]
    return {
        "preventivoAccepted": bool(preventivo and (_enum_value(getattr(preventivo, "stato", "")).upper() in {"ACCETTATO", "CONVERTITO"} or _text(getattr(preventivo, "accettato_il", "")))),
        "preventivoId": preventivo_id,
        "preventivoDate": _text(getattr(preventivo, "accettato_il", "")),
        "preventivoHref": preventivo_href,
        "conferimentoSigned": bool(conferimento and (getattr(conferimento, "firma_cliente_eseguita", False) or _text(getattr(conferimento, "firma_cliente_il", "")))),
        "conferimentoId": conferimento_id,
        "conferimentoDate": _text(getattr(conferimento, "firma_cliente_il", "")),
        "conferimentoHref": conferimento_href,
        "proformaIssued": emitted,
        "proformaHref": proforma_href,
        "primaryParcellaId": parcella_id,
        "paymentRegistered": bool(paid),
        "paymentHref": payment_href,
        "paymentParcellaId": payment_parcella_id,
        "invoiceIssued": emitted,
        "agreedFee": _euro(getattr(conferimento, "compenso_pattuito", 0.0) or getattr(preventivo, "totale", 0.0)),
        "expenses": _euro(getattr(preventivo, "totale_spese", 0.0) or getattr(preventivo, "anticipazioni_art15", 0.0)),
        "contributoUnificato": _euro(getattr(preventivo, "contributo_unificato", 0.0)),
        "totalDocuments": len(parcelle),
        "totalValue": _euro(total),
        "overrides": [
            {"id": event.id, "reason": event.reason, "message": event.message, "createdAt": event.created_at}
            for event in override
        ],
        "links": [
            {"label": "Preventivo", "href": preventivo_href},
            {"label": "Conferimento", "href": conferimento_href},
            {"label": "Parcella", "href": proforma_href},
            {"label": "Pagamento", "href": payment_href},
        ],
    }
