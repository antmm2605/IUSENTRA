"""Read-only payload for the React agenda migration page."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote

from pct.pec_operational_cleanup import is_legacy_pec_agenda_item, is_legacy_pec_deadline
from web.services.pec_source_links import (
    control_tower_source_key,
    extract_pec_attachment_source,
    is_generic_pec_source_label,
    latest_control_tower_sources,
    latest_pec_profiles,
    pec_audit_message_id,
    pec_profile_source_name,
    pec_original_label,
    pec_source_href,
    resolve_pec_source_name,
)


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
PEC_HEARING_TIME_RE = re.compile(
    r"(?<!\d)(?:ore\s*)?([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)",
    re.IGNORECASE,
)
TECHNICAL_VISIBLE_RE = re.compile(
    r"\b(?:PEC_AUDIT|pdf-deadline|pdf-semantic|pipeline|audit-grade|source_event|profile_id|payload|runtime|backend|frontend|legacy|json_api|external_uid|external_provider|worker|job|provider)\b",
    re.IGNORECASE,
)
NON_PARTY_RE = re.compile(r"\b(?:UDIENZA|COMUNICAZIONE|FISSATA|FISSATO|PRIMA|COMPAR|TRATT|ART\.?|DESCRIZIONE|OGGETTO)\b", re.IGNORECASE)
REMOTE_HEARING_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
GENERIC_PEC_SOURCE_LABELS = {
    "corpo pec",
    "oggetto pec",
    "testo pec",
    "testo/href",
    "testo / href",
    "href pec",
    "pec",
}
GENERIC_REMOTE_HEARING_PLATFORMS = {
    "altra",
    "da verificare",
    "incerta",
    "sconosciuta",
}
DOCUMENT_PRESIDIO_CANCEL_REASON_LABELS = {
    "atto_di_parte_non_genera_adempimento_automatico": "atto di parte: non genera un adempimento automatico",
    "periodo_descrittivo_o_contrattuale_non_e_termino_processuale": "periodo descrittivo o contrattuale, non termine processuale",
    "fonte_non_qualificata_come_provvedimento_o_comunicazione_ufficio": "fonte non qualificata come provvedimento o comunicazione dell'ufficio",
    "provvedimento_decisorio_prevale_su_termine_o_udienza_pregressa": "provvedimento decisorio: non resta un termine o un'udienza pregressa da presidiare",
    "data_senza_ordine_processuale_esplicito": "data priva di un ordine processuale esplicito",
}
DOCUMENT_PRESIDIO_CANCEL_MARKERS = (
    "presidio documentale automatico annullato",
    "la fonte non contiene un adempimento dell'ufficio",
    *DOCUMENT_PRESIDIO_CANCEL_REASON_LABELS.keys(),
)


def _is_legal_notification_text(*values: str) -> bool:
    text = " ".join(str(value or "") for value in values)
    folded = text.lower()
    return "iusentra_legal_notification:" in folded or "legal-notification-presidio" in folded


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


def _remote_hearing_platform_for_ui(item: Any) -> str:
    platform = _clean_text(getattr(item, "remote_hearing_platform", "") or "", limit=120)
    access_info = _clean_text(getattr(item, "remote_hearing_access_info", "") or "", limit=1600)
    if access_info and platform.casefold() in GENERIC_REMOTE_HEARING_PLATFORMS:
        return ""
    return platform


def _is_generic_pec_source_label(value: Any) -> bool:
    """Riconosce etichette tecniche interne della PEC, non nomi di allegato."""

    return is_generic_pec_source_label(value)


def _pec_original_label(source_name: str) -> str:
    """Etichetta utente per una fonte PEC: allegato vero o PEC nel suo insieme."""

    return pec_original_label(source_name)


def _pec_source_href(message_id: str, source_name: str) -> str:
    """Apre subito l'allegato ZIP/PDF della PEC quando è identificato."""

    return pec_source_href(message_id, source_name)


def _extract_pec_attachment_source(notes: str) -> str:
    """Recupera il nome dell'allegato utile anche da note PEC meno recenti."""

    return extract_pec_attachment_source(notes)


def _source_evidence(
    notes: str,
    *,
    matter_id: str = "",
    external_source_url: str = "",
    external_uid: str = "",
    source_name: str = "",
    indexed_source_name: str = "",
) -> dict[str, Any]:
    """Collega ogni dato automatico alla PEC o al documento che lo ha prodotto."""

    document_match = re.search(
        r"\b(?:PEC_DOCUMENT_PRESIDIO|PEC_AUDIT):docpresidio:([^:\s]+):([^:\s]+):([^:\s]+):([^\s]+)",
        notes,
        re.IGNORECASE,
    )
    if document_match:
        source_fascicolo_id = document_match.group(1).strip()
        document_id = document_match.group(2).strip()
        label = _extract_labeled_line(notes, "Fonte documentale", limit=140)
        return {
            "sourceHref": (
                f"/fascicoli/{quote(source_fascicolo_id, safe='')}/documenti/"
                f"{quote(document_id, safe='')}/visualizza"
            ),
            "sourceLabel": label or "Documento del fascicolo",
            "sourceKind": "documento",
            "sourceVerified": True,
        }

    event_source_name = resolve_pec_source_name(source_name, notes, limit=140)
    if event_source_name and not is_generic_pec_source_label(event_source_name):
        source_name = event_source_name
    else:
        source_name = resolve_pec_source_name(indexed_source_name, limit=140) or event_source_name

    message_id = pec_audit_message_id("\n".join(part for part in (notes, external_uid) if part))
    if message_id:
        source_label = _clean_text(source_name, limit=120)
        return {
            "sourceHref": _pec_source_href(message_id, source_label),
            "sourceLabel": _pec_original_label(source_label),
            "sourceKind": "pec",
            "sourceVerified": True,
        }

    external_href = str(external_source_url or "").strip()
    external_match = re.fullmatch(r"/api/pec/messages/([^/]+)", external_href)
    if external_match:
        message_id = external_match.group(1)
        return {
            "sourceHref": _pec_source_href(message_id, source_name),
            "sourceLabel": _pec_original_label(source_name),
            "sourceKind": "pec",
            "sourceVerified": True,
        }
    if external_href.startswith(("https://", "http://", "/")):
        return {
            "sourceHref": external_href,
            "sourceLabel": _clean_text(source_name, limit=140) or "Calendario collegato",
            "sourceKind": "calendario",
            "sourceVerified": False,
        }
    if _is_legal_notification_text(notes, source_name):
        return {
            "sourceHref": "",
            "sourceLabel": "PEC sorgente da riallineare",
            "sourceKind": "pec",
            "sourceVerified": False,
        }
    if matter_id and source_name:
        return {
            "sourceHref": f"/fascicoli/{quote(matter_id, safe='')}#documenti",
            "sourceLabel": _clean_text(source_name, limit=140),
            "sourceKind": "fascicolo",
            "sourceVerified": False,
        }
    return {
        "sourceHref": "",
        "sourceLabel": "",
        "sourceKind": "",
        "sourceVerified": False,
    }


def _remote_hearing_url(*values: Any) -> str:
    for value in values:
        match = REMOTE_HEARING_URL_RE.search(str(value or ""))
        if match:
            return match.group(0).rstrip(".,;:)]}")[:900]
    return ""


def _is_remote_hearing_ui_url(url: str, context: str = "") -> bool:
    try:
        from pct.pec_pipeline import _is_remote_hearing_url

        return _is_remote_hearing_url(str(url or ""), context=context)[0]
    except Exception:
        return False


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
        if (
            not line
            or TECHNICAL_VISIBLE_RE.search(line)
            or line.casefold().startswith("fonte documentale:")
        ):
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
        client = _extract_labeled_line(text, "Cliente", limit=90)
        if client:
            return client
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
    return any(
        token in text
        for token in (
            "posta certificata",
            "pec_audit",
            "comunicazione_cancelleria",
            "cancelleria_comunicazione",
            "provvedimento_da_esaminare",
            "sentenza_da_valutare_per_notifica",
            "ricevuta_accettazione_da_presidiare",
            "ricevuta di accettazione pec",
            "pec di accettazione",
            "ricevuta di consegna pec",
            "pec di consegna",
            "presidio pec",
            "da pec",
        )
    )


def _is_document_presidio_lex_text(*values: Any) -> bool:
    text = " ".join(str(value or "") for value in values).lower()
    return (
        "docpresidio:" in text
        or "fascicolo_documenti_audit" in text
        or "documento_fascicolo_lex" in text
        or "presidio documentale lex" in text
    )


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
            segmented = _extract_docpresidio_labeled(line, label, limit=limit)
            if segmented:
                return segmented
            return _clean_text(line.split(":", 1)[1], limit=limit).strip(" -:;.")
    # Il fallback compatto serve ai vecchi record salvati su una sola riga.
    # Sui testi multilinea potrebbe invece scambiare una label contenuta in
    # un'altra (per esempio ``Udienza`` dentro ``Verifica link udienza``).
    if "\n" not in str(text or "") and "\r" not in str(text or ""):
        return _extract_docpresidio_labeled(text, label, limit=limit)
    return ""


def _has_structured_pec_profile(text: str) -> bool:
    return bool(
        _extract_labeled_line(text, "Cliente", limit=120)
        and (
            _extract_labeled_line(text, "Evento", limit=180)
            or _extract_labeled_line(text, "Udienza", limit=120)
        )
    )


def _structured_detail_value(label: str, value: Any, *, limit: int = 220) -> str:
    cleaned = _visible_legal_text(value, limit=limit)
    if label.casefold() == "evento" and _is_pec_operational_text(cleaned):
        return ""
    return cleaned


def _pec_agenda_visible_notes(raw_notes: str, *, client: str = "", matter: str = "", court: str = "") -> str:
    lines: list[str] = []
    for label in ("Cliente", "Parte/soggetto", "Ufficio", "Giudice", "Evento", "Udienza"):
        value = _structured_detail_value(label, _extract_labeled_line(raw_notes, label, limit=220), limit=220)
        if value:
            _append_detail_line(lines, f"{label}: {value}", limit=260)
    if matter and "RG" not in " ".join(lines):
        _append_detail_line(lines, f"Fascicolo/RG: {matter}", limit=180)
    if court and "Ufficio:" not in " ".join(lines):
        _append_detail_line(lines, f"Ufficio: {court}", limit=180)
    if client and "Cliente:" not in " ".join(lines):
        _append_detail_line(lines, f"Cliente: {client}", limit=180)
    for label in ("Oggetto PEC", "Destinatario PEC", "Mittente PEC", "Possibile fascicolo da verificare"):
        value = _structured_detail_value(label, _extract_labeled_line(raw_notes, label, limit=260), limit=260)
        if value:
            _append_detail_line(lines, f"{label}: {value}", limit=300)
    activity = _extract_labeled_line(raw_notes, "Attività per l'avvocato", limit=520)
    if not activity and _is_sentence_decision_context(raw_notes):
        activity = (
            "esaminare la sentenza e valutare/preparare notifica, relata e prova; "
            "la comunicazione di cancelleria non prova la notifica dell'avvocato."
        )
    if not activity:
        activity = "verificare data, ora, fascicolo e provvedimento collegato; predisporre note, atti o comunicazioni se richiesti."
    _append_detail_line(
        lines,
        f"Attività per l'avvocato: {activity}",
        limit=540,
    )
    return _clean_text(" ".join(lines), limit=1000)


def _append_detail_line(lines: list[str], line: str, *, limit: int = 220) -> None:
    cleaned = _clean_text(line, limit=limit)
    if cleaned and cleaned.lower() not in " ".join(lines).lower():
        lines.append(cleaned)


def _normalise_for_matching(value: Any) -> str:
    text = str(value or "").casefold()
    return (
        text.replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )


def _document_presidio_cancel_reason_text(*values: Any) -> str:
    text = "\n".join(str(value or "") for value in values)
    if not _is_document_presidio_lex_text(text):
        return ""
    normalized = _normalise_for_matching(text)
    if not any(marker in normalized for marker in DOCUMENT_PRESIDIO_CANCEL_MARKERS):
        return ""
    match = re.search(r"\bMotivo:\s*([^\r\n.]+)", text, re.IGNORECASE)
    reason_code = _clean_text(match.group(1).strip(), limit=220) if match else ""
    normalized_reason = _normalise_for_matching(reason_code)
    for code, label in DOCUMENT_PRESIDIO_CANCEL_REASON_LABELS.items():
        if code in normalized_reason or code in normalized:
            return label
    if reason_code:
        return reason_code.replace("_", " ").strip()
    return "la fonte non contiene un adempimento dell'ufficio"


def _is_document_presidio_cancelled_text(*values: Any) -> bool:
    return bool(_document_presidio_cancel_reason_text(*values))


def _document_presidio_cancel_detail(*values: Any) -> str:
    reason = _document_presidio_cancel_reason_text(*values)
    if not reason:
        return ""
    return _clean_text(
        f"Presidio documentale annullato: {reason}. "
        "La fonte resta consultabile, ma non viene trattata come attività operativa.",
        limit=360,
    )


def _is_sentence_decision_context(value: str) -> bool:
    text = _normalise_for_matching(value)
    if any(
        token in text
        for token in (
            "sentenza_da_valutare_per_notifica",
            "sentenza_a_verbale",
            "judgment_to_notify",
            "strategic_notification_review",
        )
    ):
        return True
    if "sentenza" in text:
        return True
    return any(
        token in text
        for token in (
            "definitivamente decidendo",
            "sentenza a verbale",
            "resa ex art. 429",
            "art. 429 cpc",
            "art. 429 c.p.c",
            "429 cpc",
            "429 c.p.c",
        )
    )


def _is_court_registry_communication(value: str) -> bool:
    text = _normalise_for_matching(value)
    return "cancelleria" in text or "posta certificata: comunicazione" in text


def _has_operational_notification_context(title: str, notes: str) -> bool:
    title_text = _normalise_for_matching(title)
    text = _normalise_for_matching(f"{title}\n{notes}")
    if _is_legal_notification_text(title, notes):
        return True
    if "notifica sentenza" in text or "sentenza da valutare per la notifica" in text:
        return True
    if "notifica" in title_text or "notificazione" in title_text:
        return True
    if re.search(r"\b(?:ordina|dispone|autorizza|rinnova|assegna|invita)\b.{0,120}\bnotific", text):
        return True
    return False


def _agenda_origin_title(raw_title: str, legal_label: str, matter: str, notes: str) -> str:
    stripped = _strip_operational_prefix(raw_title)
    if _is_document_presidio_lex_text(raw_title, notes):
        if _is_document_presidio_cancelled_text(raw_title, notes):
            return "Presidio documentale annullato"
        if stripped.lower().startswith(("attività processuale da presidiare", "attivita processuale da presidiare")):
            return f"{legal_label} - {matter}" if matter else legal_label
        return _clean_text(stripped or legal_label, limit=180)
    if not _is_pec_operational_text(raw_title, notes):
        return _clean_text(stripped or legal_label, limit=180)
    text = f"{raw_title} {notes}".lower()
    if "ricevuta_accettazione_da_presidiare" in text:
        clean_receipt_title = _clean_text(stripped, limit=180)
        if clean_receipt_title and not clean_receipt_title.lower().startswith("presidio"):
            return clean_receipt_title
        base = "Ricevuta di accettazione PEC"
    elif _is_sentence_decision_context(text):
        base = "Sentenza da valutare per la notifica"
    elif "udienza" in text:
        base = "Udienza da comunicazione di cancelleria"
    elif _has_operational_notification_context(raw_title, notes):
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


def _extract_hearing_time(*values: Any) -> time | None:
    for value in values:
        match = PEC_HEARING_TIME_RE.search(str(value or ""))
        if match:
            return time(hour=int(match.group(1)), minute=int(match.group(2)))
    return None


def _legal_label(title: str, kind: str, notes: str = "") -> str:
    title_text = _normalise_for_matching(title)
    kind_text = _normalise_for_matching(kind)
    text = _normalise_for_matching(f"{title}\n{kind}\n{notes}")
    if _is_document_presidio_lex_text(title, notes):
        if _is_document_presidio_cancelled_text(title, notes):
            return "Presidio documentale annullato"
        if _is_sentence_decision_context(text):
            return "Sentenza da valutare per la notifica"
        if _has_operational_notification_context(title, notes):
            return "Notifica"
        doc_kind = _docpresidio_kind(title, notes)
        if doc_kind == "deposito_note" or "deposito note" in text or "note scritte" in text:
            return "Deposito note scritte"
        if doc_kind == "udienza":
            return "Udienza"
        if "deposito memoria" in text:
            return "Deposito memoria"
        if "deposito atto" in text:
            return "Deposito atto"
        if doc_kind == "termine":
            return "Provvedimento giudiziario da esaminare"
    if "ricevuta_accettazione_da_presidiare" in text:
        return "Ricevuta di accettazione PEC da presidiare"
    if _is_legal_notification_text(title, notes):
        return "Sentenza da valutare per la notifica"
    if _is_sentence_decision_context(text):
        return "Sentenza da valutare per la notifica"
    if "opposizione" in title_text and ("trattazione scritta" in title_text or "127-ter" in title_text):
        return "Opposizione alla trattazione scritta"
    if "rinvio" in text or "rinviata" in text or "differimento" in text or "differita" in text:
        return "Rinvio udienza"
    if "fissazione udienza" in text or "fissata udienza" in text or "fissata l'udienza" in text or ("fissazione" in text and "udienza" in text):
        return "Fissazione udienza"
    if "udienza" in title_text or kind_text == "udienza":
        return "Udienza"
    if (
        "deposito" in title_text
        and any(token in title_text for token in ("accett", "consegn", "esito positivo"))
    ) or (
        kind_text == "deposito"
        and any(token in text for token in ("accett", "consegn", "esito positivo"))
    ):
        return "Deposito accettato"
    if "deposito" in title_text or kind_text == "deposito":
        return "Deposito"
    if _has_operational_notification_context(title, notes):
        return "Notifica"
    if "provvedimento_da_esaminare" in text or "provvedimento giudiziario" in text:
        return "Provvedimento giudiziario da esaminare"
    if _is_court_registry_communication(text):
        return "Comunicazione di cancelleria da esaminare"
    if "pec_da_classificare" in text:
        return "PEC da classificare"
    if "pec" in text:
        return "PEC da esaminare"
    if "termine" in title_text or "scadenza" in title_text or "decorrenza" in title_text:
        return "Termine processuale da presidiare"
    if kind_text == "scadenza":
        return "Scadenza da presidiare"
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
    is_pec_operational = _is_pec_operational_text(original_title, raw_notes) or _has_structured_pec_profile(raw_notes)
    is_document_presidio = _is_document_presidio_lex_text(original_title, raw_notes)
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
    if is_pec_operational:
        for label in ("Oggetto PEC", "Destinatario PEC", "Mittente PEC", "Possibile fascicolo da verificare"):
            value = _structured_detail_value(label, _extract_labeled_line(raw_notes, label, limit=260), limit=260)
            if value:
                _append_detail_line(lines, f"{label}: {value}", limit=300)
        for label in ("Parte/soggetto", "Giudice", "Evento", "Udienza"):
            value = _structured_detail_value(label, _extract_labeled_line(raw_notes, label, limit=220), limit=220)
            if value:
                _append_detail_line(lines, f"{label}: {value}", limit=260)
        if not is_document_presidio:
            activity = _extract_labeled_line(raw_notes, "Attività per l'avvocato", limit=520)
            if not activity and _is_sentence_decision_context(f"{original_title}\n{raw_notes}\n{legal_label}"):
                activity = (
                    "esaminare la sentenza e valutare/preparare notifica, relata e prova; "
                    "la comunicazione di cancelleria non prova la notifica dell'avvocato."
                )
            if not activity:
                activity = "verificare data, ora, fascicolo e provvedimento collegato; predisporre note, atti o comunicazioni se richiesti."
            _append_detail_line(
                lines,
                f"Attività per l'avvocato: {activity}",
                limit=540,
            )
    if is_document_presidio:
        cancel_detail = _document_presidio_cancel_detail(original_title, raw_notes)
        if cancel_detail:
            _append_detail_line(lines, cancel_detail, limit=380)
        else:
            activity = _extract_labeled_line(raw_notes, "Attività per l'avvocato", limit=360)
            if not activity:
                if legal_label == "Sentenza da valutare per la notifica":
                    activity = (
                        "esaminare la sentenza e valutare/preparare notifica, relata e prova; "
                        "la comunicazione di cancelleria non prova la notifica dell'avvocato."
                    )
                elif legal_label == "Udienza":
                    activity = "verificare data, ora, fascicolo, modalità di udienza e provvedimento collegato."
                elif legal_label in {"Deposito note scritte", "Deposito memoria", "Deposito atto"}:
                    activity = "preparare il deposito indicato dal provvedimento e controllare la fonte prima della scadenza."
                elif legal_label == "Notifica":
                    activity = "verificare destinatari, relata e prova della notifica sulla fonte collegata."
                else:
                    activity = "leggere la fonte collegata e confermare se contiene un ordine processuale espresso da lavorare."
            _append_detail_line(lines, f"Attività per l'avvocato: {activity}", limit=380)
        party_subject = _extract_docpresidio_labeled(raw_notes, "Parte/soggetto", limit=180)
        if party_subject and party_subject.lower() not in " ".join(lines).lower():
            lines.append(f"Parte/soggetto: {party_subject}")
        for label in ("Modalità udienza", "Orario udienza"):
            value = _extract_labeled_line(raw_notes, label, limit=180)
            if value:
                _append_detail_line(lines, f"{label}: {value}", limit=220)
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
    notes = "" if is_pec_operational else _visible_legal_text(row.get("notes"), limit=220)
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
    matter = _clean_text(row.get("matter"), limit=120)
    if not matter and not row.get("disableMatterInference"):
        matter = _extract_rg(raw_title, raw_notes, original_title, notes)
    client = _clean_text(row.get("client"), limit=120) or _extract_party(raw_notes, notes, raw_title, original_title)
    label_context = "\n".join(
        part
        for part in (
            raw_notes or notes,
            str(row.get("sourceEventType") or ""),
            str(row.get("sourceEventAt") or ""),
        )
        if str(part or "").strip()
    )
    label = _legal_label(raw_title, kind, label_context)
    origin_title = _agenda_origin_title(raw_title, label, matter, label_context)
    if _is_pec_operational_text(raw_title, raw_notes) or _has_structured_pec_profile(raw_notes):
        structured_notes = _pec_agenda_visible_notes(
            raw_notes,
            client=client,
            matter=matter,
            court=_clean_text(row.get("court"), limit=120),
        )
        if structured_notes:
            notes = structured_notes
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
    remote_candidate = _remote_hearing_url(
        row.get("remoteHearingUrl"),
        _extract_labeled_line(raw_notes, "Link udienza audiovisiva", limit=900),
        _extract_labeled_line(raw_notes, "Collegamento remoto", limit=900),
    )
    remote_verified = bool(row.get("remoteHearingVerified")) or (
        "Verifica link udienza: identico alla fonte letta" in raw_notes
    )
    remote_url = (
        remote_candidate
        if remote_verified
        and _is_remote_hearing_ui_url(
            remote_candidate,
            str(row.get("remoteHearingSource") or raw_notes),
        )
        else ""
    )
    remote_mode = _clean_text(
        row.get("remoteHearingMode")
        or _extract_labeled_line(raw_notes, "Modalità udienza", limit=120)
        or ("Da remoto" if remote_candidate else ""),
        limit=120,
    )
    status_value = _enum_value(row.get("status")).upper()
    row["remoteHearingUrl"] = remote_url
    row["remoteHearingVerified"] = bool(remote_url and remote_verified)
    row["remoteHearingDetected"] = bool(
        row.get("remoteHearingDetected")
        or remote_candidate
        or row.get("remoteHearingPdfRequired")
    )
    row["remoteHearingMode"] = remote_mode
    row["completed"] = status_value in {"COMPLETATO", "COMPLETATA", "ESEGUITO", "ESEGUITA", "FATTO", "CHIUSO", "CHIUSA"}
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


def _agenda_event(item: Any, *, pec_profile: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    # L'Agenda operativa non deve riproporre appuntamenti già chiusi o
    # annullati: restano nello storico del repository, ma non sono attività
    # da svolgere né possono riattivare un avviso derivato dalla PEC.
    if _enum_value(getattr(item, "stato", "")) in {"COMPLETATO", "ANNULLATO"}:
        return None
    if is_legacy_pec_agenda_item(item):
        return None
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
    matter_id = str(getattr(item, "id_fascicolo", "") or "")
    source_payload = _source_evidence(
        notes,
        matter_id=matter_id,
        external_source_url=str(getattr(item, "external_source_url", "") or ""),
        external_uid=str(getattr(item, "external_uid", "") or ""),
        source_name=str(getattr(item, "remote_hearing_source", "") or ""),
        indexed_source_name=pec_profile_source_name(pec_profile),
    )
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
        "matterId": matter_id,
        "client": str(getattr(item, "cliente", "") or ""),
        "clientId": str(getattr(item, "id_cliente", "") or ""),
        "owner": str(getattr(item, "avvocato", "") or "Studio"),
        "source": "agenda",
        "syncStatus": _sync_status(item),
        "notes": notes,
        **source_payload,
        "hearingMode": str(getattr(item, "hearing_mode", "") or ""),
        "hearingTime": str(getattr(item, "hearing_time", "") or ""),
        "remoteHearingDetected": bool(getattr(item, "remote_hearing_detected", False)),
        "remoteHearingUrl": str(getattr(item, "remote_hearing_url", "") or ""),
        "remoteHearingMode": str(getattr(item, "remote_hearing_mode", "") or ""),
        "remoteHearingSource": str(getattr(item, "remote_hearing_source", "") or ""),
        "remoteHearingVerified": bool(getattr(item, "remote_hearing_verified", False)),
        "remoteHearingPlatform": _remote_hearing_platform_for_ui(item),
        "remoteHearingMeetingId": str(getattr(item, "remote_hearing_meeting_id", "") or ""),
        "remoteHearingPasscode": str(getattr(item, "remote_hearing_passcode", "") or ""),
        "remoteHearingAccessInfo": str(getattr(item, "remote_hearing_access_info", "") or ""),
        "remoteHearingPdfRequired": bool(getattr(item, "remote_hearing_pdf_required", False)),
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


def _deadline_in_range(item: Any, start: date, end: date) -> bool:
    calendar_date = getattr(item, "data_calendario_obj", None)
    if isinstance(calendar_date, date):
        return start <= calendar_date <= end
    raw_date = str(
        getattr(item, "data_scadenza", "")
        or getattr(item, "legal_due_at", "")
        or ""
    ).strip()
    try:
        parsed = date.fromisoformat(raw_date[:10])
    except ValueError:
        return False
    return start <= parsed <= end


def _control_tower_agenda_notes(source: dict[str, Any]) -> str:
    lines: list[str] = []
    subject = _clean_text(source.get("subject"), limit=220)
    if subject:
        lines.append(f"Oggetto PEC: {subject}.")
    recipient = _clean_text(source.get("recipient"), limit=160)
    if recipient:
        lines.append(f"Destinatario PEC: {recipient}.")
    sender = _clean_text(source.get("sender"), limit=160)
    if sender:
        lines.append(f"Mittente PEC: {sender}.")
    suggested = _clean_text(source.get("fascicoloSuggestedLabel"), limit=140)
    if suggested:
        lines.append(f"Possibile fascicolo da verificare: {suggested}.")
    if str(source.get("legalEventType") or "") == "ricevuta_accettazione_da_presidiare":
        lines.append(
            "Attività per l'avvocato: verificare la ricevuta di consegna collegata, "
            "controllare se il fascicolo proposto è corretto e collegare il cliente solo quando il match è certo."
        )
    detail = _clean_text(source.get("detailDescription"), limit=760)
    if detail:
        lines.append(detail)
    return "\n".join(dict.fromkeys(line for line in lines if line))


def _deadline_event(
    item: Any,
    fascicolo: Any = None,
    *,
    control_tower_source: dict[str, Any] | None = None,
    pec_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    # Come per gli appuntamenti, le scadenze annullate o completate sono
    # consultabili nello storico, non nell'Agenda delle attività aperte.
    if _enum_value(getattr(item, "stato", "")) in {"COMPLETATO", "ANNULLATO"}:
        return None
    if is_legacy_pec_deadline(item):
        return None
    calendar_date = getattr(item, "data_calendario_obj", None)
    if isinstance(calendar_date, date):
        due_date = calendar_date
    else:
        due = str(getattr(item, "data_scadenza", "") or getattr(item, "legal_due_at", "") or "").strip()
        if not due:
            return None
        try:
            due_date = date.fromisoformat(due[:10])
        except ValueError:
            return None
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
    source_notes = notes
    if control_tower_source:
        control_notes = _control_tower_agenda_notes(control_tower_source)
        if control_notes:
            notes = control_notes
    hearing_time = None
    if kind == "UDIENZA":
        hearing_time = _extract_hearing_time(
            getattr(item, "hearing_time", ""),
            getattr(item, "remote_hearing_time", ""),
            _extract_labeled_line(notes, "Orario udienza", limit=80),
            _extract_labeled_line(notes, "Orario collegamento", limit=80),
        )
    start = datetime.combine(due_date, hearing_time or time(hour=9))
    end = start + timedelta(minutes=45)
    time_label = start.strftime("%H:%M") if kind == "UDIENZA" else "Entro giornata"
    duration_label = "45 min" if kind == "UDIENZA" else "Scadenza"
    fascicolo_id = str(getattr(item, "id_fascicolo", "") or "")
    source_event_type = str(getattr(item, "source_event_type", "") or "").strip()
    source_event_at = str(getattr(item, "source_event_at", "") or "").strip()
    matter = ""
    client = ""
    client_id = str(getattr(item, "id_cliente", "") or "")
    court = ""
    if fascicolo is not None:
        matter = _clean_text(getattr(fascicolo, "rg_completo", ""), limit=120) or _clean_text(getattr(fascicolo, "numero", ""), limit=120)
        client = _clean_text(getattr(fascicolo, "nome_cliente", ""), limit=120)
        client_id = client_id or str(getattr(fascicolo, "id_cliente", "") or "")
        court = _clean_text(getattr(fascicolo, "tribunale", ""), limit=120)
    source_context = "\n".join(dict.fromkeys(part for part in (source_notes, notes) if part))
    source_payload = _source_evidence(
        source_context,
        matter_id=fascicolo_id,
        source_name=str(
            getattr(item, "remote_hearing_source", "")
            or getattr(item, "hearing_mode_source", "")
            or ""
        ),
        indexed_source_name=pec_profile_source_name(pec_profile),
    )
    if (
        not source_payload.get("sourceHref")
        and control_tower_source
        and control_tower_source.get("sourceHref")
    ):
        source_payload = {
            "sourceHref": str(control_tower_source.get("sourceHref") or ""),
            "sourceLabel": str(control_tower_source.get("sourceLabel") or "PEC originale"),
            "sourceKind": str(control_tower_source.get("sourceKind") or "pec"),
            "sourceVerified": bool(control_tower_source.get("sourceVerified")),
        }
    title = str(getattr(item, "titolo", "") or "Scadenza")
    if control_tower_source:
        title = _clean_text(control_tower_source.get("displayTitle"), limit=180) or title
        source_event_type = str(control_tower_source.get("legalEventType") or source_event_type)
    return _decorate_event({
        "id": f"scadenza-{item_id}" if item_id else f"scadenza-{due_date.isoformat()}",
        "title": title,
        "kind": kind,
        "priority": _enum_value(getattr(item, "priorita", "MEDIA")),
        "status": _enum_value(getattr(item, "stato", "APERTO")),
        "start": start.isoformat(timespec="minutes"),
        "end": end.isoformat(timespec="minutes"),
        "timeLabel": time_label,
        "durationLabel": duration_label,
        "location": "",
        "court": court,
        "matter": matter,
        "matterId": fascicolo_id,
        "client": client,
        "clientId": client_id,
        "owner": str(getattr(item, "id_utente_responsabile", "") or "Studio"),
        "source": "scadenziario",
        "syncStatus": "locale",
        "notes": notes,
        "disableMatterInference": bool(control_tower_source and not control_tower_source.get("fascicoloId")),
        "sourceEventType": source_event_type,
        "sourceEventAt": source_event_at,
        **source_payload,
        "remoteHearingUrl": str(getattr(item, "remote_hearing_url", "") or ""),
        "remoteHearingMode": str(getattr(item, "remote_hearing_mode", "") or ""),
        "remoteHearingDetected": bool(getattr(item, "remote_hearing_detected", False)),
        "remoteHearingSource": str(getattr(item, "remote_hearing_source", "") or ""),
        "remoteHearingVerified": bool(getattr(item, "remote_hearing_verified", False)),
        "remoteHearingPlatform": _remote_hearing_platform_for_ui(item),
        "remoteHearingMeetingId": str(getattr(item, "remote_hearing_meeting_id", "") or ""),
        "remoteHearingPasscode": str(getattr(item, "remote_hearing_passcode", "") or ""),
        "remoteHearingAccessInfo": str(getattr(item, "remote_hearing_access_info", "") or ""),
        "remoteHearingPdfRequired": bool(getattr(item, "remote_hearing_pdf_required", False)),
        "href": f"/scadenziario/{item_id}" if item_id else "/scadenziario",
    })


def _normal_context_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _unique_agenda_context(candidates: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    rows = [
        row
        for row in candidates
        if any(_clean_text(row.get(key), limit=120) for key in ("matter", "client", "court"))
    ]
    if not rows:
        return None
    for key in ("matter", "client"):
        values = {_normal_context_key(row.get(key)) for row in rows if _normal_context_key(row.get(key))}
        if len(values) > 1:
            return None
    return max(
        rows,
        key=lambda row: sum(bool(_clean_text(row.get(key), limit=120)) for key in ("matter", "client", "court", "matterId", "clientId")),
    )


def _is_generic_portal_hearing(event: dict[str, Any]) -> bool:
    if str(event.get("legalLabel") or "").casefold() != "udienza":
        return False
    text = " ".join(str(event.get(key) or "") for key in ("title", "originTitle", "technicalNotes", "notes")).lower()
    return "udienza da portale" in text or "sincronizzazione portale" in text


def _agenda_context_for_deadline(
    event: dict[str, Any],
    agenda_contexts: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    rows = list(agenda_contexts)
    matter_id = _clean_text(event.get("matterId"), limit=120)
    if matter_id:
        exact_id = _unique_agenda_context(
            row for row in rows if _clean_text(row.get("matterId"), limit=120) == matter_id
        )
        if exact_id is not None:
            return exact_id

    rg_key = _normal_context_key(_extract_rg(event.get("matter"), event.get("title"), event.get("technicalNotes"), event.get("notes")))
    if rg_key:
        exact_rg = _unique_agenda_context(
            row
            for row in rows
            if _normal_context_key(_extract_rg(row.get("matter"), row.get("title"), row.get("technicalNotes"), row.get("notes"))) == rg_key
        )
        if exact_rg is not None:
            return exact_rg

    if _is_generic_portal_hearing(event):
        event_date = str(event.get("start") or "")[:10]
        return _unique_agenda_context(
            row
            for row in rows
            if str(row.get("start") or "")[:10] == event_date
            and str(row.get("legalLabel") or "").casefold() in {"udienza", "fissazione udienza", "rinvio udienza"}
        )
    return None


def _enrich_deadline_from_agenda(
    event: dict[str, Any],
    agenda_contexts: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    context = _agenda_context_for_deadline(event, agenda_contexts)
    if context is None:
        return event
    enriched = dict(event)
    enriched["agendaContextMatched"] = True
    for key in ("matter", "matterId", "client", "clientId", "court", "location", "remoteHearingUrl", "remoteHearingMode"):
        if not _clean_text(enriched.get(key), limit=160) and _clean_text(context.get(key), limit=160):
            enriched[key] = context.get(key)
    if _is_generic_portal_hearing(event) and str(event.get("start") or "")[:10] == str(context.get("start") or "")[:10]:
        for key in ("start", "end", "timeLabel", "durationLabel"):
            enriched[key] = context.get(key) or enriched.get(key)
    enriched["notes"] = str(event.get("technicalNotes") or event.get("notes") or "")
    enriched["subtitle"] = ""
    return _decorate_event(enriched)


def build_agenda_display_contexts(items: Iterable[Any]) -> list[dict[str, Any]]:
    """Normalizza una sola volta gli appuntamenti usati come contesto visibile."""

    contexts: list[dict[str, Any]] = []
    for item in items:
        event = _agenda_event(item)
        if event:
            contexts.append(event)
    return contexts


def build_deadline_display_event(
    item: Any,
    *,
    fascicolo: Any = None,
    agenda_contexts: Iterable[dict[str, Any]] = (),
    control_tower_source: dict[str, Any] | None = None,
    pec_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Applica alla scadenza la stessa lettura legale usata dall'Agenda."""

    event = _deadline_event(
        item,
        fascicolo,
        control_tower_source=control_tower_source,
        pec_profile=pec_profile,
    )
    if event is None:
        return None
    return _enrich_deadline_from_agenda(event, agenda_contexts)


def _deadline_context_text(item: Any) -> str:
    return "\n".join(
        str(getattr(item, key, "") or "")
        for key in ("titolo", "descrizione", "note", "id_fascicolo")
    )


def _appointment_date(item: Any) -> str:
    parsed = getattr(item, "data_ora_dt", None)
    if not isinstance(parsed, datetime):
        try:
            parsed = datetime.fromisoformat(str(getattr(item, "data_ora", "") or ""))
        except ValueError:
            return ""
    return parsed.date().isoformat()


def _find_fascicolo_by_rg(fascicoli_repo: Any, rg_label: str) -> Any:
    rg_key = _normal_context_key(rg_label)
    if not rg_key or not hasattr(fascicoli_repo, "cerca"):
        return None
    search_value = re.sub(r"\D.*$", "", str(rg_label).removeprefix("RG ").strip())
    if not search_value:
        return None
    try:
        candidates = list(fascicoli_repo.cerca(search_value, archiviati=True))
    except Exception:
        return None
    exact = [
        candidate
        for candidate in candidates
        if _normal_context_key(_extract_rg(getattr(candidate, "rg_completo", ""), getattr(candidate, "numero", ""))) == rg_key
    ]
    return exact[0] if len(exact) == 1 else None


def _enrich_agenda_event_from_fascicolo(event: dict[str, Any], fascicolo: Any) -> dict[str, Any]:
    if fascicolo is None:
        return event
    enriched = dict(event)
    values = {
        "matter": _clean_text(getattr(fascicolo, "rg_completo", ""), limit=120)
        or _clean_text(getattr(fascicolo, "numero", ""), limit=120),
        "matterId": str(getattr(fascicolo, "id", "") or ""),
        "client": _clean_text(getattr(fascicolo, "nome_cliente", ""), limit=120),
        "clientId": str(getattr(fascicolo, "id_cliente", "") or ""),
        "court": _clean_text(getattr(fascicolo, "tribunale", ""), limit=120),
    }
    changed = False
    for key, value in values.items():
        if value and not _clean_text(enriched.get(key), limit=160):
            enriched[key] = value
            changed = True
    if not changed:
        return event
    enriched["notes"] = str(event.get("technicalNotes") or event.get("notes") or "")
    enriched["subtitle"] = ""
    return _decorate_event(enriched)


def build_react_agenda_payload(
    agenda_loader: Callable[[], Any],
    deadlines_loader: Callable[[], Any],
    fascicoli_loader: Callable[[], Any] | None = None,
    from_value: Any = "",
    to_value: Any = "",
    selected_id: str = "",
    pec_audit_db: str = "",
    tenant_id: str = "default",
) -> dict[str, Any]:
    """Return agenda and deadline rows normalized for the React shell."""

    start, end = _date_range(from_value, to_value)
    agenda_repo = agenda_loader()
    deadlines_repo = deadlines_loader()
    fascicoli_repo = fascicoli_loader() if fascicoli_loader is not None else None
    fascicoli_cache: dict[str, Any] = {}
    all_appointments = _safe_items(lambda: agenda_repo.tutti())
    appointments = [
        item
        for item in all_appointments
        if _appointment_in_range(item, start, end)
    ]
    all_deadlines = _safe_items(lambda: deadlines_repo.tutte(solo_aperte=False))
    deadlines = [item for item in all_deadlines if _deadline_in_range(item, start, end)]
    deadline_rg_keys = {
        _normal_context_key(rg)
        for item in deadlines
        if (rg := _extract_rg(_deadline_context_text(item)))
    }
    deadline_hearing_dates = {
        str(getattr(item, "data_scadenza", "") or "")[:10]
        for item in deadlines
        if _enum_value(getattr(item, "tipo", "")) == "UDIENZA"
        and str(getattr(item, "data_scadenza", "") or "")[:10]
    }
    visible_appointment_ids = {str(getattr(item, "id", "") or "") for item in appointments}
    context_appointments: list[Any] = []
    for item in all_appointments:
        if str(getattr(item, "id", "") or "") in visible_appointment_ids:
            continue
        rg_key = _normal_context_key(
            _extract_rg(
                getattr(item, "procedimento", ""),
                getattr(item, "titolo", ""),
                getattr(item, "descrizione", ""),
                getattr(item, "note", ""),
            )
        )
        same_hearing_day = (
            _enum_value(getattr(item, "tipo", "")) == "UDIENZA"
            and _appointment_date(item) in deadline_hearing_dates
        )
        if rg_key in deadline_rg_keys or same_hearing_day:
            context_appointments.append(item)

    selected = None
    if selected_id:
        try:
            selected = agenda_repo.get(selected_id)
        except Exception:
            selected = None
    control_tower_sources = latest_control_tower_sources(
        deadlines,
        pec_audit_db=pec_audit_db,
        tenant_id=tenant_id,
    )
    pec_profiles = latest_pec_profiles(
        [*appointments, *context_appointments, *deadlines, *([selected] if selected is not None else [])],
        pec_audit_db=pec_audit_db,
        tenant_id=tenant_id,
    )

    events: list[dict[str, Any]] = []
    for item in appointments:
        event = _agenda_event(item, pec_profile=pec_profiles.get(pec_audit_message_id(item)))
        if event:
            if fascicoli_repo is not None:
                matter_id = _clean_text(event.get("matterId"), limit=120)
                rg_label = _extract_rg(
                    event.get("matter"),
                    event.get("title"),
                    event.get("technicalNotes"),
                    event.get("notes"),
                )
                cache_key = f"id:{matter_id}" if matter_id else f"rg:{_normal_context_key(rg_label)}"
                fascicolo = None
                if matter_id or rg_label:
                    if cache_key not in fascicoli_cache:
                        try:
                            fascicolo = fascicoli_repo.get(matter_id) if matter_id else None
                        except Exception:
                            fascicolo = None
                        if fascicolo is None and rg_label:
                            fascicolo = _find_fascicolo_by_rg(fascicoli_repo, rg_label)
                        fascicoli_cache[cache_key] = fascicolo
                    else:
                        fascicolo = fascicoli_cache[cache_key]
                event = _enrich_agenda_event_from_fascicolo(event, fascicolo)
            events.append(event)
    agenda_contexts = list(events)
    for item in context_appointments:
        context_event = _agenda_event(item, pec_profile=pec_profiles.get(pec_audit_message_id(item)))
        if context_event:
            agenda_contexts.append(context_event)
    if selected is not None:
        event = _agenda_event(selected, pec_profile=pec_profiles.get(pec_audit_message_id(selected)))
        if event and not any(str(row.get("id") or "") == str(event.get("id") or "") for row in events):
            events.append(event)
    for item in deadlines:
        event = _deadline_event(
            item,
            control_tower_source=control_tower_sources.get(control_tower_source_key(item)),
            pec_profile=pec_profiles.get(pec_audit_message_id(item)),
        )
        if event:
            event_date = _parse_date(event["start"], start)
            if start <= event_date <= end:
                fascicolo_id = str(getattr(item, "id_fascicolo", "") or "").strip()
                rg_label = _extract_rg(_deadline_context_text(item))
                fascicolo_cache_key = f"id:{fascicolo_id}" if fascicolo_id else f"rg:{_normal_context_key(rg_label)}"
                if fascicoli_repo is not None and (fascicolo_id or rg_label):
                    if fascicolo_cache_key not in fascicoli_cache:
                        try:
                            fascicolo = fascicoli_repo.get(fascicolo_id) if fascicolo_id else None
                        except Exception:
                            fascicolo = None
                        if fascicolo is None and rg_label:
                            fascicolo = _find_fascicolo_by_rg(fascicoli_repo, rg_label)
                        fascicoli_cache[fascicolo_cache_key] = fascicolo
                    fascicolo = fascicoli_cache[fascicolo_cache_key]
                    if fascicolo is not None:
                        event = _deadline_event(
                            item,
                            fascicolo,
                            control_tower_source=control_tower_sources.get(control_tower_source_key(item)),
                            pec_profile=pec_profiles.get(pec_audit_message_id(item)),
                        ) or event
                event = _enrich_deadline_from_agenda(event, agenda_contexts)
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
            "sources": ["agenda", "scadenziario"] + (["fascicoli"] if fascicoli_loader is not None else []),
        },
    }
