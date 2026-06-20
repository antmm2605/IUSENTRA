"""Read-only payload for the React agenda migration page."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Iterable


RG_RE = re.compile(r"\b(?:R\.?\s*G\.?|RG|Ruolo generale)\s*(?:n\.?|numero|:)?\s*([0-9]{1,7}\s*/\s*[0-9]{4}(?:/[A-Z]+)?)", re.IGNORECASE)
COMMUNICATION_RG_RE = re.compile(r"\bCOMUNICAZIONE\s+([0-9]{1,7}\s*/\s*[0-9]{4})(?:\s*/\s*[A-Z]+)?\b", re.IGNORECASE)
BARE_RG_RE = re.compile(r"\b([0-9]{1,7}\s*/\s*[0-9]{4})(?:\s*/\s*[A-Z]+)?\b", re.IGNORECASE)
PARTY_RE = re.compile(r"\b(?:Ricorr\.?\s+principale|Resist\.?\s+principale|Attore|Convenuto|Ricorrente|Resistente)\s*:\s*([^\n\r;]+)", re.IGNORECASE)
DEADLINE_REF_RE = re.compile(r"\b(?:Scadenza|Termine)\s*:\s*([A-Za-z0-9_-]{6,80})", re.IGNORECASE)
OPERATIONAL_PREFIX_RE = re.compile(r"^\s*(?:Presidio\s+PEC|Presidio\s+anomalie\s+PEC|Verifica\s+comunicazione\s+di\s+cancelleria\s+PEC)\s*:?\s*-?\s*", re.IGNORECASE)
PEC_BODY_PREFIX_RE = re.compile(r"^\s*Data\s+processuale\s+futura\s+letta\s+da\s+corpo\s+PEC\s*:\s*", re.IGNORECASE)
PEC_HEARING_DATETIME_RE = re.compile(
    r"\b(?:al|alle|per\s+il|fissata\s+al|fissato\s+al)?\s*"
    r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s+"
    r"(?:ore\s*)?(\d{1,2})[:.](\d{2})\b",
    re.IGNORECASE,
)
TECHNICAL_VISIBLE_RE = re.compile(
    r"\b(?:PEC_AUDIT|pdf-deadline|pdf-semantic|pipeline|audit-grade|source_event|profile_id|payload|runtime|backend|frontend|legacy|json_api|external_uid|external_provider|worker|job|provider)\b",
    re.IGNORECASE,
)
NON_PARTY_RE = re.compile(r"\b(?:UDIENZA|COMUNICAZIONE|FISSATA|FISSATO|PRIMA|COMPAR|TRATT|ART\.?|DESCRIZIONE|OGGETTO)\b", re.IGNORECASE)


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


def _extract_labeled_segment(text: str, label: str, *, limit: int = 220) -> str:
    match = re.search(
        rf"\b{re.escape(label)}\s*:\s*(.*?)(?=\s+(?:Oggetto|Descrizione|Note|Scadenza|Tipo evento|Decorrenza letta|Fonte|Organizzatore|Sincronizzato da|Sorgente|UID esterno)\s*:|$)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return _clean_text(match.group(1), limit=limit).strip(" -:;")


def _pec_body_summary(text: Any, *, limit: int = 360) -> str:
    body = PEC_BODY_PREFIX_RE.sub("", _clean_text(text, limit=1200)).strip()
    if not body:
        return ""
    subject = _extract_labeled_segment(body, "Oggetto", limit=180)
    description = _extract_labeled_segment(body, "Descrizione", limit=220)
    note = _extract_labeled_segment(body, "Note", limit=160)
    parts: list[str] = []
    if subject:
        parts.append(f"Oggetto: {subject}")
    if description and description.casefold() != subject.casefold():
        parts.append(f"Descrizione: {description}")
    if note:
        note = re.sub(r"\bin\s+cance\S*", "in cancelleria", note, flags=re.IGNORECASE)
        parts.append(f"Nota: {note}")
    return _clean_text(" ".join(parts), limit=limit)


def _visible_legal_text(value: Any, *, limit: int = 360) -> str:
    parts: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = _clean_text(raw_line, limit=limit)
        if not line or TECHNICAL_VISIBLE_RE.search(line):
            continue
        pec_summary = _pec_body_summary(line, limit=limit)
        if pec_summary:
            parts.append(pec_summary)
            continue
        lower = line.lower()
        if lower.startswith("fonte link udienza:"):
            parts.append("Allegato udienza: " + _clean_text(line.split(":", 1)[1], limit=120))
            continue
        if lower.startswith("verifica link udienza:"):
            value_part = _clean_text(line.split(":", 1)[1], limit=160).lower()
            if "identico" in value_part:
                parts.append("Link udienza verificato sull'allegato.")
            elif value_part:
                parts.append("Link udienza da controllare sull'allegato.")
            continue
        if line.lower().startswith(("tipo evento:", "decorrenza letta:", "fonte:", "scadenza:")):
            continue
        parts.append(line)
    return _clean_text(" ".join(parts), limit=limit)


def _extract_rg(*values: Any) -> str:
    for value in values:
        text = str(value or "")
        for pattern in (RG_RE, COMMUNICATION_RG_RE):
            match = pattern.search(text)
            if match:
                return "RG " + re.sub(r"\s+", "", match.group(1).upper())
        if re.search(r"\b(?:comunicazione|udienza|ruolo|fascicolo)\b", text, re.IGNORECASE):
            match = BARE_RG_RE.search(text)
            if match:
                return "RG " + re.sub(r"\s+", "", match.group(1).upper())
    return ""


def _extract_party(*values: Any) -> str:
    for value in values:
        text = str(value or "")
        match = PARTY_RE.search(text)
        if match:
            return _clean_text(match.group(1), limit=90)
        body = PEC_BODY_PREFIX_RE.sub("", _clean_text(text, limit=500)).strip()
        body_match = re.match(r"(.{2,100}?)(?=\s+(?:Oggetto|Descrizione|Note)\s*:)", body, re.IGNORECASE)
        if body_match:
            candidate = _clean_text(body_match.group(1), limit=90).strip(" -:;")
            if candidate and not NON_PARTY_RE.search(candidate):
                return candidate
    return ""


def _is_pec_operational_text(*values: Any) -> bool:
    text = " ".join(str(value or "") for value in values).lower()
    return any(token in text for token in ("posta certificata", "pec_audit", "comunicazione_cancelleria", "presidio pec", "da pec"))


def _is_document_presidio_lex_text(*values: Any) -> bool:
    text = " ".join(str(value or "") for value in values).lower()
    return "docpresidio:" in text or "documento_fascicolo_lex" in text or "presidio documentale lex" in text


def _docpresidio_kind(*values: Any) -> str:
    text = " ".join(str(value or "") for value in values).lower()
    if "deposito note" in text:
        return "deposito_note"
    if "docpresidio:" in text and ":termine:" in text:
        return "termine"
    if "docpresidio:" in text and ":udienza:" in text:
        return "udienza"
    return ""


def _extract_docpresidio_labeled(text: str, label: str, *, limit: int = 220) -> str:
    match = re.search(
        rf"\b{re.escape(label)}\s*:\s*(.*?)(?=\s+(?:Ufficio|Giudice|RG|Cliente|Parte/soggetto|Evento|Collegamento remoto|Attività per l'avvocato|Data letta|Fonte documentale|Contesto letto|Udienza da remoto|Orario collegamento|Link udienza audiovisiva|Allegato udienza|Link udienza|Fascicolo|Scadenza|Tipo evento|Decorrenza letta|Fonte|Sincronizzato da|Sorgente|UID esterno)\s*:|$)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return _clean_text(match.group(1), limit=limit).strip(" -:;.")


def _extract_labeled_line(text: str, label: str, *, limit: int = 220) -> str:
    prefix = f"{label}:".lower()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if line.lower().startswith(prefix):
            return _clean_text(line.split(":", 1)[1], limit=limit).strip(" -:;.")
    return _extract_docpresidio_labeled(text, label, limit=limit)


def _append_detail_line(lines: list[str], line: str, *, limit: int = 220) -> None:
    cleaned = _clean_text(line, limit=limit)
    if cleaned and cleaned.lower() not in " ".join(lines).lower():
        lines.append(cleaned)


def _agenda_origin_title(raw_title: str, legal_label: str, matter: str, notes: str) -> str:
    stripped = _strip_operational_prefix(raw_title)
    if _is_document_presidio_lex_text(raw_title, notes):
        return _clean_text(stripped or legal_label, limit=180)
    if not _is_pec_operational_text(raw_title, notes):
        return _clean_text(stripped or legal_label, limit=180)
    text = f"{raw_title} {notes}".lower()
    if "udienza" in text:
        base = "Udienza da comunicazione di cancelleria"
    elif "notifica" in text or "notificazione" in text:
        base = "Notifica giudiziaria da PEC"
    elif "deposito" in text:
        base = "Comunicazione sul deposito telematico"
    else:
        base = "Comunicazione di cancelleria"
    return f"{base} - {matter}" if matter else base


def _extract_hearing_datetime(*values: Any) -> datetime | None:
    for value in values:
        text = str(value or "")
        for match in PEC_HEARING_DATETIME_RE.finditer(text):
            day, month, year, hour, minute = (int(part) for part in match.groups())
            try:
                return datetime(year, month, day, hour, minute)
            except ValueError:
                continue
    return None


def _legal_label(title: str, kind: str, notes: str = "") -> str:
    text = f"{title} {kind} {notes}".lower()
    if _is_document_presidio_lex_text(title, notes):
        doc_kind = _docpresidio_kind(title, notes)
        if doc_kind in {"deposito_note", "termine"}:
            return "Deposito note scritte"
        if doc_kind == "udienza":
            return "Udienza"
    if "rinvio" in text or "rinviata" in text or "differimento" in text or "differita" in text:
        return "Rinvio udienza"
    if "fissazione udienza" in text or "fissata udienza" in text or "fissata l'udienza" in text or ("fissazione" in text and "udienza" in text):
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


def _strip_operational_prefix(value: str) -> str:
    cleaned = str(value or "").strip(" -:")
    while True:
        next_value = OPERATIONAL_PREFIX_RE.sub("", cleaned).strip(" -:")
        if next_value == cleaned:
            return cleaned
        cleaned = next_value


def _operational_title(title: str, legal_label: str, client: str, matter: str, notes: str) -> str:
    if client and matter:
        return f"{client} · {matter}"
    if client:
        return client
    if matter:
        return matter
    stripped = _strip_operational_prefix(title)
    if stripped and not stripped.lower().startswith("presidio"):
        return _clean_text(stripped, limit=90)
    party = _extract_party(notes)
    if party:
        return party
    return legal_label


def _detail_lines(row: dict[str, Any], *, original_title: str, legal_label: str) -> list[str]:
    lines: list[str] = []
    raw_notes = str(row.get("technicalNotes") or row.get("notes") or "")
    for label, key in (
        ("Cliente/parte", "client"),
        ("Fascicolo/RG", "matter"),
        ("Ufficio", "court"),
        ("Luogo", "location"),
        ("Responsabile", "owner"),
    ):
        value = _visible_legal_text(row.get(key), limit=140)
        if value:
            lines.append(f"{label}: {value}")
    if _is_document_presidio_lex_text(original_title, raw_notes):
        party_subject = _extract_docpresidio_labeled(raw_notes, "Parte/soggetto", limit=180)
        if party_subject and party_subject.lower() not in " ".join(lines).lower():
            lines.append(f"Parte/soggetto: {party_subject}")
        remote_link = (
            _extract_labeled_line(raw_notes, "Link udienza audiovisiva", limit=240)
            or _extract_labeled_line(raw_notes, "Collegamento remoto", limit=240)
        )
        if remote_link:
            _append_detail_line(lines, f"Link udienza audiovisiva: {remote_link}", limit=280)
        remote_source = (
            _extract_labeled_line(raw_notes, "Fonte link udienza", limit=160)
            or _extract_labeled_line(raw_notes, "Allegato udienza", limit=160)
        )
        remote_check = _extract_labeled_line(raw_notes, "Verifica link udienza", limit=180)
        if remote_source:
            remote_source_line = f"Allegato udienza: {remote_source}"
            if remote_check and "identico" in remote_check.lower():
                remote_source_line += " - link verificato sull'allegato"
            elif remote_check or remote_link:
                remote_source_line += " - link da controllare sull'allegato"
            _append_detail_line(lines, remote_source_line, limit=260)
        if remote_check:
            if "identico" in remote_check.lower():
                _append_detail_line(lines, "Link udienza verificato sull'allegato.")
            else:
                _append_detail_line(lines, "Link udienza da controllare sull'allegato.")
    status = _clean_text(row.get("status"), limit=80)
    if status:
        lines.append(f"Stato: {status}")
    visible_original = _strip_operational_prefix(original_title)
    if visible_original and visible_original != row.get("displayTitle"):
        lines.append(f"Oggetto: {_clean_text(visible_original, limit=180)}")
    notes = _visible_legal_text(row.get("notes"), limit=220)
    if notes:
        lines.append(f"Dettaglio: {notes}")
    if not lines:
        lines.append(f"Attività: {legal_label}")
    return lines[:12]


def _decorate_event(row: dict[str, Any]) -> dict[str, Any]:
    raw_notes = str(row.get("notes") or "").strip()[:4000]
    raw_title = str(row.get("title") or "Appuntamento").strip()
    original_title = _visible_legal_text(raw_title, limit=180) or "Appuntamento"
    notes = _visible_legal_text(raw_notes, limit=700)
    kind = _clean_text(row.get("kind"), limit=80)
    matter = _clean_text(row.get("matter"), limit=120) or _extract_rg(raw_title, raw_notes, original_title, notes)
    client = _clean_text(row.get("client"), limit=120) or _extract_party(raw_notes, notes, raw_title, original_title)
    label = _legal_label(raw_title, kind, raw_notes or notes)
    origin_title = _agenda_origin_title(raw_title, label, matter, raw_notes or notes)
    row["technicalNotes"] = raw_notes
    row["originTitle"] = origin_title
    row["legalLabel"] = label
    row["client"] = client
    row["matter"] = matter
    row["displayTitle"] = _operational_title(origin_title, label, client, matter, notes)
    row["notes"] = notes
    subtitle = _visible_legal_text(row.get("subtitle"), limit=160)
    if not subtitle:
        subtitle = " · ".join(part for part in (matter, _clean_text(row.get("court"), limit=80), _clean_text(row.get("location"), limit=80)) if part)
    row["subtitle"] = subtitle
    row["detailTitle"] = label
    row["detailLines"] = _detail_lines(row, original_title=origin_title, legal_label=label)
    return row


def _linked_deadline_refs(row: dict[str, Any]) -> set[str]:
    text = "\n".join(str(row.get(key) or "") for key in ("technicalNotes", "notes", "title", "originTitle"))
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
    notes = "\n".join(
        part
        for part in (
            str(getattr(item, "descrizione", "") or "").strip(),
            str(getattr(item, "note", "") or "").strip(),
        )
        if part
    )
    title = str(getattr(item, "titolo", "") or "Appuntamento")
    hearing_dt = _extract_hearing_datetime(title, notes) if _is_pec_operational_text(title, notes) else None
    if hearing_dt and start.hour == 9 and start.minute == 0 and hearing_dt.date() == start.date():
        start = hearing_dt
    duration = max(15, int(getattr(item, "durata_minuti", 60) or 60))
    end = start + timedelta(minutes=duration)
    item_id = str(getattr(item, "id", "") or "")
    tipo = _enum_value(getattr(item, "tipo", ""))
    return _decorate_event({
        "id": item_id,
        "title": title,
        "kind": tipo,
        "priority": "MEDIA",
        "status": _enum_value(getattr(item, "stato", "PROGRAMMATO")),
        "start": start.isoformat(timespec="minutes"),
        "end": end.isoformat(timespec="minutes"),
        "timeLabel": start.strftime("%H:%M"),
        "durationLabel": f"{duration} min",
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
    time_label = "09:00" if kind == "UDIENZA" else "Entro giornata"
    duration_label = "45 min" if kind == "UDIENZA" else "Scadenza"
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
        "timeLabel": time_label,
        "durationLabel": duration_label,
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
