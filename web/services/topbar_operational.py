"""Payload operativi per la top bar React."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from flask import current_app, g, session

from pct.agenda import TipoAppuntamento
from pct.email_client import CartellaEmail, GestioneEmailRicevute
from pct.fatturazione import StatoParcella
from pct.fascicolo_document_presidio import duplicate_practice_groups
from pct.global_search.repository import GlobalSearchRepository
from pct.global_search.service import GlobalSearchService, default_global_search_db_path
from pct.notifiche_legali import released_office_documents_from_pec
from pct.pec_operational_cleanup import is_legacy_pec_agenda_item, is_legacy_pec_deadline
from pct.scadenziario import PrioritaTermine, StatoTermine
from pct.notifications import NotificationRecord, NotificationServiceError
from web.services.notifications_runtime import (
    build_notification_service,
    current_tenant_id as _notification_tenant_id,
    current_user_id as _notification_user_id,
)
from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_fatturazione,
    get_legal_intelligence,
    get_pagamenti,
    get_preventivi,
    get_scadenziario,
    get_soggetti,
    get_timesheet,
    tenant_corrente,
)

ROME_TZ = ZoneInfo("Europe/Rome")
SEARCH_MIN_LENGTH = 2
SEARCH_MAX_LENGTH = 120
TEXT_MAX = 500

TYPE_MAP = {
    "fascicolo": "case",
    "cliente": "client",
    "soggetto": "client",
    "parte": "client",
    "pratica": "matter",
    "preventivo": "matter",
    "conferimento": "matter",
    "scadenza": "deadline",
    "termine": "deadline",
    "appuntamento": "hearing",
    "udienza": "hearing",
    "documento": "document",
    "atto": "document",
    "attivita": "activity",
    "comunicazione": "communication",
    "email": "communication",
    "pec": "communication",
    "messaggio": "communication",
    "fattura": "invoice",
    "parcella": "invoice",
    "pagamento": "invoice",
    "deposito": "communication",
}

class TopbarApiError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _clean_text(value: Any, *, limit: int = TEXT_MAX) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _react_href(value: Any) -> str | None:
    href = _clean_text(value, limit=900)
    if not href:
        return None
    if href.startswith(("http://", "https://", "mailto:", "tel:")):
        return href
    split = urlsplit(href)
    path = split.path or href
    lower = path.rstrip("/").lower() or "/"
    if lower in {"/notifiche", "/notifiche-whatsapp"}:
        return "/impostazioni?tab=notifiche"

    agenda_match = re.match(r"^/agenda/([^/]+)/modifica/?$", path, flags=re.IGNORECASE)
    if agenda_match:
        path = f"/agenda/{agenda_match.group(1)}"
        split = split._replace(path=path, query="", fragment="")
        return urlunsplit(split)

    deadline_match = re.match(r"^/scadenziario/([^/]+)/modifica/?$", path, flags=re.IGNORECASE)
    if deadline_match:
        path = f"/scadenziario/{deadline_match.group(1)}"
        split = split._replace(path=path, query="", fragment="")
        return urlunsplit(split)

    email_match = re.match(r"^/email/([^/?#]+)$", path, flags=re.IGNORECASE)
    if email_match and email_match.group(1).lower() not in {"messaggio", "scrivi"}:
        split = split._replace(path=f"/email/messaggio/{email_match.group(1)}")
        return urlunsplit(split)

    ordinary_match = re.match(r"^/email-ordinaria/([^/?#]+)$", path, flags=re.IGNORECASE)
    if ordinary_match and ordinary_match.group(1).lower() not in {"messaggio", "scrivi"}:
        split = split._replace(path=f"/email-ordinaria/messaggio/{ordinary_match.group(1)}")
        return urlunsplit(split)

    return href


def _dedupe_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in items:
        href = _react_href(item.get("href"))
        row = dict(item)
        row["href"] = href
        key = (
            _clean_text(row.get("type"), limit=80).lower(),
            _clean_text(row.get("id"), limit=220).lower(),
            _clean_text(href, limit=500).lower(),
            _clean_text(row.get("title"), limit=220).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value or "")


def _cfg_value(key: str, default: str = "") -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if key in paths:
        return str(paths[key])
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return str(current_app.config.get(key, default))


def _tenant_id() -> str:
    tenant = tenant_corrente()
    return str(getattr(tenant, "id", "") or getattr(tenant, "slug", "") or "default")


def _user_id(user: Any | None = None) -> str:
    current = user if user is not None else g.get("utente_corrente")
    return str(getattr(current, "id", "") or getattr(current, "username", "") or "").strip()


def _username(user: Any | None = None) -> str:
    current = user if user is not None else g.get("utente_corrente")
    return str(getattr(current, "username", "") or getattr(current, "email", "") or "").strip()


def _has_perm(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    if callable(checker):
        return bool(checker(permission))
    return True


def _has_any_perm(user: Any, permissions: list[str]) -> bool:
    return any(_has_perm(user, permission) for permission in permissions)


def _require_any_permission(user: Any, permissions: list[str]) -> None:
    if not _has_any_perm(user, permissions):
        raise TopbarApiError("Permesso insufficiente.", 403)


def _parse_day(value: str | None = None) -> date:
    text = str(value or "").strip()
    if not text:
        return datetime.now(ROME_TZ).date()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise TopbarApiError("Formato data non valido. Usa YYYY-MM-DD.", 400) from exc


def _parse_iso(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ROME_TZ)
    return parsed.astimezone(ROME_TZ)


def _date_iso(day: date) -> str:
    return day.isoformat()


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=ROME_TZ)


def _priority_from_deadline(scadenza: Any, day: date | None = None) -> str:
    due = _deadline_date(scadenza)
    current = day or datetime.now(ROME_TZ).date()
    priority = _enum_value(getattr(scadenza, "priorita", ""))
    if due and due < current:
        return "urgent"
    if priority == PrioritaTermine.CRITICA.value or bool(getattr(scadenza, "perentorio", False)):
        return "urgent"
    if priority == PrioritaTermine.ALTA.value or (due and (due - current).days <= 2):
        return "important"
    return "normal"


def _priority_weight(priority: str) -> int:
    return {"urgent": 0, "important": 1, "normal": 2}.get(priority, 2)


def _deadline_date(scadenza: Any) -> date | None:
    value = getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "legal_due_at", "")
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _deadline_status(scadenza: Any, today: date | None = None) -> str:
    state = _enum_value(getattr(scadenza, "stato", ""))
    if state == StatoTermine.COMPLETATO.value:
        return "completed"
    due = _deadline_date(scadenza)
    if due and due < (today or datetime.now(ROME_TZ).date()) and state != StatoTermine.COMPLETATO.value:
        return "overdue"
    return "open"


def _case_lookup() -> dict[str, Any]:
    try:
        return {item.id: item for item in get_fascicoli().tutti(archiviati=True)}
    except Exception:
        current_app.logger.info("Top bar: fascicoli non disponibili per lookup", exc_info=True)
        return {}


def _client_lookup() -> dict[str, Any]:
    try:
        return {item.id: item for item in get_clienti().tutti()}
    except Exception:
        current_app.logger.info("Top bar: clienti non disponibili per lookup", exc_info=True)
        return {}


def _client_name(clienti: dict[str, Any], client_id: str, fallback: str = "") -> str:
    cliente = clienti.get(str(client_id or ""))
    if not cliente:
        return _clean_text(fallback)
    return _clean_text(getattr(cliente, "nome_completo", "") or fallback)


def _case_title(fascicoli: dict[str, Any], case_id: str) -> str:
    fascicolo = fascicoli.get(str(case_id or ""))
    if not fascicolo:
        return ""
    return _clean_text(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "numero", ""))


def _duplicate_practice_today_items(fascicoli: dict[str, Any], day: date) -> list[dict[str, Any]]:
    rows = [
        item
        for item in fascicoli.values()
        if _enum_value(getattr(item, "stato", "")).upper() not in {"ARCHIVIATO", "DEFINITO"}
    ]
    items: list[dict[str, Any]] = []
    for index, group in enumerate(duplicate_practice_groups(rows)):
        ids = [str(value) for value in (group.get("ids") or []) if str(value or "").strip()]
        first_id = ids[0] if ids else None
        items.append(
            {
                "id": f"duplicate-case-{index}-{group.get('key')}",
                "type": "task",
                "title": "Verificare pratiche doppie per cliente e RG",
                "time": None,
                "date": day.isoformat(),
                "priority": "important",
                "href": f"/fascicoli?rg={quote(str(group.get('rg') or '').replace('RG ', ''), safe='')}",
                "caseId": first_id,
                "clientName": _clean_text(group.get("client")) or None,
                "status": f"{int(group.get('count') or len(ids) or 0)} fascicoli da confrontare",
            }
        )
    return items


def _email_manager() -> GestioneEmailRicevute:
    return GestioneEmailRicevute(_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"))


def _is_raw_pct_deposit_receipt_email(email: Any) -> bool:
    subject = _clean_text(getattr(email, "oggetto", ""), limit=500).lower()
    body = _clean_text(
        " ".join(
            [
                str(getattr(email, "corpo_testo", "") or ""),
                str(getattr(email, "corpo_html", "") or ""),
            ]
        ),
        limit=2500,
    ).lower()
    status = _clean_text(getattr(email, "stato_pct", ""), limit=80).upper()
    haystack = f"{subject} {body}"
    technical_subject = any(
        token in haystack
        for token in (
            "accettazione deposito telematico",
            "esito controlli automatici deposito telematico",
            "esito controlli deposito",
            "idbusta",
        )
    )
    technical_state = status in {
        "ACCETTATO_PEC",
        "CONSEGNATO",
        "WARN_CONTROLLI",
        "ERRORE_CONTROLLI",
        "ACCETTATO_CANCELLERIA",
        "RIFIUTATO_CANCELLERIA",
    } and "deposito" in haystack
    return bool(technical_subject or technical_state)


def _global_search_db_path() -> Path:
    configured = current_app.config.get("GLOBAL_SEARCH_INDEX")
    if configured:
        return Path(str(configured))
    return default_global_search_db_path(_cfg_value("SEARCH_INDEX", "./search/index.db"))


def _global_search_context() -> dict[str, Any]:
    context: dict[str, Any] = {
        "tenant_id": _tenant_id(),
        "search_index_path": _cfg_value("SEARCH_INDEX", ""),
        "fascicoli": None,
        "clienti": None,
        "soggetti": None,
        "scadenziario": None,
        "agenda": None,
        "preventivi": None,
        "fatturazione": None,
        "pagamenti": None,
        "legal_intelligence": None,
    }
    factories = {
        "fascicoli": get_fascicoli,
        "clienti": get_clienti,
        "soggetti": get_soggetti,
        "scadenziario": get_scadenziario,
        "agenda": get_agenda,
        "preventivi": get_preventivi,
        "fatturazione": get_fatturazione,
        "pagamenti": get_pagamenti,
        "legal_intelligence": get_legal_intelligence,
    }
    for key, factory in factories.items():
        try:
            context[key] = factory()
        except Exception:
            current_app.logger.info("Top bar: modulo %s non disponibile per ricerca", key, exc_info=True)
    return context


def global_search_payload(user: Any, query: str, limit: int = 20) -> dict[str, Any]:
    _require_any_permission(
        user,
        [
            "fascicoli.leggi",
            "clienti.leggi",
            "agenda.leggi",
            "scadenziario.leggi",
            "messaggi.leggi",
        ],
    )
    q = _clean_text(query, limit=SEARCH_MAX_LENGTH)
    if len(q) < SEARCH_MIN_LENGTH:
        raise TopbarApiError("Inserisci almeno 2 caratteri.", 400)
    if len(str(query or "")) > SEARCH_MAX_LENGTH:
        raise TopbarApiError("La ricerca supera la lunghezza massima consentita.", 400)
    safe_limit = max(1, min(int(limit or 20), 50))
    repository = GlobalSearchRepository(_global_search_db_path())
    service = GlobalSearchService(repository)
    try:
        context = _global_search_context()
        stats = service.stats(context)
        if stats.get("total", 0) == 0:
            service.reindex(context)
        raw = service.search(context, q, limit=safe_limit, user=user)
    finally:
        repository.close()

    results = [_search_result_to_topbar(item) for item in raw.get("results", [])]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        grouped.setdefault(item["type"], []).append(item)
    return {
        "ok": True,
        "query": q,
        "total": len(results),
        "results": results,
        "groups": [{"type": key, "items": value} for key, value in grouped.items()],
    }


def _search_result_to_topbar(item: dict[str, Any]) -> dict[str, Any]:
    entity_type = str(item.get("entity_type") or item.get("type") or "").strip().lower()
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    result_type = TYPE_MAP.get(entity_type, entity_type or "matter")
    status = _clean_text(metadata.get("status") or metadata.get("stato") or "")
    priority = _clean_text(metadata.get("priority") or metadata.get("priorita") or "normal").lower()
    if priority not in {"normal", "important", "urgent"}:
        priority = "urgent" if status.upper() in {"SCADUTO", "CRITICA", "URGENTE"} else "normal"
    return {
        "id": str(item.get("entity_id") or item.get("id") or ""),
        "type": result_type,
        "title": _clean_text(item.get("title") or item.get("titolo")),
        "subtitle": _clean_text(item.get("subtitle") or item.get("sottotitolo")) or None,
        "description": _clean_text(item.get("snippet") or item.get("description")) or None,
        "href": _clean_text(item.get("source_url") or item.get("url") or "/global-search"),
        "priority": priority,
        "metadata": {
            "clientName": _clean_text(metadata.get("clientName") or metadata.get("cliente") or "") or None,
            "caseNumber": _clean_text(metadata.get("caseNumber") or metadata.get("numero") or "") or None,
            "date": _clean_text(item.get("date") or metadata.get("date") or metadata.get("data") or "") or None,
            "status": status or None,
        },
    }


def today_payload(user: Any, date_value: str | None = None) -> dict[str, Any]:
    day = _parse_day(date_value)
    items: list[dict[str, Any]] = []
    summary = {
        "hearingsToday": 0,
        "deadlinesToday": 0,
        "tasksToday": 0,
        "urgentItems": 0,
        "unreadCommunications": 0,
    }
    fascicoli = _case_lookup()
    clienti = _client_lookup()

    if _has_perm(user, "fascicoli.leggi"):
        try:
            duplicate_items = _duplicate_practice_today_items(fascicoli, day)
            if duplicate_items:
                summary["tasksToday"] += len(duplicate_items)
                summary["urgentItems"] += len(duplicate_items)
                items.extend(duplicate_items)
        except Exception:
            current_app.logger.info("Top bar oggi: controllo pratiche doppie non disponibile", exc_info=True)

    if _has_perm(user, "agenda.leggi"):
        try:
            for appointment in get_agenda().per_giorno(day):
                if is_legacy_pec_agenda_item(appointment):
                    continue
                if _enum_value(getattr(appointment, "tipo", "")) == TipoAppuntamento.UDIENZA.value:
                    summary["hearingsToday"] += 1
                    item_type = "hearing"
                else:
                    item_type = "appointment"
                dt = getattr(appointment, "data_ora_dt", None) or _parse_iso(getattr(appointment, "data_ora", ""))
                items.append(
                    {
                        "id": appointment.id,
                        "type": item_type,
                        "title": _clean_text(appointment.titolo),
                        "time": dt.strftime("%H:%M") if dt else None,
                        "date": getattr(appointment, "data_ora", ""),
                        "priority": "important" if item_type == "hearing" else "normal",
                        "href": f"/agenda/{appointment.id}/modifica",
                        "caseId": None,
                        "clientName": _clean_text(getattr(appointment, "cliente", "")) or None,
                        "status": _enum_value(getattr(appointment, "stato", "")) or None,
                    }
                )
        except Exception:
            current_app.logger.info("Top bar oggi: agenda non disponibile", exc_info=True)

    if _has_perm(user, "scadenziario.leggi"):
        try:
            for scadenza in get_scadenziario().tutte(solo_aperte=False):
                if is_legacy_pec_deadline(scadenza):
                    continue
                due = _deadline_date(scadenza)
                if due is None:
                    continue
                status = _deadline_status(scadenza, day)
                days = (due - day).days
                if status == "completed":
                    continue
                if due == day:
                    summary["deadlinesToday"] += 1
                if due == day or 0 <= days <= 7 or status == "overdue":
                    priority = _priority_from_deadline(scadenza, day)
                    if priority == "urgent" or status == "overdue":
                        summary["urgentItems"] += 1
                    items.append(
                        {
                            "id": scadenza.id,
                            "type": "deadline",
                            "title": _clean_text(scadenza.titolo),
                            "time": None,
                            "date": due.isoformat(),
                            "priority": priority,
                            "href": f"/scadenziario/{scadenza.id}/modifica",
                            "caseId": getattr(scadenza, "id_fascicolo", "") or None,
                            "clientName": _client_name(
                                clienti,
                                getattr(fascicoli.get(getattr(scadenza, "id_fascicolo", "")), "id_cliente", ""),
                                getattr(fascicoli.get(getattr(scadenza, "id_fascicolo", "")), "nome_cliente", ""),
                            )
                            or None,
                            "status": status,
                        }
                    )
        except Exception:
            current_app.logger.info("Top bar oggi: scadenziario non disponibile", exc_info=True)

    try:
        timesheet = get_timesheet()
        if hasattr(timesheet, "tutte"):
            for entry in timesheet.tutte():
                if str(getattr(entry, "data_attivita", ""))[:10] != day.isoformat():
                    continue
                summary["tasksToday"] += 1
                items.append(
                    {
                        "id": entry.id,
                        "type": "task",
                        "title": _clean_text(entry.descrizione),
                        "time": None,
                        "date": entry.data_attivita,
                        "priority": "normal",
                        "href": "/timesheet",
                        "caseId": getattr(entry, "id_fascicolo", "") or None,
                        "clientName": _client_name(clienti, getattr(entry, "id_cliente", "")) or None,
                        "status": _enum_value(getattr(entry, "stato", "")) or None,
                    }
                )
    except Exception:
        current_app.logger.info("Top bar oggi: timesheet non disponibile", exc_info=True)

    if _has_perm(user, "messaggi.leggi"):
        try:
            unread = _email_manager().tutte(
                cartella=CartellaEmail.INBOX,
                solo_non_lette=True,
                data_da=day.isoformat(),
                data_a=day.isoformat(),
            )
            summary["unreadCommunications"] = len(unread)
            for email in unread[:5]:
                priority = "important" if getattr(email, "e_pst", False) else "normal"
                items.append(
                    {
                        "id": email.id,
                        "type": "communication",
                        "title": _clean_text(email.oggetto) or "Comunicazione senza oggetto",
                        "time": (_parse_iso(email.timestamp) or _start_of_day(day)).strftime("%H:%M"),
                        "date": email.timestamp,
                        "priority": priority,
                        "href": f"/email/{email.id}",
                        "caseId": None,
                        "clientName": None,
                        "status": email.stato,
                    }
                )
        except Exception:
            current_app.logger.info("Top bar oggi: PEC non disponibile", exc_info=True)

    items = _dedupe_items(items)
    items.sort(key=lambda item: (_priority_weight(item["priority"]), item.get("date") or "", item.get("time") or ""))
    return {"ok": True, "date": day.isoformat(), "summary": summary, "items": items[:30]}


def quick_deadlines_payload(user: Any) -> dict[str, Any]:
    _require_any_permission(user, ["scadenziario.leggi"])
    today = datetime.now(ROME_TZ).date()
    tomorrow = today + timedelta(days=1)
    week = today + timedelta(days=7)
    fascicoli = _case_lookup()
    clienti = _client_lookup()
    summary = {"today": 0, "tomorrow": 0, "nextSevenDays": 0, "urgent": 0, "overdue": 0}
    rows: list[dict[str, Any]] = []
    try:
        scadenze = get_scadenziario().tutte(solo_aperte=False)
    except Exception as exc:
        raise TopbarApiError("Scadenziario non disponibile.", 503) from exc
    for scadenza in scadenze:
        if is_legacy_pec_deadline(scadenza):
            continue
        due = _deadline_date(scadenza)
        if due is None:
            continue
        status = _deadline_status(scadenza, today)
        if status == "completed":
            continue
        priority = _priority_from_deadline(scadenza, today)
        if due == today:
            summary["today"] += 1
        if due == tomorrow:
            summary["tomorrow"] += 1
        if today <= due <= week:
            summary["nextSevenDays"] += 1
        if priority == "urgent":
            summary["urgent"] += 1
        if status == "overdue":
            summary["overdue"] += 1
        if due <= week or priority == "urgent" or status == "overdue":
            case_id = getattr(scadenza, "id_fascicolo", "")
            fascicolo = fascicoli.get(case_id)
            rows.append(
                {
                    "id": scadenza.id,
                    "title": _clean_text(scadenza.titolo),
                    "dueDate": due.isoformat(),
                    "priority": priority,
                    "status": status,
                    "caseId": case_id or None,
                    "caseTitle": _case_title(fascicoli, case_id) or None,
                    "clientName": _client_name(
                        clienti,
                        getattr(fascicolo, "id_cliente", ""),
                        getattr(fascicolo, "nome_cliente", ""),
                    )
                    or None,
                    "href": _react_href(f"/scadenziario/{scadenza.id}/modifica"),
                }
            )
    rows = _dedupe_items(rows)
    rows.sort(key=lambda item: (_priority_weight(item["priority"]), item["dueDate"], item["title"]))
    return {"ok": True, "summary": summary, "deadlines": rows[:25]}


def notifications_payload(user: Any) -> dict[str, Any]:
    items = _dedupe_items(_persistent_notification_items(user))
    unread_count = sum(1 for item in items if not item["read"])
    return {"ok": True, "unreadCount": unread_count, "items": items[:30]}


def mark_notification_read(notification_id: str, user: Any) -> dict[str, Any]:
    safe_id = _clean_text(notification_id, limit=200)
    try:
        service = build_notification_service()
        service.mark_read(_notification_tenant_id(), _notification_user_id(user), safe_id)
        return notifications_payload(user)
    except NotificationServiceError as exc:
        raise TopbarApiError(str(exc), exc.status_code) from exc
    except Exception:
        current_app.logger.info("Top bar notifiche: repository persistente non disponibile", exc_info=True)
        known = {item["id"] for item in _notification_items(user)}
        if safe_id not in known:
            raise TopbarApiError("Notifica non trovata.", 404)
        read_ids = _read_notification_ids()
        read_ids.add(safe_id)
        _save_notification_ids(read_ids)
        return _session_notifications_payload(user)


def mark_all_notifications_read(user: Any) -> dict[str, Any]:
    try:
        service = build_notification_service()
        service.mark_all_read(_notification_tenant_id(), _notification_user_id(user))
        return notifications_payload(user)
    except Exception:
        current_app.logger.info("Top bar notifiche: lettura massiva su sessione per fallback", exc_info=True)
        ids = {item["id"] for item in _notification_items(user)}
        _save_notification_ids(_read_notification_ids() | ids)
        return _session_notifications_payload(user)


def _session_notifications_payload(user: Any) -> dict[str, Any]:
    read_ids = _read_notification_ids()
    items = _dedupe_items(_notification_items(user))
    for item in items:
        item["read"] = item["id"] in read_ids
    unread_count = sum(1 for item in items if not item["read"])
    return {"ok": True, "unreadCount": unread_count, "items": items[:30]}


def _persistent_notification_items(user: Any) -> list[dict[str, Any]]:
    generated = _notification_items(user)
    try:
        tenant_id = _notification_tenant_id()
        user_id = _notification_user_id(user)
        if not user_id:
            return _dedupe_items(generated)
        service = build_notification_service()
        records = service.sync_operational_items(tenant_id=tenant_id, user_id=user_id, items=generated)
        return _dedupe_items(_record_to_topbar_item(record) for record in records)
    except Exception:
        current_app.logger.info("Top bar notifiche: uso fallback in sessione", exc_info=True)
        read_ids = _read_notification_ids()
        for item in generated:
            item["read"] = item["id"] in read_ids
        return _dedupe_items(generated)


def _record_to_topbar_item(record: NotificationRecord) -> dict[str, Any]:
    payload = record.payload_json if isinstance(record.payload_json, dict) else {}
    message = _clean_text(record.body)
    return {
        "id": record.id,
        "type": record.type,
        "title": record.title or "Notifica operativa",
        "message": message,
        "body": message,
        "createdAt": payload.get("createdAt") or record.created_at,
        "priority": record.priority,
        "read": bool(record.read_at),
        "href": _react_href(record.href),
        "actionLabel": payload.get("actionLabel") or None,
    }


def _read_notification_ids() -> set[str]:
    values = session.get("topbar_read_notifications", [])
    if isinstance(values, list):
        return {str(value) for value in values if str(value).strip()}
    return set()


def _save_notification_ids(values: set[str]) -> None:
    session["topbar_read_notifications"] = sorted(values)[-200:]
    session.modified = True


def _portal_acquisition_href_for_release(fascicolo: Any, release: dict[str, Any]) -> str:
    source = _clean_text(release.get("fontePortale") or release.get("servizioPortale") or "PST").upper()
    if "PDP" in source:
        base = "/portali/pdp/acquisizione"
    elif "PAT" in source or "SIGA" in source:
        base = "/portali/pat/acquisizione"
    elif "PTT" in source or "SIGIT" in source:
        base = "/portali/ptt/acquisizione"
    else:
        base = "/portali/pst/acquisizione"
    params = [
        ("id_fasc", _clean_text(getattr(fascicolo, "id", ""))),
        ("fascicolo_id", _clean_text(getattr(fascicolo, "id", ""))),
        ("mode", "update_existing"),
        ("focus", "documenti"),
        ("numero", _clean_text(release.get("numeroRg") or getattr(fascicolo, "numero_rg", ""))),
        ("anno", _clean_text(release.get("annoRg") or getattr(fascicolo, "anno_rg", ""))),
        ("ufficio", _clean_text(release.get("ufficio") or getattr(fascicolo, "tribunale", ""))),
        ("id_deposito_pct", _clean_text(release.get("depositoId"))),
        ("id_deposito", _clean_text(release.get("idDepositoEsterno"))),
        ("id_documento", _clean_text(release.get("documentoId") or release.get("riferimentoPortale"))),
        ("documento_portale", _clean_text(release.get("nome"))),
        ("single_document", "1"),
        ("pec_id", _clean_text(release.get("pecId"))),
        ("hash", _clean_text(release.get("hashSha256"))),
        ("non_duplicare_documenti", "1"),
        ("fase_successiva", "relata_notifica"),
    ]
    query = "&".join(f"{quote(key)}={quote(value)}" for key, value in params if value)
    return f"{base}?{query}#acquisizione-portale" if query else f"{base}#acquisizione-portale"


def _notification_items(user: Any) -> list[dict[str, Any]]:
    now = datetime.now(ROME_TZ)
    today = now.date()
    items: list[dict[str, Any]] = []
    if _has_perm(user, "scadenziario.leggi"):
        try:
            for scadenza in get_scadenziario().tutte(solo_aperte=False):
                if is_legacy_pec_deadline(scadenza):
                    continue
                due = _deadline_date(scadenza)
                status = _deadline_status(scadenza, today)
                if due is None or status == "completed":
                    continue
                days = (due - today).days
                if days > 2 and _priority_from_deadline(scadenza, today) != "urgent":
                    continue
                priority = _priority_from_deadline(scadenza, today)
                items.append(
                    _notification(
                        f"deadline:{scadenza.id}:{due.isoformat()}",
                        "deadline",
                        _clean_text(scadenza.titolo),
                        "Scadenza oggi" if days == 0 else "Scadenza superata" if days < 0 else f"Scade tra {days} giorni",
                        due.isoformat(),
                        priority,
                        f"/scadenziario/{scadenza.id}/modifica",
                        "Apri scadenza",
                    )
                )
        except Exception:
            current_app.logger.info("Top bar notifiche: scadenze non disponibili", exc_info=True)
    if _has_perm(user, "agenda.leggi"):
        try:
            for appointment in get_agenda().tutti():
                if is_legacy_pec_agenda_item(appointment):
                    continue
                dt = getattr(appointment, "data_ora_dt", None) or _parse_iso(getattr(appointment, "data_ora", ""))
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ROME_TZ)
                if not dt or not (now <= dt <= now + timedelta(hours=48)):
                    continue
                kind = "hearing" if _enum_value(getattr(appointment, "tipo", "")) == TipoAppuntamento.UDIENZA.value else "task"
                items.append(
                    _notification(
                        f"{kind}:{appointment.id}:{dt.isoformat()}",
                        kind,
                        _clean_text(appointment.titolo),
                        dt.strftime("%d/%m/%Y alle %H:%M"),
                        dt.isoformat(),
                        "important" if kind == "hearing" else "normal",
                        f"/agenda/{appointment.id}/modifica",
                        "Apri agenda",
                    )
                )
        except Exception:
            current_app.logger.info("Top bar notifiche: agenda non disponibile", exc_info=True)
    if _has_perm(user, "messaggi.leggi"):
        try:
            for email in _email_manager().tutte(cartella=CartellaEmail.INBOX, solo_non_lette=True)[:10]:
                if _is_raw_pct_deposit_receipt_email(email):
                    continue
                timestamp = email.timestamp or email.ricevuta_il
                priority = "urgent" if getattr(email, "stato_pct", "") in {"ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA"} else "important" if getattr(email, "e_pst", False) else "normal"
                items.append(
                    _notification(
                        f"communication:{email.id}",
                        "communication",
                        _clean_text(email.oggetto) or "PEC non letta",
                        _clean_text(email.mittente_nome or email.mittente),
                        timestamp,
                        priority,
                        f"/email/{email.id}",
                        "Apri PEC",
                    )
                )
        except Exception:
            current_app.logger.info("Top bar notifiche: PEC non disponibile", exc_info=True)
    if _has_perm(user, "telematico.leggi"):
        try:
            office_emails = _email_manager().tutte()[:500]
            for fascicolo in get_fascicoli().tutti(archiviati=True):
                for release in released_office_documents_from_pec(fascicolo, office_emails)[:5]:
                    rg = "/".join(
                        part
                        for part in (
                            _clean_text(release.get("numeroRg") or getattr(fascicolo, "numero_rg", "")),
                            _clean_text(release.get("annoRg") or getattr(fascicolo, "anno_rg", "")),
                        )
                        if part
                    )
                    source = _clean_text(release.get("fontePortale") or "PEC cancelleria")
                    document_name = _clean_text(release.get("nome") or release.get("tipo") or "Documento d'ufficio")
                    detail = f"{document_name} comunicato da {source}"
                    if rg:
                        detail = f"{detail}, R.G. {rg}"
                    if release.get("notificaRichiesta"):
                        detail = f"{detail}. Scarica dal portale solo questo provvedimento prima della relata."
                    items.append(
                        _notification(
                            f"pec-office-release:{fascicolo.id}:{release.get('pecId') or release.get('riferimentoPortale')}:{release.get('documentoId') or document_name}",
                            "document",
                            "Provvedimento da notificare",
                            detail,
                            _clean_text(release.get("dataDeposito")) or now.isoformat(),
                            "urgent" if release.get("notificaRichiesta") else "important",
                            _clean_text(release.get("acquisitionHref")) or _portal_acquisition_href_for_release(fascicolo, release),
                            "Scarica dal portale",
                        )
                    )
                for deposito in list(getattr(fascicolo, "depositi_pct", []) or [])[-5:]:
                    stato = _enum_value(getattr(deposito, "stato", ""))
                    if not stato:
                        continue
                    title = f"Deposito telematico {getattr(fascicolo, 'numero', '')}".strip()
                    priority = "urgent" if any(token in stato for token in ("ERRORE", "RIFIUTATO", "FALLITO")) else "important"
                    if priority != "urgent" and not any(token in stato for token in ("ACCETTATO", "CONSEGNATO")):
                        continue
                    created = getattr(deposito, "timestamp", "") or getattr(deposito, "data_invio", "") or getattr(fascicolo, "modificato_il", "")
                    items.append(
                        _notification(
                            f"filing:{fascicolo.id}:{getattr(deposito, 'id', stato)}",
                            "filing",
                            title,
                            stato.replace("_", " ").title(),
                            created,
                            priority,
                            f"/fascicoli/{fascicolo.id}/deposito/prepara#ricevute-deposito",
                            "Apri deposito",
                        )
                    )
        except Exception:
            current_app.logger.info("Top bar notifiche: depositi non disponibili", exc_info=True)
    if _has_perm(user, "fascicoli.leggi"):
        try:
            cutoff = now - timedelta(hours=48)
            for fascicolo in get_fascicoli().tutti(archiviati=True):
                for documento in getattr(fascicolo, "documenti", []) or []:
                    loaded_at = _parse_iso(getattr(documento, "data_caricamento", ""))
                    if not loaded_at or loaded_at < cutoff:
                        continue
                    title = _clean_text(getattr(documento, "nome", "") or getattr(documento, "nome_originale", ""))
                    items.append(
                        _notification(
                            f"document:{fascicolo.id}:{getattr(documento, 'id', title)}",
                            "document",
                            title or "Documento aggiornato",
                            _clean_text(getattr(fascicolo, "titolo", "")),
                            loaded_at.isoformat(),
                            "normal",
                            f"/fascicoli/{fascicolo.id}",
                            "Apri fascicolo",
                        )
                    )
        except Exception:
            current_app.logger.info("Top bar notifiche: documenti non disponibili", exc_info=True)
    if _has_perm(user, "clienti.leggi"):
        try:
            for item in _invoice_notifications(today):
                items.append(item)
        except Exception:
            current_app.logger.info("Top bar notifiche: fatturazione non disponibile", exc_info=True)
    items = _dedupe_items(items)
    items.sort(key=lambda item: (_priority_weight(item["priority"]), item.get("createdAt") or ""), reverse=False)
    return items[:40]


def _invoice_notifications(today: date) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    fatturazione = get_fatturazione()
    for parcella in fatturazione.tutte():
        stato = _enum_value(getattr(parcella, "stato", ""))
        due = str(getattr(parcella, "data_scadenza", "") or "")[:10]
        if stato not in {StatoParcella.EMESSA.value, StatoParcella.SCADUTA.value}:
            continue
        if not due or due > today.isoformat():
            continue
        priority = "urgent" if stato == StatoParcella.SCADUTA.value or due < today.isoformat() else "important"
        items.append(
            _notification(
                f"invoice:{parcella.id}:{due}",
                "invoice",
                f"Fattura {getattr(parcella, 'numero', '')}".strip(),
                "Fattura scaduta o non pagata",
                due,
                priority,
                f"/fatturazione/{parcella.id}",
                "Apri fattura",
            )
        )
    return items


def _notification(
    item_id: str,
    item_type: str,
    title: str,
    message: str,
    created_at: str,
    priority: str,
    href: str | None,
    action_label: str | None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": item_type,
        "title": title or "Notifica operativa",
        "message": message,
        "body": message,
        "createdAt": created_at,
        "priority": priority if priority in {"normal", "important", "urgent"} else "normal",
        "read": False,
        "href": _react_href(href),
        "actionLabel": action_label,
    }
