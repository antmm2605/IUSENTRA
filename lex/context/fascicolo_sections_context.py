"""Contesto sezionato del fascicolo per Lex."""

from __future__ import annotations

from typing import Any

from pct.fascicolo_workspace import build_fascicolo_workspace
from web.helpers import get_agenda, get_fascicoli, get_scadenziario

from .document_context import load_document_context


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _sort_value(row: dict[str, Any]) -> str:
    return str(
        row.get("ordine_data")
        or row.get("data_ora")
        or row.get("timestamp")
        or row.get("data")
        or row.get("data_documento")
        or row.get("data_caricamento")
        or ""
    ).strip()


def _sorted_rows(rows: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    return sorted(rows, key=_sort_value, reverse=reverse)


def _serialize_attivita(attivita) -> dict[str, Any]:
    return {
        "id": getattr(attivita, "id", ""),
        "fonte": "attivita_processuale",
        "tipo": getattr(getattr(attivita, "tipo", None), "value", ""),
        "titolo": getattr(attivita, "titolo", ""),
        "descrizione": getattr(attivita, "descrizione", ""),
        "data": getattr(attivita, "data", ""),
        "ordine_data": getattr(attivita, "data", ""),
        "esito": getattr(getattr(attivita, "esito", None), "value", ""),
        "luogo": getattr(attivita, "luogo", ""),
        "note": getattr(attivita, "note", ""),
        "id_documento": getattr(attivita, "id_documento", ""),
        "id_deposito_pct": getattr(attivita, "id_deposito_pct", ""),
        "email_mittente": getattr(attivita, "email_mittente", ""),
        "email_oggetto": getattr(attivita, "email_oggetto", ""),
        "avvocato": getattr(attivita, "avvocato", ""),
    }


def _serialize_deposito(deposito, *, fonte: str) -> dict[str, Any]:
    return {
        "id": getattr(deposito, "id", ""),
        "fonte": fonte,
        "tipo_atto": getattr(deposito, "tipo_atto", ""),
        "titolo": getattr(deposito, "nome_atto_principale", "") or getattr(deposito, "tipo_atto", ""),
        "timestamp": getattr(deposito, "timestamp", ""),
        "ordine_data": getattr(deposito, "timestamp", ""),
        "stato": getattr(deposito, "stato", ""),
        "esito_controlli": getattr(deposito, "esito_controlli", ""),
        "messaggio": getattr(deposito, "messaggio", ""),
        "note": getattr(deposito, "note", ""),
        "pec_destinatario": getattr(deposito, "pec_destinatario", ""),
        "id_deposito_esterno": getattr(deposito, "id_deposito_esterno", ""),
        "fonte_portale": getattr(deposito, "fonte_portale", ""),
        "servizio_portale": getattr(deposito, "servizio_portale", ""),
        "documenti_count": len(list(getattr(deposito, "documenti_ids", []) or [])),
        "documenti_portale_count": len(list(getattr(deposito, "documenti_portale", []) or [])),
    }


def _serialize_scadenza(scadenza) -> dict[str, Any]:
    data = getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "data", "")
    return {
        "id": getattr(scadenza, "id", ""),
        "fonte": "scadenza",
        "tipo": getattr(getattr(scadenza, "tipo", None), "value", ""),
        "titolo": getattr(scadenza, "titolo", ""),
        "descrizione": getattr(scadenza, "descrizione", ""),
        "data": data,
        "ordine_data": data,
        "stato": getattr(getattr(scadenza, "stato", None), "value", ""),
        "priorita": getattr(getattr(scadenza, "priorita", None), "value", ""),
        "note": getattr(scadenza, "note", ""),
        "id_fascicolo": getattr(scadenza, "id_fascicolo", ""),
    }


def _serialize_appuntamento(appuntamento) -> dict[str, Any]:
    return {
        "id": getattr(appuntamento, "id", ""),
        "fonte": "agenda",
        "tipo": getattr(getattr(appuntamento, "tipo", None), "value", ""),
        "titolo": getattr(appuntamento, "titolo", ""),
        "descrizione": getattr(appuntamento, "note", ""),
        "data_ora": getattr(appuntamento, "data_ora", ""),
        "ordine_data": getattr(appuntamento, "data_ora", ""),
        "stato": getattr(getattr(appuntamento, "stato", None), "value", ""),
        "luogo": getattr(appuntamento, "luogo", ""),
        "tribunale": getattr(appuntamento, "tribunale", ""),
        "procedimento": getattr(appuntamento, "procedimento", ""),
    }


def _agenda_fascicolo_rows(target_id: str, fascicolo) -> list[Any]:
    keys = {
        _clean_spaces(target_id).lower(),
        _clean_spaces(getattr(fascicolo, "id_cliente", "")).lower(),
        _clean_spaces(getattr(fascicolo, "numero", "")).lower(),
        _clean_spaces(getattr(fascicolo, "numero_rg", "")).lower(),
        _clean_spaces(getattr(fascicolo, "rg_completo", "")).lower(),
    }
    keys.discard("")
    rows: list[Any] = []
    for appuntamento in get_agenda().tutti():
        procedimento = _clean_spaces(getattr(appuntamento, "procedimento", "")).lower()
        id_cliente = _clean_spaces(getattr(appuntamento, "id_cliente", "")).lower()
        if keys and procedimento not in keys and id_cliente not in keys:
            continue
        rows.append(appuntamento)
    return rows


def _scadenze_fascicolo_rows(target_id: str) -> list[Any]:
    rows: list[Any] = []
    for scadenza in get_scadenziario().tutte(solo_aperte=False):
        if _clean_spaces(getattr(scadenza, "id_fascicolo", "")) != target_id:
            continue
        rows.append(scadenza)
    return rows


def load_fascicolo_sections_context(
    *,
    pratica_id: str = "",
    fascicolo_id: str = "",
    documenti: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    target_id = _clean_spaces(pratica_id) or _clean_spaces(fascicolo_id)
    if not target_id:
        return {}

    gestore = get_fascicoli()
    fascicolo = gestore.get(target_id)
    if not fascicolo:
        return {}

    documenti_rows = list(documenti or load_document_context(pratica_id=target_id, fascicolo_id=target_id, limit=None))
    agenda_rows = _agenda_fascicolo_rows(target_id, fascicolo)
    scadenze_rows = _scadenze_fascicolo_rows(target_id)
    workspace = build_fascicolo_workspace(
        fascicolo,
        apps=agenda_rows,
        scadenze=scadenze_rows,
    )

    attivita_processuali = [_serialize_attivita(row) for row in list(workspace.get("attivita_processuali") or [])]
    udienze_scadenze = _sorted_rows(
        [
            *[_serialize_attivita(row) for row in list(workspace.get("udienze_attivita") or [])],
            *[_serialize_deposito(row, fonte="deposito_udienza_scadenza") for row in list(workspace.get("udienze_depositi") or [])],
            *[_serialize_scadenza(row) for row in list(workspace.get("scadenze") or [])],
            *[_serialize_appuntamento(row) for row in list(workspace.get("appuntamenti") or [])],
        ],
        reverse=False,
    )
    comunicazioni_cancelleria = _sorted_rows(
        [
            *[_serialize_attivita(row) for row in list(workspace.get("comunicazioni_attivita") or [])],
            *[_serialize_deposito(row, fonte="deposito_comunicazione_cancelleria") for row in list(workspace.get("comunicazioni_depositi") or [])],
        ],
        reverse=True,
    )
    istanze = _sorted_rows(
        [
            *[
                {
                    **row,
                    "fonte": "documento_istanza",
                    "titolo": row.get("nome", ""),
                    "ordine_data": row.get("data_documento") or row.get("data_caricamento") or "",
                }
                for row in documenti_rows
                if "istanza" in _clean_spaces(f"{row.get('nome', '')} {row.get('note', '')} {row.get('tipo', '')}").lower()
            ],
            *[_serialize_deposito(row, fonte="deposito_istanza") for row in list(workspace.get("istanze_depositi") or [])],
        ],
        reverse=True,
    )

    return {
        "counts": dict(workspace.get("counts") or {}),
        "documenti_buckets": dict(workspace.get("documenti_buckets") or {}),
        "attivita_processuali": attivita_processuali,
        "documenti_fascicolo": documenti_rows,
        "udienze_scadenze": udienze_scadenze,
        "comunicazioni_cancelleria": comunicazioni_cancelleria,
        "istanze": istanze,
    }
