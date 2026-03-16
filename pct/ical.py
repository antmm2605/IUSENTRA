"""
pct/ical.py — Generazione feed iCalendar (RFC 5545).

Nessuna dipendenza esterna — implementazione pura Python.
Compatibile con Google Calendar, Apple Calendar, Outlook.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from typing import List, Optional


def _escape(s: str) -> str:
    """Escape per valori iCal: \ ; , newline."""
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _dt(dt: datetime) -> str:
    """Formatta datetime in UTC per iCal: YYYYMMDDTHHMMSSZ"""
    if dt.tzinfo is None:
        return dt.strftime("%Y%m%dT%H%M%S")
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fold(line: str) -> str:
    """RFC 5545 line folding: max 75 ottetti, continua con CRLF + spazio."""
    result = []
    while len(line.encode("utf-8")) > 75:
        # taglia a 75 byte (considerando multi-byte chars)
        chunk = line[:75]
        while len(chunk.encode("utf-8")) > 75:
            chunk = chunk[:-1]
        result.append(chunk)
        line = " " + line[len(chunk):]
    result.append(line)
    return "\r\n".join(result)


class ICalBuilder:
    """Costruisce un file .ics con eventi VEVENT."""

    def __init__(self, cal_name: str = "Agenda", prod_id: str = "-//Studio Legale PCT//IT"):
        self._cal_name = cal_name
        self._prod_id  = prod_id
        self._events: List[str] = []

    def aggiungi_evento(
        self,
        uid:         str,
        summary:     str,
        dtstart:     datetime,
        dtend:       Optional[datetime] = None,
        description: str = "",
        location:    str = "",
        url:         str = "",
        allarme_min: Optional[int] = 60,  # minuti prima — None per disabilitare
    ) -> "ICalBuilder":
        from datetime import timedelta
        if dtend is None:
            dtend = dtstart + timedelta(hours=1)

        lines = [
            "BEGIN:VEVENT",
            f"UID:{_escape(uid)}",
            f"DTSTAMP:{_dt(datetime.now())}",
            f"DTSTART:{_dt(dtstart)}",
            f"DTEND:{_dt(dtend)}",
            f"SUMMARY:{_escape(summary)}",
        ]
        if description:
            lines.append(f"DESCRIPTION:{_escape(description)}")
        if location:
            lines.append(f"LOCATION:{_escape(location)}")
        if url:
            lines.append(f"URL:{url}")
        if allarme_min is not None:
            lines += [
                "BEGIN:VALARM",
                "TRIGGER:-PT" + str(allarme_min) + "M",
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
        ])
        return header + "\r\n" + "\r\n".join(self._events) + "\r\nEND:VCALENDAR\r\n"


def agenda_to_ical(appuntamenti, studio_nome: str = "Studio Legale PCT",
                   base_url: str = "") -> str:
    """
    Converte la lista di appuntamenti in un feed iCal.
    appuntamenti: lista di oggetti Appuntamento (pct.agenda)
    """
    cal = ICalBuilder(cal_name=f"Agenda — {studio_nome}")
    for a in appuntamenti:
        desc_parts = []
        if getattr(a, "descrizione", ""):
            desc_parts.append(a.descrizione)
        if getattr(a, "tipo", None):
            desc_parts.append(f"Tipo: {a.tipo.value}")
        uid = f"{a.id}@pct-studio-legale"
        cal.aggiungi_evento(
            uid=uid,
            summary=a.titolo,
            dtstart=a.data_ora,
            location=getattr(a, "luogo", "") or "",
            description="\n".join(desc_parts),
            url=f"{base_url}/agenda/{a.id}" if base_url else "",
        )
    return cal.build()


def scadenze_to_ical(scadenze, studio_nome: str = "Studio Legale PCT") -> str:
    """Converte le scadenze in un feed iCal (eventi tutto il giorno)."""
    from datetime import timedelta
    cal = ICalBuilder(cal_name=f"Scadenze — {studio_nome}")
    for s in scadenze:
        dt = datetime.combine(s.scadenza, datetime.min.time())
        desc_parts = [s.descrizione or ""]
        if s.perentorio:
            desc_parts.append("⚠️ SCADENZA PERENTORIA")
        cal.aggiungi_evento(
            uid=f"{s.id}@scadenze-pct",
            summary=("⚠️ " if s.perentorio else "") + s.titolo,
            dtstart=dt,
            dtend=dt + timedelta(hours=1),
            description="\n".join(desc_parts),
            allarme_min=1440,  # 24h prima
        )
    return cal.build()
