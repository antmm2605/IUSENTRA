"""Read-only payload for the React agenda migration page."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Iterable


RG_RE = re.compile(r"\b(?:R\.?\s*G\.?|RG|Ruolo generale)\s*(?:n\.?|numero|:)?\s*([0-9]{1,7}\s*/\s*[0-9]{4}(?:/[A-Z]+)?)", re.IGNORECASE)
PARTY_RE = re.compile(r"\b(?:Ricorr\.?\s+principale|Resist\.?\s+principale|Attore|Convenuto|Ricorrente|Resistente)\s*:\s*([^\n\r;]+)", re.IGNORECASE)
DEADLINE_REF_RE = re.compile(r"\b(?:Scadenza|Termine)\s*:\s*([A-Za-z0-9_-]{6,80})", re.IGNORECASE)
OPERATIONAL_PREFIX_RE = re.compile(r"^\s*(?:Presidio\s+PEC|Presidio\s+anomalie\s+PEC|Verifica\s+comunicazione\s+di\s+cancelleria\s+PEC)\s*:?\s*-?\s*", re.IGNORECASE)


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


def _clean_text(value: Any, *, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _extract_rg(*values: Any) -> str:
    for value in values:
        match = RG_RE.search(str(value or ""))
        if match:
            return "RG " + re.sub(r"\s+", "", match.group(1).upper())
    return ""


def _extract_party(*values: Any) -> str:
    for value in values:
        match = PARTY_RE.search(str(value or ""))
        if match:
            return _clean_text(match.group(1), limit=90)
    return ""


def _legal_label(title: str, kind: str, notes: str = "") -> str:
    text = f"{title} {kind} {notes}".lower()
    if "rinvio" in text or "rinviata" in text or "differimento" in text or "differita" in text:
        return "Rinvio udienza"
    if "fissazione udienza" in text or "fissata udienza" in text or "fissata l'udienza" in text:
        return "Fissazione udienza"
    if "udienza" in text:
        return "Udienza"
    if "deposito" in text and any(token in text for token in ("accett", "consegn", "esito positivo")):
        return "Deposito accettato"
    if "deposito" in text:
        return "Deposito"
    if "notifica" in text or "notificazione" in text:
        return "Notifica"
    if "termine" in text or "scadenza" in text or "decorrenza" in text:
        return "Termine giuridico"
    if "pec" in text or "cancelleria" in text:
        return "Comunicazione PEC"
    return "Adempimento"


def _operational_title(title: str, legal_label: str, client: str, matter: str, notes: str) -> str:
    if client and matter:
        return f"{client} · {matter}"
    if client:
        return client
    if matter:
        return matter
    stripped = OPERATIONAL_PREFIX_RE.sub("", title or "").strip(" -:")
    if stripped and not stripped.lower().startswith("presidio"):
        return _clean_text(stripped, limit=90)
    party = _extract_party(notes)
    if party:
        return party
    return legal_label


def _detail_lines(row: dict[str, Any], *, original_title: str, legal_label: str) -> list[str]:
    lines: list[str] = []
    for label, key in (
        ("Cliente/parte", "client"),
        ("Fascicolo/RG", "matter"),
        ("Ufficio", "court"),
        ("Luogo", "location"),
        ("Responsabile", "owner"),
        ("Fonte", "source"),
    ):
        value = _clean_text(row.get(key), limit=140)
        if value:
            lines.append(f"{label}: {value}")
    status = _clean_text(row.get("status"), limit=80)
    if status:
        lines.append(f"Stato: {status}")
    if original_title and original_title != row.get("displayTitle"):
        lines.append(f"Oggetto originale: {_clean_text(original_title, limit=180)}")
    notes = _clean_text(row.get("notes"), limit=220)
    if notes:
        lines.append(f"Dettaglio: {notes}")
    if not lines:
        lines.append(f"Tipo evento: {legal_label}")
    return lines[:8]


def _decorate_event(row: dict[str, Any]) -> dict[str, Any]:
    original_title = _clean_text(row.get("title") or "Appuntamento", limit=180)
    notes = _clean_text(row.get("notes"), limit=700)
    kind = _clean_text(row.get("kind"), limit=80)
    matter = _clean_text(row.get("matter"), limit=120) or _extract_rg(original_title, notes)
    client = _clean_text(row.get("client"), limit=120) or _extract_party(notes, original_title)
    label = _legal_label(original_title, kind, notes)
    row["originTitle"] = original_title
    row["legalLabel"] = label
    row["client"] = client
    row["matter"] = matter
    row["displayTitle"] = _operational_title(original_title, label, client, matter, notes)
    subtitle = _clean_text(row.get("subtitle"), limit=160)
    if not subtitle:
        subtitle = " · ".join(part for part in (matter, _clean_text(row.get("court"), limit=80), _clean_text(row.get("location"), limit=80)) if part)
    row["subtitle"] = subtitle
    row["detailTitle"] = label
    row["detailLines"] = _detail_lines(row, original_title=original_title, legal_label=label)
    return row


def _linked_deadline_refs(row: dict[str, Any]) -> set[str]:
    text = "\n".join(str(row.get(key) or "") for key in ("notes", "title", "originTitle"))
    return {match.group(1) for match in DEADLINE_REF_RE.finditer(text)}


def _event_dedupe_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    def normal(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()

    return (
        str(row.get("start") or "")[:16],
        normal(row.get("legalLabel") or row.get("kind")),
        normal(row.get("displayTitle") or row.get("title")),
        normal(row.get("matter")),
        normal(row.get("client")),
    )


def _dedupe_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(events)
    linked_deadlines: set[str] = set()
    for row in rows:
        if str(row.get("source") or "") == "agenda":
            linked_deadlines.update(_linked_deadline_refs(row))

    deduped: list[dict[str, Any]] = []
    positions: dict[tuple[str, str, str, str, str], int] = {}
    for row in rows:
        row_id = str(row.get("id") or "")
        if str(row.get("source") or "") == "scadenziario" and row_id.startswith("scadenza-") and row_id.removeprefix("scadenza-") in linked_deadlines:
            continue
        key = _event_dedupe_key(row)
        existing_index = positions.get(key)
        if existing_index is None:
            positions[key] = len(deduped)
            deduped.append(row)
            continue
        existing = deduped[existing_index]
        if str(existing.get("source") or "") != "agenda" and str(row.get("source") or "") == "agenda":
            deduped[existing_index] = row
    return deduped


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
    notes = "\n".join(
        part
        for part in (
            str(getattr(item, "descrizione", "") or "").strip(),
            str(getattr(item, "note", "") or "").strip(),
        )
        if part
    )
    return _decorate_event({
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
        "matterId": str(getattr(item, "id_fascicolo", "") or ""),
        "client": str(getattr(item, "cliente", "") or ""),
        "clientId": str(getattr(item, "id_cliente", "") or ""),
        "owner": str(getattr(item, "avvocato", "") or "Studio"),
        "source": "agenda",
        "syncStatus": _sync_status(item),
        "notes": notes,
        "href": f"/agenda/{item_id}" if item_id else "/agenda",
    })


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
    if tipo == "UDIENZA":
        kind = "UDIENZA"
    elif "DEPOSITO" in tipo:
        kind = "DEPOSITO"
    else:
        kind = "SCADENZA"
    notes = "\n".join(
        part
        for part in (
            str(getattr(item, "descrizione", "") or "").strip(),
            str(getattr(item, "note", "") or "").strip(),
        )
        if part
    )
    return _decorate_event({
        "id": f"scadenza-{item_id}" if item_id else f"scadenza-{due_date.isoformat()}",
        "title": str(getattr(item, "titolo", "") or "Scadenza"),
        "kind": kind,
        "priority": _enum_value(getattr(item, "priorita", "MEDIA")),
        "status": _enum_value(getattr(item, "stato", "APERTO")),
        "start": start.isoformat(timespec="minutes"),
        "end": end.isoformat(timespec="minutes"),
        "location": "",
        "court": "",
        "matter": str(getattr(item, "id_fascicolo", "") or ""),
        "matterId": str(getattr(item, "id_fascicolo", "") or ""),
        "client": "",
        "clientId": str(getattr(item, "id_cliente", "") or ""),
        "owner": str(getattr(item, "id_utente_responsabile", "") or "Studio"),
        "source": "scadenziario",
        "syncStatus": "locale",
        "notes": notes,
        "href": f"/scadenziario/{item_id}" if item_id else "/scadenziario",
    })


def build_react_agenda_payload(
    agenda_loader: Callable[[], Any],
    deadlines_loader: Callable[[], Any],
    from_value: Any = "",
    to_value: Any = "",
    selected_id: str = "",
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
    if selected_id:
        try:
            selected = agenda_repo.get(selected_id)
        except Exception:
            selected = None
        if selected is not None:
            event = _agenda_event(selected)
            if event and not any(str(row.get("id") or "") == str(event.get("id") or "") for row in events):
                events.append(event)
    for item in deadlines:
        event = _deadline_event(item)
        if event:
            event_date = _parse_date(event["start"], start)
            if start <= event_date <= end:
                events.append(event)

    events = _dedupe_events(events)
    events.sort(key=lambda row: str(row.get("start") or ""))
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "events": events,
        "selected_id": selected_id,
        "contracts": {
            "mock_fallback": False,
            "read_only": True,
            "sources": ["agenda", "scadenziario"],
        },
    }
