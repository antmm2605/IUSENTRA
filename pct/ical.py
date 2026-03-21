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

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional


# ──────────────────────────────────────────── helpers RFC 5545

def _escape(s: str) -> str:
    """Escape caratteri speciali per valori iCal."""
    return (
        s.replace("\\", "\\\\")
         .replace(";", "\\;")
         .replace(",", "\\,")
         .replace("\n", "\\n")
    )


def _dt(dt: datetime) -> str:
    """Datetime → stringa UTC iCal (YYYYMMDDTHHMMSSZ)."""
    if dt.tzinfo is None:
        # Tratta come ora locale (floating), senza conversione
        return dt.strftime("%Y%m%dT%H%M%S")
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

    def __init__(self, cal_name: str = "Agenda", prod_id: str = "-//Studio Legale PCT//IT"):
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
            f"X-WR-CALNAME:{_escape(self._cal_name)}",
            "X-WR-TIMEZONE:Europe/Rome",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
            "X-PUBLISHED-TTL:PT1H",
        ])
        if self._events:
            return header + "\r\n" + "\r\n".join(self._events) + "\r\nEND:VCALENDAR\r\n"
        return header + "\r\nEND:VCALENDAR\r\n"


# ──────────────────────────────────────────── funzioni pubbliche

def agenda_to_ical(appuntamenti, studio_nome: str = "Studio Legale PCT",
                   base_url: str = "") -> str:
    """
    Converte la lista di Appuntamento in un feed iCal.
    Usa data_ora_dt (property datetime) e reminder_minuti per l'allarme.
    """
    cal = ICalBuilder(cal_name=f"Agenda — {studio_nome}")
    for a in appuntamenti:
        # Costruzione descrizione
        desc_parts = []
        note = getattr(a, "note", "") or ""
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
            summary=a.titolo,
            dtstart=dt_start,
            dtend=dt_end,
            location=getattr(a, "luogo", "") or "",
            description="\n".join(desc_parts),
            url=f"{base_url}/agenda/{a.id}" if base_url else "",
            allarme_min=reminder,
            last_modified=last_mod,
        )
    return cal.build()


def scadenze_to_ical(scadenze, studio_nome: str = "Studio Legale PCT") -> str:
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

        desc_parts = [getattr(s, "descrizione", "") or ""]
        perentorio = getattr(s, "perentorio", False)
        if perentorio:
            desc_parts.append("⚠️ SCADENZA PERENTORIA — termine non prorogabile")

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

        summary = ("⚠️ " if perentorio else "") + (getattr(s, "titolo", "") or "Scadenza")

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
                             studio_nome: str = "Studio Legale PCT",
                             base_url: str = "") -> str:
    """
    Feed combinato: agenda + scadenze in un unico calendario.
    Utile per una sola sottoscrizione che copre tutto.
    """
    cal = ICalBuilder(cal_name=f"Studio — {studio_nome}")

    # ---- Appuntamenti ----
    for a in appuntamenti:
        desc_parts = []
        note = getattr(a, "note", "") or ""
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
            summary=a.titolo,
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

        desc_parts = [getattr(s, "descrizione", "") or ""]
        perentorio = getattr(s, "perentorio", False)
        if perentorio:
            desc_parts.append("⚠️ SCADENZA PERENTORIA")

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

        summary = ("⚠️ " if perentorio else "") + (getattr(s, "titolo", "") or "Scadenza")

        cal.aggiungi_evento_giornata(
            uid=f"{s.id}@pct-scadenze",
            summary=summary,
            start_date=d,
            description="\n".join(p for p in desc_parts if p),
            allarmi_min=allarmi,
            last_modified=last_mod,
        )

    return cal.build()
