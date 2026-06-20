"""Bridge dati per la pagina React Scadenziario.

La funzione espone alla shell React una vista normalizzata delle scadenze usando
solo repository e servizi operativi esistenti. Le scritture restano sulle route
Flask gia' auditate: crea, modifica, completa, elimina, bulk, export e iCal.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pct.scadenziario import (
    OFFICE_MODE_LABELS,
    PRESET_TERMINI,
    PrioritaTermine,
    SOURCE_EVENT_TYPE_LABELS,
    StatoTermine,
    TipoTermine,
    profili_termine_builtin,
)
from pct.termini_processuali import (
    CALENDAR_VERSION,
    DeadlinePracticeRepository,
    ENGINE_VERSION,
    LEGAL_SOURCES,
    RULESET_VERSION,
    DEFAULT_TEMPLATES,
)
from web.services.scadenziario_views import (
    VISTA_LABEL_SCADENZIARIO,
    is_scadenza_pec,
    normalizza_vista_scadenziario,
    scadenze_per_vista,
)

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
TECHNICAL_VISIBLE_RE = re.compile(
    r"\b(?:PEC_AUDIT|pdf-deadline|pdf-semantic|pipeline|audit|audit-grade|source_event|profile_id|payload|runtime|backend|frontend|legacy|json_api|external_uid|external_provider|worker|job|provider|webhook|endpoint)\b",
    re.IGNORECASE,
)
INTERNAL_NOTE_PREFIXES = (
    "tipo evento:",
    "decorrenza letta:",
    "fonte:",
    "scadenza:",
    "hash:",
    "id:",
)
OPERATIONAL_PREFIX_RE = re.compile(
    r"^\s*(?:Presidio\s+PEC|Presidio\s+anomalie\s+PEC|Verifica\s+comunicazione\s+di\s+cancelleria\s+PEC)\s*:?\s*-?\s*",
    re.IGNORECASE,
)
PEC_SUBJECT_NOISE_RE = re.compile(
    r"\b(?:POSTA\s+CERTIFICATA|COMUNICAZIONE\s+[A-Z0-9./_-]+|Notificazione\s+ai\s+sensi\s+del\s+D\.L\.\s*179/2012)\b:?",
    re.IGNORECASE,
)
PEC_RG_RE = re.compile(r"\b(?:N\.?\s*R\.?\s*G\.?|NRG|RG)\s*:?\s*(\d{1,8}/\d{4}(?:/[A-Z]+)?)\b", re.IGNORECASE)
PEC_NUMBER_RE = re.compile(r"\b(\d{1,8}/20\d{2})(?:/[A-Z]+)?\b", re.IGNORECASE)


def _normalise_for_matching(value: Any) -> str:
    text = str(value or "").lower()
    return text.replace("à", "a").replace("è", "e").replace("é", "e").replace("ì", "i").replace("ò", "o").replace("ù", "u")


def _pec_context(scadenza: Any) -> str:
    return " ".join(
        str(value or "")
        for value in (
            getattr(scadenza, "titolo", ""),
            getattr(scadenza, "descrizione", ""),
            getattr(scadenza, "note", ""),
            getattr(scadenza, "id_fascicolo", ""),
            getattr(scadenza, "source_event_type", ""),
        )
    )


def _is_document_presidio_lex(scadenza: Any) -> bool:
    context = _normalise_for_matching(_pec_context(scadenza))
    return "documento_fascicolo_lex" in context or "docpresidio:" in context


def _pec_rg_label(context: str) -> str:
    match = PEC_RG_RE.search(context) or PEC_NUMBER_RE.search(context)
    if not match:
        return ""
    number = match.group(1).upper()
    if "/" in number:
        pieces = number.split("/")
        if len(pieces) >= 2:
            number = "/".join(pieces[:2])
    return f"RG {number}"


def _pec_event_summary(context: str) -> str:
    norm = _normalise_for_matching(context)
    if "rinvio" in norm:
        return "rinvio udienza"
    if "differimento" in norm:
        return "differimento udienza"
    if "conferma" in norm:
        return "conferma udienza"
    if "fissazione" in norm or "avviso di udienza" in norm or "avviso udienza" in norm:
        return "fissazione udienza"
    if "discussione" in norm:
        return "udienza di discussione"
    if "udienza" in norm:
        return "udienza"
    if "notifica" in norm or "notificazione" in norm:
        return "notifica giudiziaria"
    if "cancelleria" in norm or "comunicazione" in norm:
        return "comunicazione di cancelleria"
    return ""


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _short_text(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _visible_legal_text(value: Any, limit: int = 160) -> str:
    parts: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = _short_text(raw_line, limit=max(limit, 220))
        if not line:
            continue
        line = re.sub(r"\bPEC_AUDIT:[A-Za-z0-9_-]+", "", line).strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("fonte link udienza:"):
            parts.append("Allegato udienza: " + _short_text(line.split(":", 1)[1], 120))
            continue
        if lowered.startswith("verifica link udienza:"):
            value_part = _short_text(line.split(":", 1)[1], 160).lower()
            if "identico" in value_part:
                parts.append("Link udienza verificato sull'allegato.")
            elif value_part:
                parts.append("Link udienza da controllare sull'allegato.")
            continue
        if lowered.startswith(INTERNAL_NOTE_PREFIXES):
            continue
        if TECHNICAL_VISIBLE_RE.search(line):
            continue
        line = PEC_SUBJECT_NOISE_RE.sub("", line).strip(" -:")
        line = OPERATIONAL_PREFIX_RE.sub("", line).strip(" -:")
        if line:
            parts.append(line)
    return _short_text(" ".join(parts), limit)


def _legal_scadenza_title(scadenza: Any) -> str:
    if _is_document_presidio_lex(scadenza):
        title = _visible_legal_text(getattr(scadenza, "titolo", ""), 112)
        if title:
            return title
    if is_scadenza_pec(scadenza):
        context = _pec_context(scadenza)
        summary = _pec_event_summary(context)
        rg = _pec_rg_label(context)
        if "udienza" in summary:
            details = [summary]
            if rg:
                details.append(rg)
            return _short_text(f"Udienza da PEC: {' - '.join(details)}", 96)
        if summary == "notifica giudiziaria":
            return _short_text(" - ".join(part for part in ("Notifica giudiziaria da PEC", rg) if part), 96)
        if summary == "comunicazione di cancelleria":
            return _short_text(" - ".join(part for part in ("Comunicazione di cancelleria da PEC", rg) if part), 96)
    title = _visible_legal_text(getattr(scadenza, "titolo", ""), 96)
    if title:
        return title
    tipo = _type_label(getattr(scadenza, "tipo", TipoTermine.ALTRO.value))
    fascicolo = str(getattr(scadenza, "id_fascicolo", "") or "").strip()
    return _short_text(f"{tipo} {fascicolo}".strip() or "Scadenza", 96)


def _legal_scadenza_description(scadenza: Any) -> str:
    if _is_document_presidio_lex(scadenza):
        description = _visible_legal_text(getattr(scadenza, "descrizione", ""), 220)
        if description:
            return description
        note = _visible_legal_text(getattr(scadenza, "note", ""), 220)
        if note:
            return note
    if is_scadenza_pec(scadenza):
        context = _pec_context(scadenza)
        summary = _pec_event_summary(context)
        rg = _pec_rg_label(context)
        if "udienza" in summary:
            parts = ["Udienza rilevata da PEC."]
            if rg:
                parts.append(f"Fascicolo {rg}.")
            if bool(getattr(scadenza, "remote_hearing_detected", False)):
                parts.append("Collegamento audiovisivo da verificare sull'allegato prima dell'udienza.")
            else:
                parts.append("Verificare provvedimento, fascicolo e attività collegate.")
            return _short_text(" ".join(parts), 150)
        if summary == "notifica giudiziaria":
            return _short_text("Notifica giudiziaria rilevata da PEC: controllare atto, fascicolo e termini applicabili.", 150)
        if summary == "comunicazione di cancelleria":
            return _short_text("Comunicazione di cancelleria da PEC: verificare provvedimento e attività conseguenti.", 150)
    description = _visible_legal_text(getattr(scadenza, "descrizione", ""), 150)
    if description:
        return description
    return _visible_legal_text(getattr(scadenza, "note", ""), 150)


def _legal_scadenza_detail_description(scadenza: Any) -> str:
    if _is_document_presidio_lex(scadenza):
        description = _visible_legal_text(getattr(scadenza, "descrizione", ""), 900)
        if description:
            return description
    description = _visible_legal_text(getattr(scadenza, "descrizione", ""), 520)
    if description:
        return description
    return _visible_legal_text(getattr(scadenza, "note", ""), 520)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw[:10], raw.replace("Z", "+00:00")[:10]):
        try:
            return date.fromisoformat(sample)
        except ValueError:
            continue
    return None


def _format_date(value: Any) -> str:
    parsed = _parse_date(value)
    if not parsed:
        return "-"
    today = date.today()
    if parsed == today:
        return "oggi"
    if parsed == today + _one_day():
        return "domani"
    if parsed == today - _one_day():
        return "ieri"
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]}"
    return parsed.strftime("%d/%m/%Y")


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)


def _days_to(value: Any) -> int | None:
    parsed = _parse_date(value)
    if not parsed:
        return None
    return (parsed - date.today()).days


def _days_label(days: int | None) -> str:
    if days is None:
        return "-"
    if days == 0:
        return "oggi"
    if days == 1:
        return "+1 gg"
    if days == -1:
        return "-1 gg"
    return f"{days:+d} gg" if days > 0 else f"{days} gg"


def _date_sort_value(value: Any, *, overdue: bool = False) -> int:
    parsed = _parse_date(value)
    if not parsed:
        return -10_000_000 if overdue else 10_000_000
    ordinal = parsed.toordinal()
    return -ordinal if overdue else ordinal


def _source_event_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    labels = {
        **SOURCE_EVENT_TYPE_LABELS,
        "pct_deposito": "Deposito telematico",
        "cancelleria_comunicazione": "Comunicazione di cancelleria",
        "notifica_giudice_pace": "Notifica giudiziaria",
        "notifica_pec": "Notifica PEC",
        "udienza_remota": "Udienza da remoto",
        "documento_fascicolo": "Documento notificato nel fascicolo",
    }
    return labels.get(raw, raw.replace("_", " ").title())


def _document_presidio_event_label(scadenza: Any) -> str:
    tipo = _enum_value(getattr(scadenza, "tipo", ""))
    title_context = _normalise_for_matching(getattr(scadenza, "titolo", ""))
    context = _normalise_for_matching(
        " ".join(
            str(value or "")
            for value in (
                getattr(scadenza, "titolo", ""),
                getattr(scadenza, "descrizione", ""),
                getattr(scadenza, "note", ""),
            )
        )
    )
    if "deposito note" in title_context or "deposito note" in context:
        return "Deposito note scritte"
    if "deposito memoria" in title_context or "deposito memoria" in context or tipo == TipoTermine.DEPOSITO_MEMORIA.value:
        return "Deposito memoria"
    if "deposito atto" in title_context or "deposito atto" in context or tipo == TipoTermine.DEPOSITO_ATTO.value:
        return "Deposito atto"
    if "notifica" in title_context or "notifica" in context or tipo == TipoTermine.NOTIFICA.value:
        return "Notifica"
    if tipo == TipoTermine.UDIENZA.value or "fissazione udienza" in title_context or "udienza da remoto" in context:
        return "Udienza"
    if tipo in {TipoTermine.TERMINE_PERENTORIO.value, TipoTermine.TERMINE_ORDINATORIO.value}:
        return "Termine processuale"
    if tipo == TipoTermine.ADEMPIMENTO.value:
        return "Attività processuale"
    return "Presidio documentale Lex"


def _source_event_label_for_scadenza(scadenza: Any) -> str:
    if _is_document_presidio_lex(scadenza):
        return _document_presidio_event_label(scadenza)
    if is_scadenza_pec(scadenza):
        summary = _pec_event_summary(_pec_context(scadenza))
        if "udienza" in summary:
            return "Udienza"
        if summary == "notifica giudiziaria":
            return "Notifica giudiziaria"
        if summary == "comunicazione di cancelleria":
            return "Comunicazione di cancelleria"
    return _source_event_label(getattr(scadenza, "source_event_type", ""))


def _priority_label(value: Any) -> str:
    priority = _enum_value(value)
    return {
        PrioritaTermine.CRITICA.value: "Critica",
        PrioritaTermine.ALTA.value: "Alta",
        PrioritaTermine.MEDIA.value: "Media",
        PrioritaTermine.BASSA.value: "Bassa",
    }.get(priority, priority.title() or "Media")


def _status_label(value: Any) -> str:
    status = _enum_value(value)
    return {
        StatoTermine.APERTO.value: "Aperta",
        StatoTermine.COMPLETATO.value: "Completata",
        StatoTermine.ANNULLATO.value: "Annullata",
        StatoTermine.SCADUTO.value: "Scaduta",
    }.get(status, status.title() or "Aperta")


def _type_label(value: Any) -> str:
    text = _enum_value(value)
    labels = {
        TipoTermine.UDIENZA.value: "Udienza",
        TipoTermine.DEPOSITO_MEMORIA.value: "Deposito memoria",
        TipoTermine.DEPOSITO_ATTO.value: "Deposito atto",
        TipoTermine.NOTIFICA.value: "Notifica",
        TipoTermine.IMPUGNAZIONE.value: "Impugnazione",
        TipoTermine.RISPOSTA_ECCEZIONE.value: "Risposta/eccezione",
        TipoTermine.PAGAMENTO.value: "Pagamento",
        TipoTermine.PRESCRIZIONE.value: "Prescrizione",
        TipoTermine.DECADENZA.value: "Decadenza",
        TipoTermine.ADEMPIMENTO.value: "Adempimento",
        TipoTermine.TERMINE_PERENTORIO.value: "Termine perentorio",
        TipoTermine.TERMINE_ORDINATORIO.value: "Termine ordinatorio",
        TipoTermine.ALTRO.value: "Altro",
    }
    return labels.get(text, text.replace("_", " ").title() if text else "Altro")


def _tone_for(priority: Any, status: Any, days: int | None) -> str:
    priority_value = _enum_value(priority)
    status_value = _enum_value(status)
    if status_value == StatoTermine.COMPLETATO.value:
        return "success"
    if status_value == StatoTermine.SCADUTO.value or (days is not None and days < 0):
        return "danger"
    if priority_value == PrioritaTermine.CRITICA.value:
        return "danger"
    if priority_value == PrioritaTermine.ALTA.value:
        return "warning"
    if priority_value == PrioritaTermine.BASSA.value:
        return "success"
    return "primary"


def _safe_get(manager: Any, item_id: str):
    if not manager or not item_id:
        return None
    getter = getattr(manager, "get", None)
    if not callable(getter):
        return None
    try:
        return getter(item_id)
    except Exception:
        return None


def _fascicolo_label(fascicolo: Any, fallback_id: str = "") -> str:
    if not fascicolo:
        return fallback_id or "-"
    rg = str(getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero_rg", "") or getattr(fascicolo, "numero", "") or "").strip()
    title = str(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "") or "").strip()
    if rg and title:
        return f"{rg} - {title}"
    return rg or title or fallback_id or "-"


def _client_label(scadenza: Any, fascicolo: Any = None) -> str:
    direct = str(
        getattr(scadenza, "nome_cliente", "")
        or getattr(scadenza, "cliente", "")
        or getattr(scadenza, "parte", "")
        or ""
    ).strip()
    if direct:
        return direct
    if fascicolo:
        fascicolo_client = str(
            getattr(fascicolo, "nome_cliente", "")
            or getattr(fascicolo, "cliente", "")
            or getattr(fascicolo, "parte", "")
            or ""
        ).strip()
        if fascicolo_client:
            return fascicolo_client
    return "-"


def _owner_label(scadenza: Any, gestione_utenti: Any, fascicolo: Any = None) -> str:
    user_id = str(getattr(scadenza, "id_utente_responsabile", "") or "").strip()
    utente = _safe_get(gestione_utenti, user_id)
    if not utente and user_id:
        by_username = getattr(gestione_utenti, "get_by_username", None)
        if callable(by_username):
            try:
                utente = by_username(user_id)
            except Exception:
                utente = None
    return (
        str(getattr(utente, "nome_completo", "") or "").strip()
        or str(getattr(utente, "username", "") or "").strip()
        or str(getattr(fascicolo, "avvocato_referente", "") or "").strip()
        or user_id
        or "-"
    )


def _trace_count(scadenza: Any) -> int:
    trace = getattr(scadenza, "trace", None)
    if isinstance(trace, list):
        return len(trace)
    raw = str(getattr(scadenza, "trace_json", "") or "").strip()
    if not raw:
        return 0
    try:
        import json

        parsed = json.loads(raw)
        return len(parsed) if isinstance(parsed, list) else 0
    except Exception:
        return 0


def _is_remote_hearing_ui_url(url: str, context: str = "") -> bool:
    try:
        from pct.pec_pipeline import _is_remote_hearing_url

        return _is_remote_hearing_url(str(url or ""), context=context)[0]
    except Exception:
        return False


def _remote_hearing_payload(scadenza: Any) -> dict[str, Any]:
    note = str(getattr(scadenza, "note", "") or "")
    url = str(getattr(scadenza, "remote_hearing_url", "") or "").strip()
    source = str(getattr(scadenza, "remote_hearing_source", "") or "").strip()
    if url and not _is_remote_hearing_ui_url(url, source or note):
        url = ""
    mode = str(getattr(scadenza, "remote_hearing_mode", "") or "").strip()
    time_value = str(getattr(scadenza, "remote_hearing_time", "") or "").strip()
    access_info = str(getattr(scadenza, "remote_hearing_access_info", "") or "").strip()
    pdf_required = bool(getattr(scadenza, "remote_hearing_pdf_required", False))
    detected = bool(getattr(scadenza, "remote_hearing_detected", False))
    if not url:
        for match in re.finditer(r"Link udienza audiovisiva:\s*(https?://\S+|www\.\S+)", note, flags=re.I):
            candidate = match.group(1).rstrip(".,;)")
            if _is_remote_hearing_ui_url(candidate, match.group(0)):
                url = candidate
                detected = True
                break
    if not source:
        match = re.search(r"Fonte link udienza:\s*([^\n]+)", note, flags=re.I)
        source = match.group(1).strip() if match else ""
    if not mode:
        match = re.search(r"Udienza da remoto:\s*([^\n]+)", note, flags=re.I)
        mode = match.group(1).strip() if match else ""
    if not time_value:
        match = re.search(r"Orario collegamento:\s*([^\n]+)", note, flags=re.I)
        time_value = match.group(1).strip() if match else ""
    if not access_info:
        match = re.search(r"Istruzioni accesso udienza:\s*([^\n]+)", note, flags=re.I)
        access_info = match.group(1).strip() if match else ""
    if "Link udienza audiovisiva: da acquisire" in note:
        pdf_required = True
        detected = True
    verified = bool(getattr(scadenza, "remote_hearing_verified", False))
    if "Verifica link udienza: identico alla fonte letta" in note:
        verified = True
    return {
        "remoteHearingDetected": bool(detected or url or pdf_required),
        "remoteHearingMode": _short_text(mode, 80),
        "remoteHearingUrl": url,
        "remoteHearingSource": _short_text(source, 140),
        "remoteHearingVerified": verified,
        "remoteHearingIntegrity": str(getattr(scadenza, "remote_hearing_integrity", "") or ""),
        "remoteHearingTime": _short_text(time_value, 80),
        "remoteHearingAccessInfo": _short_text(access_info, 220),
        "remoteHearingPdfRequired": pdf_required and not bool(url),
    }


def _row(scadenza: Any, *, gestione_fascicoli: Any, gestione_utenti: Any) -> dict[str, Any]:
    item_id = str(getattr(scadenza, "id", "") or "")
    due_date = str(getattr(scadenza, "data_scadenza", "") or "")
    days = getattr(scadenza, "giorni_alla_scadenza", None)
    if days is None:
        days = _days_to(due_date)
    fascicolo_id = str(getattr(scadenza, "id_fascicolo", "") or "")
    fascicolo = _safe_get(gestione_fascicoli, fascicolo_id)
    priority = _enum_value(getattr(scadenza, "priorita", PrioritaTermine.MEDIA.value)) or PrioritaTermine.MEDIA.value
    status = _enum_value(getattr(scadenza, "stato", StatoTermine.APERTO.value)) or StatoTermine.APERTO.value
    office_mode = str(getattr(scadenza, "judicial_office_operating_mode", "") or "").strip()
    patron_name = str(getattr(scadenza, "judicial_office_patron_name", "") or "").strip()
    patron_day = int(getattr(scadenza, "judicial_office_patron_day", 0) or 0)
    patron_month = int(getattr(scadenza, "judicial_office_patron_month", 0) or 0)
    patron_label = patron_name
    if patron_name and patron_day and patron_month:
        patron_label = f"{patron_name} ({patron_day:02d}/{patron_month:02d})"
    remote_payload = _remote_hearing_payload(scadenza)
    return {
        "id": item_id,
        "date": due_date,
        "dateLabel": _format_date(due_date),
        "title": _legal_scadenza_title(scadenza),
        "description": _legal_scadenza_description(scadenza),
        "detailDescription": _legal_scadenza_detail_description(scadenza),
        "type": _enum_value(getattr(scadenza, "tipo", TipoTermine.ALTRO.value)) or TipoTermine.ALTRO.value,
        "typeLabel": _type_label(getattr(scadenza, "tipo", TipoTermine.ALTRO.value)),
        "priority": priority,
        "priorityLabel": _priority_label(priority),
        "tone": _tone_for(priority, status, days),
        "status": status,
        "statusLabel": _status_label(status),
        "days": days,
        "daysLabel": _days_label(days),
        "overdue": bool(days is not None and days < 0) or status == StatoTermine.SCADUTO.value,
        "dueToday": days == 0,
        "peremptory": bool(getattr(scadenza, "perentorio", False)),
        "advanced": bool(getattr(scadenza, "ha_calcolo_avanzato", False)),
        "operative": bool(getattr(scadenza, "operational_due_at", "")),
        "operationalDueAt": str(getattr(scadenza, "operational_due_at", "") or ""),
        "operationalDueLabel": _format_date(getattr(scadenza, "operational_due_at", "")),
        "fascicoloId": fascicolo_id,
        "fascicoloLabel": _fascicolo_label(fascicolo, fascicolo_id),
        "clientLabel": _client_label(scadenza, fascicolo),
        "ownerLabel": _owner_label(scadenza, gestione_utenti, fascicolo),
        "sourceEventAt": str(getattr(scadenza, "source_event_at", "") or getattr(scadenza, "data_decorrenza", "") or ""),
        "sourceEventLabel": _format_date(getattr(scadenza, "source_event_at", "") or getattr(scadenza, "data_decorrenza", "")),
        "sourceEventType": str(getattr(scadenza, "source_event_type", "") or ""),
        "sourceEventTypeLabel": _source_event_label_for_scadenza(scadenza),
        "officeLabel": str(getattr(scadenza, "judicial_office_name", "") or getattr(fascicolo, "tribunale", "") or ""),
        "officeModeLabel": OFFICE_MODE_LABELS.get(office_mode, office_mode.replace("_", " ").title() if office_mode else ""),
        "officePatronLabel": patron_label,
        "officeVerifiedAt": str(getattr(scadenza, "judicial_office_verified_at", "") or ""),
        "octoberObservanceBlocks": bool(getattr(scadenza, "october_observance_blocks", False)),
        "traceCount": _trace_count(scadenza),
        **remote_payload,
        "href": f"/scadenziario/{item_id}?vista=tutte",
        "editHref": f"/scadenziario/{item_id}/modifica",
        "completeHref": f"/scadenziario/{item_id}/completa",
        "deleteHref": f"/scadenziario/{item_id}/elimina",
    }


def _all_scadenze(gestione_scadenziario: Any) -> list[Any]:
    try:
        gestione_scadenziario.scadute()
    except Exception:
        pass
    try:
        return list(gestione_scadenziario.tutte(solo_aperte=False))
    except Exception:
        return []


def _is_open(item: Any) -> bool:
    return _enum_value(getattr(item, "stato", "")) == StatoTermine.APERTO.value


def _is_completed(item: Any) -> bool:
    return _enum_value(getattr(item, "stato", "")) == StatoTermine.COMPLETATO.value


def _is_overdue(item: Any) -> bool:
    status = _enum_value(getattr(item, "stato", ""))
    days = getattr(item, "giorni_alla_scadenza", None)
    if days is None:
        days = _days_to(getattr(item, "data_scadenza", ""))
    return status == StatoTermine.SCADUTO.value or bool(days is not None and days < 0)


def _summary(all_items: list[Any]) -> dict[str, int]:
    open_items = [item for item in all_items if _is_open(item)]
    pec_items = [item for item in all_items if is_scadenza_pec(item)]
    pec_operational_items = [item for item in pec_items if _is_open(item) and not _is_overdue(item)]
    def days(item: Any) -> int | None:
        current = getattr(item, "giorni_alla_scadenza", None)
        return current if current is not None else _days_to(getattr(item, "data_scadenza", ""))

    return {
        "total": len(all_items),
        "open": len(open_items),
        "critical": sum(1 for item in open_items if _enum_value(getattr(item, "priorita", "")) == PrioritaTermine.CRITICA.value),
        "high": sum(1 for item in open_items if _enum_value(getattr(item, "priorita", "")) == PrioritaTermine.ALTA.value),
        "completed": sum(1 for item in all_items if _is_completed(item)),
        "overdue": sum(1 for item in all_items if _is_overdue(item)),
        "within7": sum(1 for item in open_items if (days(item) is not None and 0 <= int(days(item)) <= 7)),
        "advanced": sum(1 for item in all_items if bool(getattr(item, "ha_calcolo_avanzato", False))),
        "operative": sum(1 for item in all_items if bool(getattr(item, "operational_due_at", ""))),
        "pec": len(pec_operational_items),
        "pec_open": len(pec_operational_items),
        "pec_overdue": sum(1 for item in pec_items if _is_overdue(item)),
        "pec_future": len(pec_operational_items),
        "peremptory": sum(1 for item in all_items if bool(getattr(item, "perentorio", False))),
    }


def _facet(value: str, label: str, count: int) -> dict[str, Any]:
    return {"value": value, "label": label, "count": count}


def _facets(all_items: list[Any], summary: dict[str, int]) -> dict[str, list[dict[str, Any]]]:
    type_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for item in all_items:
        type_counts[_enum_value(getattr(item, "tipo", TipoTermine.ALTRO.value))] = type_counts.get(_enum_value(getattr(item, "tipo", TipoTermine.ALTRO.value)), 0) + 1
        priority_counts[_enum_value(getattr(item, "priorita", PrioritaTermine.MEDIA.value))] = priority_counts.get(_enum_value(getattr(item, "priorita", PrioritaTermine.MEDIA.value)), 0) + 1
        status_counts[_enum_value(getattr(item, "stato", StatoTermine.APERTO.value))] = status_counts.get(_enum_value(getattr(item, "stato", StatoTermine.APERTO.value)), 0) + 1
    return {
        "views": [
            _facet("aperte", "Aperte", summary["open"]),
            _facet("critiche", "Critiche", summary["critical"]),
            _facet("alte", "Alta priorità", summary["high"]),
            _facet("completate", "Completate", summary["completed"]),
            _facet("scadute", "Scadute", summary["overdue"]),
            _facet("imminenti", "Entro 7 gg", summary["within7"]),
            _facet("avanzate", "Avanzate", summary["advanced"]),
            _facet("operative", "Operative", summary["operative"]),
            _facet("pec", "Da PEC", summary["pec"]),
            _facet("tutte", "Tutte", summary["total"]),
        ],
        "types": [_facet("", "Tutti i tipi", len(all_items))] + [
            _facet(tipo.value, _type_label(tipo), type_counts.get(tipo.value, 0)) for tipo in TipoTermine
        ],
        "priorities": [_facet("", "Tutte le priorità", len(all_items))] + [
            _facet(priority.value, _priority_label(priority), priority_counts.get(priority.value, 0)) for priority in PrioritaTermine
        ],
        "statuses": [_facet("", "Tutti gli stati", len(all_items))] + [
            _facet(status.value, _status_label(status), status_counts.get(status.value, 0)) for status in StatoTermine
        ],
    }


def _bool_arg(args: Mapping[str, Any], key: str) -> bool:
    return str(args.get(key, "") or "").strip().lower() in {"1", "true", "on", "yes"}


def _text_arg(args: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        raw = str(args.get(key, "") or "").strip()
        if raw:
            return raw
    return ""


def _filtered_scadenze(gestione_scadenziario: Any, args: Mapping[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    vista = normalizza_vista_scadenziario(str(args.get("vista", "aperte") or "aperte"))
    tipo_raw = str(args.get("tipo", "") or "").strip()
    priority_raw = str(args.get("priorita", "") or "").strip()
    id_fascicolo = str(args.get("id_fascicolo", "") or "").strip()
    q = str(args.get("q", "") or "").strip()
    from_raw = str(args.get("dal", "") or "").strip()
    to_raw = str(args.get("al", "") or "").strip()
    peremptory = _bool_arg(args, "perentorio")
    advanced = _bool_arg(args, "avanzate")
    operative = _bool_arg(args, "operative")
    guida_pratica = _text_arg(args, "guida_pratica", "guidaPratica", "codice_guida", "codiceGuida")
    try:
        tipo = TipoTermine(tipo_raw) if tipo_raw else None
    except ValueError:
        tipo = None
        tipo_raw = ""
    try:
        priority = PrioritaTermine(priority_raw) if priority_raw else None
    except ValueError:
        priority = None
        priority_raw = ""

    scadenze = scadenze_per_vista(
        gestione_scadenziario,
        vista=vista,
        tipo=tipo,
        priorita=priority,
        id_fascicolo=id_fascicolo,
    )
    if q:
        ql = q.lower()
        scadenze = [
            item for item in scadenze
            if ql in str(getattr(item, "titolo", "") or "").lower()
            or ql in str(getattr(item, "descrizione", "") or "").lower()
            or ql in str(getattr(item, "note", "") or "").lower()
        ]
    if from_raw:
        scadenze = [item for item in scadenze if str(getattr(item, "data_scadenza", "") or "") >= from_raw]
    if to_raw:
        scadenze = [item for item in scadenze if str(getattr(item, "data_scadenza", "") or "") <= to_raw]
    if peremptory:
        scadenze = [item for item in scadenze if bool(getattr(item, "perentorio", False))]
    if advanced:
        scadenze = [item for item in scadenze if bool(getattr(item, "ha_calcolo_avanzato", False))]
    if operative:
        scadenze = [item for item in scadenze if bool(getattr(item, "operational_due_at", ""))]
    if vista == "scadute":
        scadenze.sort(
            key=lambda item: (
                _date_sort_value(getattr(item, "data_scadenza", ""), overdue=True),
                _enum_value(getattr(item, "priorita", "")),
            )
        )
    else:
        scadenze.sort(
            key=lambda item: (
                1 if _is_overdue(item) else 0,
                _date_sort_value(getattr(item, "data_scadenza", ""), overdue=_is_overdue(item)),
                _enum_value(getattr(item, "priorita", "")),
            )
        )
    return scadenze, {
        "view": vista,
        "viewLabel": VISTA_LABEL_SCADENZIARIO.get(vista, "Scadenze"),
        "q": q,
        "type": tipo_raw,
        "priority": priority_raw,
        "from": from_raw,
        "to": to_raw,
        "peremptory": peremptory,
        "advanced": advanced,
        "operative": operative,
        "guidaPratica": guida_pratica,
        "fascicoloId": id_fascicolo,
    }


def _card(card_id: str, title: str, description: str, value: Any, tone: str, icon: str, *, label: str, kind: str = "link", href: str = "", view: str = "") -> dict[str, Any]:
    return {
        "id": card_id,
        "title": title,
        "description": description,
        "value": value,
        "tone": tone,
        "icon": icon,
        "action": {
            "kind": kind,
            "label": label,
            "href": href,
            "view": view,
        },
    }

def _operative_cards(summary: dict[str, int]) -> list[dict[str, Any]]:
    return [
        _card(
            "overdue",
            "Scadute da chiudere",
            "Apri subito i termini scaduti non completati e decidi se completarli, correggerli o riassegnarli.",
            summary["overdue"],
            "danger" if summary["overdue"] else "neutral",
            "alert",
            kind="filter",
            label="Apri scadute",
            view="scadute",
        ),
        _card(
            "critical",
            "Presidio critico",
            "Filtra le scadenze critiche e lavora prima quelle con fascicolo o udienza collegata.",
            summary["critical"],
            "danger" if summary["critical"] else "neutral",
            "calendar",
            kind="filter",
            label="Mostra critiche",
            view="critiche",
        ),
        _card(
            "pec",
            "Scadenze da PEC",
            "Apri le scadenze PEC ancora operative, con agenda e priorità collegate. I termini già superati restano nello storico dei controlli.",
            summary["pec"],
            "info",
            "archive",
            kind="filter",
            label="Apri PEC operative",
            view="pec",
        ),
        _card(
            "bulk-complete",
            "Completa selezionate",
            "Seleziona le righe e chiudi insieme i termini già lavorati.",
            "bulk",
            "success",
            "check",
            kind="bulk_complete",
            label="Completa selezione",
        ),
    ]


def _calculator_templates(scadenziario_db_path: str = "") -> list[dict[str, Any]]:
    anchor = str(scadenziario_db_path or "").strip()
    if anchor:
        try:
            templates = DeadlinePracticeRepository.json(_deadline_repository_path(anchor)).list_templates()
            if templates:
                return templates
        except Exception:
            pass
    return [template.to_dict() for template in DEFAULT_TEMPLATES]


def _deadline_repository_path(scadenziario_db_path: str) -> str:
    return str(Path(scadenziario_db_path).with_name("termini_processuali.json"))


def _normalizza_chiave_template(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _template_metadata(template: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = template.get("metadata") if isinstance(template.get("metadata"), Mapping) else {}
    return metadata


def _calculator_template_dedupe_key(template: Mapping[str, Any]) -> tuple[Any, ...]:
    metadata = _template_metadata(template)
    return (
        _normalizza_chiave_template(template.get("name")),
        _normalizza_chiave_template(template.get("matter_type")),
        int(template.get("base_value") or 0),
        _normalizza_chiave_template(template.get("period_type")),
        _normalizza_chiave_template(template.get("direction")),
        bool(template.get("suspend_august")),
        _normalizza_chiave_template(template.get("ferial_suspension_policy")),
        bool(template.get("free_term")),
        bool(template.get("urgent")),
        bool(template.get("extend_saturday")),
        bool(template.get("extend_holiday")),
        _normalizza_chiave_template(template.get("reference_law")),
        bool(template.get("cartabia_compliant", True)),
        _normalizza_chiave_template(metadata.get("decorrenza") or metadata.get("source_event")),
        _normalizza_chiave_template(metadata.get("natura")),
    )


def dedupe_calculator_templates(templates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Riduce i duplicati di presentazione senza fondere regole diverse.

    Le schede della Guida Pratica possono generare molti template con codici
    interni differenti ma identica regola di calcolo. Nel calcolatore l'avvocato
    deve vedere una sola voce per ogni termine realmente distinto.
    """

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for template in templates:
        if not isinstance(template, Mapping):
            continue
        key = _calculator_template_dedupe_key(template)
        if key not in unique:
            unique[key] = dict(template)
    return _calculator_templates_with_display_names(list(unique.values()))


def _template_period_label(template: Mapping[str, Any]) -> str:
    unit = "mesi" if str(template.get("period_type") or "").strip() == "months" else "giorni"
    value = int(template.get("base_value") or 0)
    direction = "a ritroso" if str(template.get("direction") or "").strip() == "backward" else "in avanti"
    return f"{value} {unit} {direction}"


def _calculator_templates_with_display_names(templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    name_counts: dict[str, int] = {}
    for template in templates:
        name = _normalizza_chiave_template(template.get("name"))
        name_counts[name] = name_counts.get(name, 0) + 1

    labelled: list[tuple[dict[str, Any], str]] = []
    label_counts: dict[str, int] = {}
    for template in templates:
        name = str(template.get("name") or "Termine processuale").strip() or "Termine processuale"
        label = name
        if name_counts.get(_normalizza_chiave_template(name), 0) > 1:
            metadata = _template_metadata(template)
            detail_parts = [
                _template_period_label(template),
                str(template.get("reference_law") or "").strip(),
                str(metadata.get("denominazione_guida") or metadata.get("codice_guida") or "").strip(),
            ]
            details = " - ".join(part for part in detail_parts if part)
            label = f"{name} - {details}" if details else name
        labelled.append((template, label))
        label_counts[label] = label_counts.get(label, 0) + 1

    out: list[dict[str, Any]] = []
    for template, label in labelled:
        if label_counts.get(label, 0) > 1:
            metadata = _template_metadata(template)
            suffix = str(metadata.get("codice_guida") or template.get("code") or "").strip()
            if suffix:
                label = f"{label} - {suffix}"
        enriched = dict(template)
        enriched["displayName"] = label
        out.append(enriched)
    return out


def _templates_for_guide(templates: list[dict[str, Any]], codice_guida: str) -> list[dict[str, Any]]:
    code = str(codice_guida or "").strip()
    if not code:
        return dedupe_calculator_templates(templates)
    matched: list[dict[str, Any]] = []
    for template in templates:
        metadata = template.get("metadata") if isinstance(template.get("metadata"), dict) else {}
        if str(metadata.get("codice_guida") or "").strip() == code:
            matched.append(template)
            continue
        if str(metadata.get("codice_originale_guida") or "").strip() == code:
            matched.append(template)
    return dedupe_calculator_templates(matched or templates)


def build_react_scadenziario_payload(
    *,
    gestione_scadenziario: Any,
    gestione_fascicoli: Any,
    gestione_utenti: Any = None,
    query_args: Mapping[str, Any] | None = None,
    termini_processuali_db: str = "",
) -> dict[str, Any]:
    args: Mapping[str, Any] = query_args or {}
    all_items = _all_scadenze(gestione_scadenziario)
    summary = _summary(all_items)
    filtered, query = _filtered_scadenze(gestione_scadenziario, args)
    calculator_templates = _templates_for_guide(
        _calculator_templates(termini_processuali_db),
        str(query.get("guidaPratica") or ""),
    )
    rows = [_row(item, gestione_fascicoli=gestione_fascicoli, gestione_utenti=gestione_utenti) for item in filtered]
    overdue_preview = []
    if query.get("view") in {"scadute", "tutte"}:
        overdue_preview = [
            _row(item, gestione_fascicoli=gestione_fascicoli, gestione_utenti=gestione_utenti)
            for item in sorted(
                [item for item in all_items if _is_overdue(item)],
                key=lambda item: _date_sort_value(getattr(item, "data_scadenza", ""), overdue=True),
            )[:5]
        ]
    next_items = [
        _row(item, gestione_fascicoli=gestione_fascicoli, gestione_utenti=gestione_utenti)
        for item in sorted([item for item in all_items if _is_open(item) and not _is_overdue(item)], key=lambda item: str(getattr(item, "data_scadenza", "") or ""))[:5]
    ]
    return {
        "generatedAt": _iso_now(),
        "source": "repository_reali",
        "contracts": {
            "mock_fallback": False,
            "read_only": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "query": query,
        "summary": summary,
        "items": rows,
        "overduePreview": overdue_preview,
        "nextItems": next_items,
        "operativeCards": _operative_cards(summary),
        "calculator": {
            "templates": calculator_templates,
            "engineVersion": ENGINE_VERSION,
            "rulesetVersion": RULESET_VERSION,
            "calendarVersion": CALENDAR_VERSION,
            "legalSources": list(LEGAL_SOURCES),
            "endpoints": {
                "calculate": "/api/v1/ui/scadenziario/termini/calculate",
                "explain": "/api/v1/ui/scadenziario/termini/explain",
                "validate": "/api/v1/ui/scadenziario/termini/validate",
                "audit": "/api/v1/ui/scadenziario/termini/audit",
                "override": "/api/v1/ui/scadenziario/termini/override",
                "createDeadline": "/api/v1/ui/scadenziario/termini/crea-scadenza",
                "pdfPreview": "/api/v1/ui/scadenziario/pdf-scadenze/anteprima",
                "pdfImport": "/api/v1/ui/scadenziario/pdf-scadenze/importa",
            },
            "scheduler": {
                "thresholds": [30, 15, 7, 1, 0],
                "channel": "PEC",
                "mode": "pianificazione_idempotente_con_audit",
            },
        },
        "facets": _facets(all_items, summary),
        "actions": {
            "new": "/scadenziario/nuova",
            "exportCsv": "/scadenziario/export.csv",
            "exportPdf": "/scadenziario/pdf",
            "exportIcs": "/scadenziario/export.ics",
            "agenda": "/agenda",
            "calendarSettings": "/impostazioni/calendario",
            "lex": "#lex",
            "bulkComplete": "/scadenziario/bulk-completa",
        },
    }


# Payload React per /scadenziario/nuova
def _safe_text(value: Any, default: str = "") -> str:
    return str(value or default).strip()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _label_from_enum(value: Any) -> str:
    raw = _enum_value(value)
    return raw.replace("_", " ").title() if raw else ""


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            payload = value.to_dict()
            return dict(payload) if isinstance(payload, dict) else {}
        except Exception:
            return {}
    return {}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return _safe_text(getattr(value, "value", ""))
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            return _safe_text(value)
    return _safe_text(value)


def _safe_items(loader: Callable[[], Iterable[Any]] | None) -> list[Any]:
    if not callable(loader):
        return []
    try:
        value = loader()
        return list(value or [])
    except Exception:
        return []


def _call_tutti(repo: Any, *args: Any, **kwargs: Any) -> list[Any]:
    if repo is None:
        return []
    if isinstance(repo, list):
        return repo
    method = getattr(repo, "tutti", None)
    if not callable(method):
        return []
    try:
        return list(method(*args, **kwargs) or [])
    except TypeError:
        try:
            return list(method() or [])
        except Exception:
            return []
    except Exception:
        return []


def _fascicolo_option(item: Any) -> dict[str, Any]:
    item_id = _safe_text(getattr(item, "id", ""))
    rg = (
        _safe_text(getattr(item, "rg_completo", ""))
        or _safe_text(getattr(item, "numero_rg", ""))
        or _safe_text(getattr(item, "numero", ""))
    )
    title = _safe_text(getattr(item, "titolo", "")) or _safe_text(getattr(item, "oggetto", "")) or "Fascicolo"
    court = _safe_text(getattr(item, "tribunale", ""))
    client = _safe_text(getattr(item, "nome_cliente", "")) or _safe_text(getattr(item, "cliente", ""))
    prefix = f"{rg} - " if rg else ""
    return {
        "id": item_id,
        "value": item_id,
        "label": f"{prefix}{title}",
        "subtitle": " • ".join(part for part in [court, client] if part),
        "badge": _enum_value(getattr(item, "stato", "")),
    }


def _utente_option(item: Any) -> dict[str, Any]:
    item_id = _safe_text(getattr(item, "id", ""))
    label = (
        _safe_text(getattr(item, "nome_completo", ""))
        or " ".join(part for part in [_safe_text(getattr(item, "nome", "")), _safe_text(getattr(item, "cognome", ""))] if part)
        or _safe_text(getattr(item, "username", ""))
        or _safe_text(getattr(item, "email", ""))
        or "Utente"
    )
    return {
        "id": item_id,
        "value": item_id,
        "label": label,
        "subtitle": _safe_text(getattr(item, "email", "")),
        "badge": _enum_value(getattr(item, "ruolo", "")),
    }


def _preset_options() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in PRESET_TERMINI.items():
        payload = _as_dict(value)
        label = (
            _safe_text(payload.get("label"))
            or _safe_text(payload.get("titolo"))
            or _safe_text(payload.get("name"))
            or key.replace("_", " ").title()
        )
        rows.append(
            {
                "key": key,
                "label": label,
                "description": _safe_text(payload.get("description") or payload.get("descrizione") or payload.get("notes")),
                "title_template": _safe_text(payload.get("title_template") or payload.get("titolo") or label),
                "deadline_profile_code": _safe_text(payload.get("deadline_profile_code") or payload.get("profile_code") or payload.get("profile")),
                "tipo": _safe_text(payload.get("tipo") or payload.get("type")),
                "source_event_type": _safe_text(payload.get("source_event_type")),
                "metadata": _json_safe(payload),
            }
        )
    return rows


def _studio_payload(config_loader: Callable[[], Any] | None) -> dict[str, Any]:
    try:
        config_holder = config_loader() if callable(config_loader) else None
        studio = getattr(getattr(config_holder, "config", config_holder), "studio", None)
    except Exception:
        studio = None
    if studio is None:
        return {}

    def get_any(*names: str) -> str:
        for name in names:
            value = getattr(studio, name, "")
            if value:
                return _safe_text(value)
            if isinstance(studio, dict) and studio.get(name):
                return _safe_text(studio.get(name))
        return ""

    return {
        "nome": get_any("nome", "denominazione", "studio_nome", "name"),
        "patron_name": get_any("patrono_nome", "patrono", "santo_patrono", "patron_name", "studio_patron_name"),
        "patron_day": get_any("patrono_giorno", "patron_day", "studio_patron_day"),
        "patron_month": get_any("patrono_mese", "patron_month", "studio_patron_month"),
    }


def _date_input(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _datetime_input(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return raw[:16]


def _scadenza_form_defaults(scadenza: Any | None) -> dict[str, Any]:
    if scadenza is None:
        return {
            "tipo": TipoTermine.UDIENZA.value,
            "operational_lead_business_days": "2",
            "office_operating_mode": "open",
        }
    return {
        "titolo": _safe_text(getattr(scadenza, "titolo", "")),
        "tipo": _enum_value(getattr(scadenza, "tipo", TipoTermine.UDIENZA.value)) or TipoTermine.UDIENZA.value,
        "preset": _safe_text(getattr(scadenza, "preset", "")),
        "deadline_profile_code": _safe_text(getattr(scadenza, "deadline_profile_code", "")),
        "source_event_at": _datetime_input(getattr(scadenza, "source_event_at", "") or getattr(scadenza, "data_decorrenza", "")),
        "data_scadenza": _date_input(getattr(scadenza, "data_scadenza", "")),
        "data_decorrenza": _date_input(getattr(scadenza, "data_decorrenza", "")),
        "perentorio": bool(getattr(scadenza, "perentorio", False)),
        "id_fascicolo": _safe_text(getattr(scadenza, "id_fascicolo", "")),
        "id_utente": _safe_text(getattr(scadenza, "id_utente_responsabile", "")),
        "descrizione": _safe_text(getattr(scadenza, "descrizione", "")),
        "note": _safe_text(getattr(scadenza, "note", "")),
        "judicial_office_id": _safe_text(getattr(scadenza, "judicial_office_id", "")),
        "office_patron_name": _safe_text(getattr(scadenza, "office_patron_name", "")),
        "office_patron_day": _safe_text(getattr(scadenza, "office_patron_day", "")),
        "office_patron_month": _safe_text(getattr(scadenza, "office_patron_month", "")),
        "office_operating_mode": _safe_text(getattr(scadenza, "office_operating_mode", "open"), "open"),
        "office_source_url": _safe_text(getattr(scadenza, "office_source_url", "")),
        "office_verified_at": _date_input(getattr(scadenza, "office_verified_at", "")),
        "operational_lead_business_days": _safe_text(getattr(scadenza, "operational_lead_business_days", "2"), "2"),
        "october_observance_blocks": bool(getattr(scadenza, "october_observance_blocks", False)),
        "id_cliente": _safe_text(getattr(scadenza, "id_cliente", "")),
        "from_cliente": _safe_text(getattr(scadenza, "id_cliente", "")),
    }
def build_react_scadenziario_nuova_payload(
    *,
    fascicoli_loader: Callable[[], Any] | None,
    utenti_loader: Callable[[], Any] | None,
    config_loader: Callable[[], Any] | None,
    scadenziario_loader: Callable[[], Any] | None = None,
    id_scadenza: str = "",
) -> dict[str, Any]:
    fascicoli_repo = fascicoli_loader() if callable(fascicoli_loader) else None
    utenti_repo = utenti_loader() if callable(utenti_loader) else None
    fascicoli = _call_tutti(fascicoli_repo, archiviati=False)
    utenti = _call_tutti(utenti_repo, solo_attivi=True)
    profiles = list(profili_termine_builtin().values())
    scadenza = None
    if id_scadenza and callable(scadenziario_loader):
        try:
            scadenza = scadenziario_loader().get(id_scadenza)
        except Exception:
            scadenza = None
    mode = "edit" if scadenza is not None else "new"
    write_endpoint = f"/scadenziario/{id_scadenza}/modifica" if mode == "edit" else "/scadenziario/nuova"

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "mode": mode,
        "id_scadenza": id_scadenza if mode == "edit" else "",
        "tipi": [
            {"value": tipo.value, "label": tipo.value, "description": _label_from_enum(tipo)}
            for tipo in TipoTermine
        ],
        "preset_list": _preset_options(),
        "profili_termine": profiles,
        "fascicoli": [_fascicolo_option(item) for item in fascicoli],
        "utenti": [_utente_option(item) for item in utenti],
        "office_modes": [
            {"value": value, "label": label}
            for value, label in OFFICE_MODE_LABELS.items()
        ],
        "office_kinds": [
            "Tutti",
            "Tribunale",
            "Procura",
            "Proc.Gen.",
            "Corte d'App.",
            "Cassazione",
            "Assise",
            "G.d.P.",
            "Minori",
            "Sorv.",
            "TAR",
            "CdS",
            "CGARS",
            "CGT",
            "CPT",
        ],
        "studio": _studio_payload(config_loader),
        "defaults": _scadenza_form_defaults(scadenza),
        "actions": {
            "write_endpoint": write_endpoint,
            "calculate_endpoint": "/scadenziario/calcola-termine",
            "detail": f"/scadenziario/{id_scadenza}" if mode == "edit" else "/scadenziario",
            "list": "/scadenziario",
        },
        "contracts": {
            "mock_fallback": False,
            "write_endpoint": write_endpoint,
            "calculate_endpoint": "/scadenziario/calcola-termine",
        },
    }
