"""Orchestrazione timer attivita per la top bar React."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pct.timesheet import StatoTimesheet
from web.helpers import get_clienti, get_fascicoli, get_time_tracking, get_timesheet
from web.services import topbar_timer_contesto as contesto
from web.services.topbar_operational import ROME_TZ, TopbarApiError, _clean_text, _user_id, _username

ACTIVITY_LABELS = {
    "call": "Telefonata",
    "drafting": "Redazione atto",
    "research": "Studio pratica",
    "hearing": "Udienza",
    "meeting": "Riunione",
    "email": "Email/PEC",
    "filing": "Deposito",
    "other": "Attività",
}


def active_timer_payload(user: Any) -> dict[str, Any]:
    timer = get_time_tracking().active_for_user(_user_id(user))
    return {"ok": True, "timer": _timer_to_api(timer) if timer else None, **_contesto_utente(user)}


def search_links_payload(query: str, case_id: str = "", client_id: str = "") -> dict[str, Any]:
    if case_id or client_id:
        return {"ok": True, "items": contesto.per_identificativo(case_id, client_id)}
    return {"ok": True, "items": contesto.cerca(query)}


def _contesto_utente(user: Any) -> dict[str, Any]:
    oggi = datetime.now(ROME_TZ).date()
    return {
        "today": contesto.riepilogo_oggi(_user_id(user), _username(user), oggi),
        "recent": contesto.recenti(_user_id(user), _username(user)),
    }


def _collegamenti_validati(payload: dict[str, Any]) -> tuple[str, str]:
    case_id = _clean_text(payload.get("caseId") or payload.get("case_id") or "", limit=120)
    client_id = _clean_text(payload.get("clientId") or payload.get("client_id") or "", limit=120)
    if case_id and not get_fascicoli().get(case_id):
        raise TopbarApiError("Fascicolo non trovato.", 404)
    if client_id and not get_clienti().get(client_id):
        raise TopbarApiError("Cliente non trovato.", 404)
    if case_id and not client_id:
        fascicolo = get_fascicoli().get(case_id)
        client_id = _clean_text(getattr(fascicolo, "id_cliente", "")) if fascicolo else ""
    return case_id, client_id


def start_timer_payload(user: Any, payload: dict[str, Any]) -> dict[str, Any]:
    case_id, client_id = _collegamenti_validati(payload)
    try:
        timer = get_time_tracking().start(
            user_id=_user_id(user),
            username=_username(user),
            case_id=case_id,
            client_id=client_id,
            activity_type=_clean_text(payload.get("activityType") or payload.get("activity_type") or "other", limit=40),
            description=_clean_text(payload.get("description") or ""),
        )
    except RuntimeError as exc:
        raise TopbarApiError("Hai già un timer in corso: fermalo prima di avviarne un altro.", 409) from exc
    return {"ok": True, "timer": _timer_to_api(timer)}


def update_timer_payload(user: Any, timer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Correzione del timer in corso: descrizione, tipo, fascicolo o cliente."""

    modifiche: dict[str, Any] = {}
    if "description" in payload:
        modifiche["description"] = _clean_text(payload.get("description") or "")
    if "activityType" in payload:
        modifiche["activity_type"] = _clean_text(payload.get("activityType") or "other", limit=40)
    if "caseId" in payload or "clientId" in payload:
        case_id, client_id = _collegamenti_validati(payload)
        modifiche.update(case_id=case_id, client_id=client_id)
    try:
        timer = get_time_tracking().aggiorna(timer_id, _user_id(user), **modifiche)
    except KeyError as exc:
        raise TopbarApiError("Timer non trovato.", 404) from exc
    except PermissionError as exc:
        raise TopbarApiError("Timer non autorizzato.", 403) from exc
    return {"ok": True, "timer": _timer_to_api(timer)}


def pause_timer_payload(user: Any, timer_id: str) -> dict[str, Any]:
    timer = _timer_action(user, timer_id, "pause")
    return {"ok": True, "timer": _timer_to_api(timer)}


def resume_timer_payload(user: Any, timer_id: str) -> dict[str, Any]:
    timer = _timer_action(user, timer_id, "resume")
    return {"ok": True, "timer": _timer_to_api(timer)}


def stop_timer_payload(user: Any, timer_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ferma il timer e registra il tempo nel timesheet; «discard» lo ferma senza registrare."""

    dati = payload or {}
    if "description" in dati:
        update_timer_payload(user, timer_id, {"description": dati.get("description")})
    timer = _timer_action(user, timer_id, "stop")
    time_entry = None if dati.get("discard") else _save_timer_to_timesheet(user, timer)
    saved = None
    if time_entry is not None:
        info = contesto.collegamenti(time_entry.id_fascicolo, time_entry.id_cliente)
        saved = {"minutes": int(time_entry.minuti), "description": time_entry.descrizione,
                 "caseLabel": info["caseLabel"], "href": "/timesheet"}
    return {
        "ok": True,
        "timer": _timer_to_api(timer),
        "timeEntry": {"id": time_entry.id, "href": "/timesheet"} if time_entry else None,
        "saved": saved,
        "message": (f"Registrati {saved['minutes']} min nel timesheet." if saved else "Timer fermato senza registrare il tempo."),
        **_contesto_utente(user),
    }


def _timer_action(user: Any, timer_id: str, action: str):
    repo = get_time_tracking()
    try:
        if action == "pause":
            return repo.pause(timer_id, _user_id(user))
        if action == "resume":
            return repo.resume(timer_id, _user_id(user))
        return repo.stop(timer_id, _user_id(user))
    except KeyError as exc:
        raise TopbarApiError("Timer non trovato.", 404) from exc
    except PermissionError as exc:
        raise TopbarApiError("Timer non autorizzato.", 403) from exc


def _timer_to_api(timer: Any | None) -> dict[str, Any] | None:
    if timer is None:
        return None
    return {
        **contesto.collegamenti(timer.case_id, timer.client_id),
        "id": timer.id,
        "caseId": timer.case_id or None,
        "clientId": timer.client_id or None,
        "activityType": timer.activity_type,
        "description": timer.description or None,
        "startedAt": timer.started_at,
        "pausedAt": timer.paused_at or None,
        "endedAt": timer.ended_at or None,
        "elapsedSeconds": int(timer.current_elapsed()),
        "status": timer.status,
    }


def _save_timer_to_timesheet(user: Any, timer: Any):
    if getattr(timer, "status", "") != "stopped":
        return None
    if getattr(timer, "timesheet_entry_id", ""):
        return None
    minutes = contesto.minuti_da_secondi(int(timer.elapsed_seconds or 0))
    description = _clean_text(timer.description) or ACTIVITY_LABELS.get(timer.activity_type, "Attività")
    entry = get_timesheet().crea(
        descrizione=description,
        minuti=minutes,
        id_fascicolo=timer.case_id,
        id_cliente=timer.client_id,
        id_utente=_user_id(user),
        username=_username(user),
        data_attivita=(getattr(timer, "ended_at", "") or datetime.now(ROME_TZ).isoformat())[:10],
        fatturabile=True,
        stato=StatoTimesheet.APERTO,
        origine="timer-topbar",
        dati_json={"timer_id": timer.id, "activity_type": timer.activity_type},
    )
    get_time_tracking().collega_timesheet(timer.id, _user_id(user), entry.id)
    return entry
