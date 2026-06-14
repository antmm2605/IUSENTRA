"""
pct/ical.py — Generazione feed iCalendar (RFC 5545).

Nessuna dipendenza esterna — implementazione pura Python.
Compatibile con Google Calendar, Apple Calendar, Outlook.

Feed disponibili:
  agenda_to_ical()           — appuntamenti (VEVENT con ora)
  scadenze_to_ical()         — scadenze (VEVENT tutto il giorno + multi-VALARM)
  agenda_scadenze_to_ical()  — feed combinato (agenda + scadenze)
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

_ROME = ZoneInfo("Europe/Rome")
TECHNICAL_VISIBLE_RE = re.compile(
    r"\b(?:PEC_AUDIT|pipeline|audit|audit-grade|source_event|profile_id|payload|runtime|backend|frontend|legacy|json_api|external_uid|external_provider|worker|job|provider|webhook|endpoint)\b",
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


# ──────────────────────────────────────────── helpers RFC 5545

def _escape(s: str) -> str:
    """Escape caratteri speciali per valori iCal."""
    return (
        s.replace("\\", "\\\\")
         .replace(";", "\\;")
         .replace(",", "\\,")
         .replace("\n", "\\n")
    )


def _short_text(value: object, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _visible_calendar_text(value: object, limit: int = 500) -> str:
    parts: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = _short_text(raw_line, limit=max(limit, 220))
        if not line:
            continue
        line = re.sub(r"\bPEC_AUDIT:[A-Za-z0-9_.:-]+", "", line).strip()
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
        line = OPERATIONAL_PREFIX_RE.sub("", line).strip(" -:")
        if line:
            parts.append(line)
    return _short_text(" ".join(parts), limit)


def _prefixed_summary(prefix: str, title: str) -> str:
    clean_prefix = str(prefix or "").strip().rstrip(":")
    clean_title = str(title or "").strip()
    if not clean_title:
        return clean_prefix
    if clean_title.lower().startswith(clean_prefix.lower()):
        return clean_title
    return f"{clean_prefix}: {clean_title}"


def _sequence(last_modified: Optional[datetime]) -> int:
    """Restituisce il SEQUENCE come Unix timestamp di last_modified (o 0).

    SEQUENCE è obbligatorio per la sincronizzazione con Google Calendar:
    ad ogni modifica il valore cresce → il client rileva l'aggiornamento.
    Usare il timestamp Unix di last_modified è conforme a RFC 5545 e
    compatibile con Google Calendar, Apple Calendar, Outlook.
    """
    if last_modified is None:
        return 0
    dt = last_modified
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_ROME)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return int((dt.astimezone(timezone.utc) - epoch).total_seconds())


def _dt(dt: datetime) -> str:
    """Datetime → stringa UTC iCal (YYYYMMDDTHHMMSSZ).

    I datetime senza fuso orario (naive) vengono trattati come Europe/Rome
    e convertiti in UTC prima dell'emissione. Questo evita che Google Calendar
    interpreti gli orari come UTC (causando uno sfasamento di 1-2 ore).
    """
    if dt.tzinfo is None:
        # Naive datetime: assume Europe/Rome (fuso orario italiano)
        dt = dt.replace(tzinfo=_ROME)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _date_val(d: date) -> str:
    """Date → stringa iCal per eventi tutto il giorno (YYYYMMDD)."""
    return d.strftime("%Y%m%d")


def _fold(line: str) -> str:
    """RFC 5545 line folding: max 75 ottetti, continua con CRLF + spazio."""
    result = []
    while len(line.encode("utf-8")) > 75:
        chunk = line[:75]
        while len(chunk.encode("utf-8")) > 75:
            chunk = chunk[:-1]
        result.append(chunk)
        line = " " + line[len(chunk):]
    result.append(line)
    return "\r\n".join(result)


# ──────────────────────────────────────────── ICalBuilder

class ICalBuilder:
    """Costruisce un file .ics RFC 5545."""

    def __init__(self, cal_name: str = "Agenda", prod_id: str = "-//IUSENTRA//IT"):
        self._cal_name = cal_name
        self._prod_id  = prod_id
        self._events: List[str] = []

    def aggiungi_evento(
        self,
        uid:           str,
        summary:       str,
        dtstart:       datetime,
        dtend:         Optional[datetime] = None,
        description:   str = "",
        location:      str = "",
        url:           str = "",
        allarme_min:   Optional[int] = 60,      # singolo allarme (retrocompatibilità)
        allarmi_min:   Optional[List[int]] = None,  # lista allarmi, sovrascrive allarme_min
        last_modified: Optional[datetime] = None,
    ) -> "ICalBuilder":
        if dtend is None:
            dtend = dtstart + timedelta(hours=1)

        dtstamp = _dt(datetime.now(timezone.utc))

        lines = [
            "BEGIN:VEVENT",
            f"UID:{_escape(uid)}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{_dt(dtstart)}",
            f"DTEND:{_dt(dtend)}",
            "STATUS:CONFIRMED",
            f"SEQUENCE:{_sequence(last_modified)}",
            "TRANSP:OPAQUE",
        ]
        if last_modified:
            lines.append(f"LAST-MODIFIED:{_dt(last_modified)}")
        lines.append(f"SUMMARY:{_escape(summary)}")
        if description:
            lines.append(f"DESCRIPTION:{_escape(description)}")
        if location:
            lines.append(f"LOCATION:{_escape(location)}")
        if url:
            lines.append(f"URL:{url}")

        # VALARM — notifiche native del calendario
        allarmi = allarmi_min if allarmi_min is not None else (
            [allarme_min] if allarme_min is not None else []
        )
        for am in allarmi:
            if am >= 1440:  # ≥ 1 giorno → usa giorni
                trigger = f"-P{am // 1440}D"
            elif am >= 60:  # ≥ 1 ora
                trigger = f"-PT{am}M"
            else:
                trigger = f"-PT{am}M"
            lines += [
                "BEGIN:VALARM",
                f"TRIGGER:{trigger}",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape(summary)}",
                "END:VALARM",
            ]

        lines.append("END:VEVENT")
        self._events.append("\r\n".join(_fold(l) for l in lines))
        return self

    def aggiungi_evento_giornata(
        self,
        uid:           str,
        summary:       str,
        start_date:    date,
        description:   str = "",
        url:           str = "",
        allarmi_min:   Optional[List[int]] = None,
        last_modified: Optional[datetime] = None,
    ) -> "ICalBuilder":
        """Aggiunge un evento tutto il giorno (DATE, senza ora)."""
        end_date = start_date + timedelta(days=1)
        dtstamp  = _dt(datetime.now(timezone.utc))

        lines = [
            "BEGIN:VEVENT",
            f"UID:{_escape(uid)}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;VALUE=DATE:{_date_val(start_date)}",
            f"DTEND;VALUE=DATE:{_date_val(end_date)}",
            "STATUS:CONFIRMED",
            f"SEQUENCE:{_sequence(last_modified)}",
            "TRANSP:TRANSPARENT",
        ]
        if last_modified:
            lines.append(f"LAST-MODIFIED:{_dt(last_modified)}")
        lines.append(f"SUMMARY:{_escape(summary)}")
        if description:
            lines.append(f"DESCRIPTION:{_escape(description)}")
        if url:
            lines.append(f"URL:{url}")

        for am in (allarmi_min or []):
            if am >= 1440:
                trigger = f"-P{am // 1440}D"
            else:
                trigger = f"-PT{am}M"
            lines += [
                "BEGIN:VALARM",
                f"TRIGGER:{trigger}",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape(summary)}",
                "END:VALARM",
            ]

        lines.append("END:VEVENT")
        self._events.append("\r\n".join(_fold(l) for l in lines))
        return self

    def build(self) -> str:
        header = "\r\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:{self._prod_id}",
            "CALSCALE:GREGORIAN",
            f"X-WR-CALNAME:{_escape(self._cal_name)}",
            "X-WR-TIMEZONE:Europe/Rome",
            "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
            "X-PUBLISHED-TTL:PT1H",
        ])
        if self._events:
            return header + "\r\n" + "\r\n".join(self._events) + "\r\nEND:VCALENDAR\r\n"
        return header + "\r\nEND:VCALENDAR\r\n"


# ──────────────────────────────────────────── funzioni pubbliche

def agenda_to_ical(appuntamenti, studio_nome: str = "IUSENTRA",
                   base_url: str = "") -> str:
    """
    Converte la lista di Appuntamento in un feed iCal.
    Usa data_ora_dt (property datetime) e reminder_minuti per l'allarme.
    """
    cal = ICalBuilder(cal_name=f"Agenda — {studio_nome}")
    for a in appuntamenti:
        # Costruzione descrizione
        desc_parts = []
        note = _visible_calendar_text(getattr(a, "note", "") or "", 700)
        if note:
            desc_parts.append(note)
        if getattr(a, "tipo", None):
            desc_parts.append(f"Tipo: {a.tipo.value}")
        if getattr(a, "procedimento", ""):
            desc_parts.append(f"Procedimento: {a.procedimento}")
        if getattr(a, "avvocato", ""):
            desc_parts.append(f"Avv.: {a.avvocato}")

        # Datetime dell'evento (usa data_ora_dt se disponibile)
        dt_start = getattr(a, "data_ora_dt", None) or a.data_ora
        if isinstance(dt_start, str):
            try:
                dt_start = datetime.fromisoformat(dt_start)
            except Exception:
                continue  # salta eventi con data non valida

        durata = getattr(a, "durata_minuti", 60) or 60
        dt_end = dt_start + timedelta(minutes=durata)

        # Allarme — usa reminder_minuti del singolo appuntamento
        reminder = getattr(a, "reminder_minuti", 60)

        # last_modified
        mod = getattr(a, "modificato_il", None)
        last_mod = None
        if mod:
            try:
                last_mod = datetime.fromisoformat(mod)
            except Exception:
                pass

        cal.aggiungi_evento(
            uid=f"{a.id}@pct-agenda",
            summary=_visible_calendar_text(getattr(a, "titolo", ""), 140) or "Appuntamento",
            dtstart=dt_start,
            dtend=dt_end,
            location=getattr(a, "luogo", "") or "",
            description="\n".join(desc_parts),
            url=f"{base_url}/agenda/{a.id}" if base_url else "",
            allarme_min=reminder,
            last_modified=last_mod,
        )
    return cal.build()


def scadenze_to_ical(scadenze, studio_nome: str = "IUSENTRA") -> str:
    """
    Converte le scadenze in un feed iCal (eventi tutto il giorno).
    Le scadenze perentorie ricevono allarmi multipli (7gg, 3gg, 1gg, 60min).
    """
    cal = ICalBuilder(cal_name=f"Scadenze — {studio_nome}")
    for s in scadenze:
        # data_scadenza_obj è property che restituisce date
        d = getattr(s, "data_scadenza_obj", None)
        if d is None:
            # fallback: prova parsing diretto
            raw = getattr(s, "data_scadenza", "")
            if not raw:
                continue
            try:
                d = date.fromisoformat(raw)
            except Exception:
                continue

        desc_parts = [_visible_calendar_text(getattr(s, "descrizione", "") or "", 700)]
        perentorio = getattr(s, "perentorio", False)
        if perentorio:
            desc_parts.append("Termine perentorio: controllare il deposito entro la data indicata.")

        # Allarmi: perentoria → 7gg + 3gg + 1gg + 60min; normale → 1gg + 60min
        if perentorio:
            allarmi = [7 * 1440, 3 * 1440, 1440, 60]
        else:
            giorni_preavviso = getattr(s, "giorni_preavviso", [7, 3, 1]) or [1]
            allarmi = [g * 1440 for g in giorni_preavviso] + [60]

        # last_modified
        mod = getattr(s, "modificato_il", None)
        last_mod = None
        if mod:
            try:
                last_mod = datetime.fromisoformat(mod)
            except Exception:
                pass

        title = _visible_calendar_text(getattr(s, "titolo", ""), 140) or "Scadenza"
        summary = _prefixed_summary("Termine perentorio" if perentorio else "Scadenza", title)

        cal.aggiungi_evento_giornata(
            uid=f"{s.id}@pct-scadenze",
            summary=summary,
            start_date=d,
            description="\n".join(p for p in desc_parts if p),
            allarmi_min=allarmi,
            last_modified=last_mod,
        )
    return cal.build()


def agenda_scadenze_to_ical(appuntamenti, scadenze,
                             studio_nome: str = "IUSENTRA",
                             base_url: str = "") -> str:
    """
    Feed combinato: agenda + scadenze in un unico calendario.
    Utile per una sola sottoscrizione che copre tutto.
    """
    cal = ICalBuilder(cal_name=f"Studio — {studio_nome}")

    # ---- Appuntamenti ----
    for a in appuntamenti:
        desc_parts = []
        note = _visible_calendar_text(getattr(a, "note", "") or "", 700)
        if note:
            desc_parts.append(note)
        if getattr(a, "tipo", None):
            desc_parts.append(f"Tipo: {a.tipo.value}")
        if getattr(a, "procedimento", ""):
            desc_parts.append(f"Procedimento: {a.procedimento}")

        dt_start = getattr(a, "data_ora_dt", None) or a.data_ora
        if isinstance(dt_start, str):
            try:
                dt_start = datetime.fromisoformat(dt_start)
            except Exception:
                continue

        durata   = getattr(a, "durata_minuti", 60) or 60
        dt_end   = dt_start + timedelta(minutes=durata)
        reminder = getattr(a, "reminder_minuti", 60)

        mod = getattr(a, "modificato_il", None)
        last_mod = None
        if mod:
            try:
                last_mod = datetime.fromisoformat(mod)
            except Exception:
                pass

        cal.aggiungi_evento(
            uid=f"{a.id}@pct-agenda",
            summary=_visible_calendar_text(getattr(a, "titolo", ""), 140) or "Appuntamento",
            dtstart=dt_start,
            dtend=dt_end,
            location=getattr(a, "luogo", "") or "",
            description="\n".join(desc_parts),
            url=f"{base_url}/agenda/{a.id}" if base_url else "",
            allarme_min=reminder,
            last_modified=last_mod,
        )

    # ---- Scadenze ----
    for s in scadenze:
        d = getattr(s, "data_scadenza_obj", None)
        if d is None:
            raw = getattr(s, "data_scadenza", "")
            if not raw:
                continue
            try:
                d = date.fromisoformat(raw)
            except Exception:
                continue

        desc_parts = [_visible_calendar_text(getattr(s, "descrizione", "") or "", 700)]
        perentorio = getattr(s, "perentorio", False)
        if perentorio:
            desc_parts.append("Termine perentorio: controllare il deposito entro la data indicata.")

        if perentorio:
            allarmi = [7 * 1440, 3 * 1440, 1440, 60]
        else:
            giorni_preavviso = getattr(s, "giorni_preavviso", [1]) or [1]
            allarmi = [g * 1440 for g in giorni_preavviso] + [60]

        mod = getattr(s, "modificato_il", None)
        last_mod = None
        if mod:
            try:
                last_mod = datetime.fromisoformat(mod)
            except Exception:
                pass

        title = _visible_calendar_text(getattr(s, "titolo", ""), 140) or "Scadenza"
        summary = _prefixed_summary("Termine perentorio" if perentorio else "Scadenza", title)

        cal.aggiungi_evento_giornata(
            uid=f"{s.id}@pct-scadenze",
            summary=summary,
            start_date=d,
            description="\n".join(p for p in desc_parts if p),
            allarmi_min=allarmi,
            last_modified=last_mod,
        )

    return cal.build()
