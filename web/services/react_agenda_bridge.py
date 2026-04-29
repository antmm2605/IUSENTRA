"""Read-only payload for the React agenda migration page."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Iterable


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _parse_date(value: Any, fallback: date) -> date:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return fallback


def _date_range(from_value: Any, to_value: Any) -> tuple[date, date]:
    today = date.today()
    start = _parse_date(from_value, today - timedelta(days=7))
    end = _parse_date(to_value, today + timedelta(days=30))
    if end < start:
        start, end = end, start
    return start, end


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_items(loader: Callable[[], Iterable[Any]]) -> list[Any]:
    try:
        return list(loader())
    except Exception:
        return []


def _sync_status(item: Any) -> str:
    provider = str(getattr(item, "external_provider", "") or "").strip()
    last_sync = str(getattr(item, "external_last_sync", "") or "").strip()
    if provider and last_sync:
        return "sincronizzato"
    if provider:
        return "da_sincronizzare"
    return "locale"


def _agenda_event(item: Any) -> dict[str, Any] | None:
    start = getattr(item, "data_ora_dt", None)
    if not isinstance(start, datetime):
        try:
            start = datetime.fromisoformat(str(getattr(item, "data_ora", "") or ""))
        except ValueError:
            return None
    duration = max(15, int(getattr(item, "durata_minuti", 60) or 60))
    end = start + timedelta(minutes=duration)
    item_id = str(getattr(item, "id", "") or "")
    tipo = _enum_value(getattr(item, "tipo", ""))
    return {
        "id": item_id,
        "title": str(getattr(item, "titolo", "") or "Appuntamento"),
        "kind": tipo,
        "priority": "MEDIA",
        "status": _enum_value(getattr(item, "stato", "PROGRAMMATO")),
        "start": start.isoformat(timespec="minutes"),
        "end": end.isoformat(timespec="minutes"),
        "location": str(getattr(item, "luogo", "") or ""),
        "court": str(getattr(item, "tribunale", "") or ""),
        "matter": str(getattr(item, "procedimento", "") or ""),
        "client": str(getattr(item, "cliente", "") or ""),
        "owner": str(getattr(item, "avvocato", "") or "Studio"),
        "source": "agenda",
        "syncStatus": _sync_status(item),
        "notes": str(getattr(item, "note", "") or ""),
        "href": f"/agenda/{item_id}" if item_id else "/agenda",
    }


def _appointment_in_range(item: Any, start: date, end: date) -> bool:
    parsed = getattr(item, "data_ora_dt", None)
    if not isinstance(parsed, datetime):
        try:
            parsed = datetime.fromisoformat(str(getattr(item, "data_ora", "") or ""))
        except ValueError:
            return False
    return start <= parsed.date() <= end


def _deadline_event(item: Any) -> dict[str, Any] | None:
    due = str(getattr(item, "data_scadenza", "") or getattr(item, "legal_due_at", "") or "").strip()
    if not due:
        return None
    try:
        due_date = date.fromisoformat(due[:10])
    except ValueError:
        return None
    start = datetime.combine(due_date, time(hour=9))
    end = start + timedelta(minutes=45)
    item_id = str(getattr(item, "id", "") or "")
    tipo = _enum_value(getattr(item, "tipo", ""))
    return {
        "id": f"scadenza-{item_id}" if item_id else f"scadenza-{due_date.isoformat()}",
        "title": str(getattr(item, "titolo", "") or "Scadenza"),
        "kind": "DEPOSITO" if "DEPOSITO" in tipo else "SCADENZA",
        "priority": _enum_value(getattr(item, "priorita", "MEDIA")),
        "status": _enum_value(getattr(item, "stato", "APERTO")),
        "start": start.isoformat(timespec="minutes"),
        "end": end.isoformat(timespec="minutes"),
        "location": "",
        "court": "",
        "matter": str(getattr(item, "id_fascicolo", "") or ""),
        "client": "",
        "owner": str(getattr(item, "id_utente_responsabile", "") or "Studio"),
        "source": "scadenziario",
        "syncStatus": "locale",
        "notes": str(getattr(item, "descrizione", "") or getattr(item, "note", "") or ""),
        "href": "/scadenziario",
    }


def build_react_agenda_payload(
    agenda_loader: Callable[[], Any],
    deadlines_loader: Callable[[], Any],
    from_value: Any = "",
    to_value: Any = "",
) -> dict[str, Any]:
    """Return agenda and deadline rows normalized for the React shell."""

    start, end = _date_range(from_value, to_value)
    agenda_repo = agenda_loader()
    deadlines_repo = deadlines_loader()
    appointments = [
        item
        for item in _safe_items(lambda: agenda_repo.tutti())
        if _appointment_in_range(item, start, end)
    ]
    deadlines = _safe_items(lambda: deadlines_repo.tutte(solo_aperte=True))

    events: list[dict[str, Any]] = []
    for item in appointments:
        event = _agenda_event(item)
        if event:
            events.append(event)
    for item in deadlines:
        event = _deadline_event(item)
        if event:
            event_date = _parse_date(event["start"], start)
            if start <= event_date <= end:
                events.append(event)

    events.sort(key=lambda row: str(row.get("start") or ""))
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "events": events,
        "contracts": {
            "mock_fallback": False,
            "read_only": True,
            "sources": ["agenda", "scadenziario"],
        },
    }
