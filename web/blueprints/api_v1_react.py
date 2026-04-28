"""Endpoint ponte per la migrazione React progressiva.

Questi endpoint restano sottili: espongono dati normalizzati alla shell React
riusando i repository e i servizi esistenti, senza creare una seconda source of
truth frontend.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request

from pct import __version__ as APP_VERSION
from pct.fatturazione import StatoParcella
from pct.workspace_intelligente import WorkspaceIntelligenteService
from web.helpers import (
    get_agenda,
    get_calendar_sync,
    get_fascicoli,
    get_fatturazione,
    get_giurisprudenza,
    get_scadenziario,
    studio_nome,
)

api_v1_react = Blueprint("api_v1_react", __name__, url_prefix="/api/v1/ui")


def _api_key_valida() -> bool:
    api_key = str(current_app.config.get("API_KEY", "") or "")
    return bool(api_key and request.headers.get("X-API-Key") == api_key)


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return jsonify({"errore": "Autenticazione richiesta.", "codice": 401}), 401

    return wrapper


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workspace_overview() -> dict[str, Any]:
    service = WorkspaceIntelligenteService(
        agenda=get_agenda(),
        scadenziario=get_scadenziario(),
        fascicoli=get_fascicoli(),
        calendar_sync=get_calendar_sync(),
        giurisprudenza=get_giurisprudenza(),
        snapshot_path=str(current_app.config.get("WORKSPACE_INTELLIGENCE_DB", "")),
    )
    return service.panoramica(horizon_days=14)


def _parcelle_da_incassare() -> float:
    try:
        parcelle = get_fatturazione().tutte()
    except Exception:
        current_app.logger.exception("Calcolo parcelle da incassare non disponibile per React bridge.")
        return 0.0
    escluse = {StatoParcella.PAGATA.value, StatoParcella.ANNULLATA.value}
    totale = 0.0
    for parcella in parcelle:
        stato = getattr(getattr(parcella, "stato", ""), "value", getattr(parcella, "stato", ""))
        if str(stato) in escluse:
            continue
        totale += float(getattr(parcella, "netto_a_pagare", 0.0) or 0.0)
    return round(totale, 2)


def _euro(value: float) -> str:
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _count_agenda_oggi() -> int:
    today = date.today()
    try:
        appuntamenti = get_agenda().tutti()
    except Exception:
        current_app.logger.exception("Agenda non disponibile per React bridge.")
        return 0
    count = 0
    for item in appuntamenti:
        raw = getattr(item, "data_ora_dt", None) or getattr(item, "data_ora", "")
        try:
            giorno = raw.date() if hasattr(raw, "date") else datetime.fromisoformat(str(raw)[:19]).date()
        except (TypeError, ValueError):
            continue
        if giorno == today:
            count += 1
    return count


def _fascicoli_preview(limit: int = 5) -> list[dict[str, Any]]:
    try:
        fascicoli = get_fascicoli().tutti(archiviati=False)
    except Exception:
        current_app.logger.exception("Fascicoli non disponibili per React bridge.")
        return []
    out: list[dict[str, Any]] = []
    for fascicolo in fascicoli[:limit]:
        out.append(
            {
                "id": str(getattr(fascicolo, "id", "")),
                "title": str(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo"),
                "rg": str(getattr(fascicolo, "numero_rg", "") or "RG non impostato"),
                "office": str(getattr(fascicolo, "tribunale", "") or "Ufficio non impostato"),
                "status": str(getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", ""))),
                "client": str(getattr(fascicolo, "id_cliente", "") or ""),
                "counterparty": str(getattr(fascicolo, "controparte", "") or ""),
                "nextHearing": "",
                "riskScore": 0,
            }
        )
    return out


def _count_fascicoli_attivi() -> int:
    try:
        return len(get_fascicoli().tutti(archiviati=False))
    except Exception:
        current_app.logger.exception("Conteggio fascicoli non disponibile per React bridge.")
        return 0


@api_v1_react.get("/bootstrap")
@_richiedi_auth
def bootstrap():
    utente = g.get("utente_corrente")
    tenant = g.get("tenant")
    return jsonify(
        {
            "product": "IUSENTRA",
            "version": APP_VERSION,
            "shell": "react",
            "mounted_at": "/app-v2",
            "generated_at": _iso_now(),
            "studio": {
                "nome": studio_nome(),
                "tenant": getattr(tenant, "slug", "") if tenant else "",
            },
            "user": {
                "id": getattr(utente, "id", "") if utente else "",
                "username": getattr(utente, "username", "") if utente else "",
                "role": str(getattr(getattr(utente, "ruolo", ""), "value", getattr(utente, "ruolo", "")))
                if utente
                else "api",
            },
            "route_flags": {
                "replace_dashboard": False,
                "replace_fascicoli": False,
                "replace_scadenziario": False,
                "replace_telematico": False,
                "replace_preventivi": False,
                "replace_sito_studio": False,
            },
        }
    )


@api_v1_react.get("/dashboard")
@_richiedi_auth
def dashboard():
    try:
        overview = _workspace_overview()
        summary = dict(overview.get("summary") or {})
        fascicoli = _fascicoli_preview()
        stats = {
            "todayAppointments": _count_agenda_oggi(),
            "urgentDeadlines": int(summary.get("scadenze_urgenti") or 0),
            "openMatters": _count_fascicoli_attivi(),
            "unpaidAmount": _euro(_parcelle_da_incassare()),
            "documentsToReview": int(summary.get("notifiche_scadenze") or 0),
        }
        return jsonify(
            {
                "source": "workspace_intelligente",
                "generated_at": overview.get("generated_at") or _iso_now(),
                "stats": stats,
                "actions": list(overview.get("actions") or []),
                "fascicoli": fascicoli,
            }
        )
    except Exception as exc:
        current_app.logger.exception("Errore dashboard React bridge: %s", exc)
        return jsonify(
            {
                "source": "errore_controllato",
                "generated_at": _iso_now(),
                "stats": {
                    "todayAppointments": 0,
                    "urgentDeadlines": 0,
                    "openMatters": 0,
                    "unpaidAmount": "€ 0,00",
                    "documentsToReview": 0,
                },
                "actions": [],
                "fascicoli": [],
                "warning": "Dati non disponibili. La UI storica resta la fonte operativa.",
            }
        ), 200


@api_v1_react.get("/fascicoli/<id_fascicolo>")
@_richiedi_auth
def fascicolo(id_fascicolo: str):
    fasc = get_fascicoli().get(id_fascicolo)
    if not fasc:
        return jsonify({"errore": "Fascicolo non trovato.", "codice": 404}), 404
    return jsonify(fasc.to_dict())


@api_v1_react.post("/lex/chat")
@_richiedi_auth
def lex_chat():
    return jsonify(
        {
            "answer": (
                "La conversazione Lex dentro la shell React è in migrazione controllata. "
                "Per attività operative usa ancora il pannello Lex della UI attuale, così restano "
                "attivi retrieval, fonti, guardrail e audit completi."
            ),
            "source": "react_migration_guard",
            "generated_at": _iso_now(),
        }
    )
