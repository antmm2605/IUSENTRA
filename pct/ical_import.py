"""
pct/ical_import.py — Parser iCalendar (RFC 5545) per importazione eventi.

Nessuna dipendenza esterna — implementazione pura Python.
Compatibile con export di Google Calendar, Apple Calendar, Outlook,
Thunderbird Lightning e qualsiasi client conforme a RFC 5545.

Uso:
    from pct.ical_import import parse_ics, EventoImportato
    eventi = parse_ics(testo_ics)          # → List[EventoImportato]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# ──────────────────────────────────────────── costanti

_ROME = ZoneInfo("Europe/Rome")

# Mapping alias TZID → IANA usati da Outlook/Windows
_TZID_ALIAS: Dict[str, str] = {
    # Windows / Outlook
    "Romance Standard Time":     "Europe/Paris",
    "Central Europe Standard Time": "Europe/Warsaw",
    "W. Europe Standard Time":   "Europe/Berlin",
    "Israel Standard Time":      "Asia/Jerusalem",
    "Russian Standard Time":     "Europe/Moscow",
    "Eastern Standard Time":     "America/New_York",
    "Pacific Standard Time":     "America/Los_Angeles",
    "Mountain Standard Time":    "America/Denver",
    "Central Standard Time":     "America/Chicago",
    "GMT Standard Time":         "Europe/London",
    "FLE Standard Time":         "Europe/Helsinki",
    # Apple / altri alias comuni
    "Europe/Roma":               "Europe/Rome",
    "IT":                        "Europe/Rome",
    "CET":                       "Europe/Rome",
    "CEST":                      "Europe/Rome",
}


# ──────────────────────────────────────────── dataclass output

@dataclass
class EventoImportato:
    """Rappresenta un singolo VEVENT estratto da un file .ics."""
    uid:           str = ""
    titolo:        str = ""
    data_ora:      str = ""          # ISO 8601 "YYYY-MM-DDTHH:MM:SS" oppure "YYYY-MM-DD" (tutto-giorno)
    durata_minuti: int = 60
    tutto_giorno:  bool = False
    luogo:         str = ""
    descrizione:   str = ""
    stato_ical:    str = "CONFIRMED"  # CONFIRMED, TENTATIVE, CANCELLED
    organizzatore: str = ""
    rrule:         str = ""          # ricorrenza (solo info, non espandiamo)

    @property
    def data_display(self) -> str:
        """Data leggibile per la UI (es. '15 Mar 2024')."""
        try:
            if self.tutto_giorno:
                d = date.fromisoformat(self.data_ora)
                return d.strftime("%-d %b %Y")
            dt = datetime.fromisoformat(self.data_ora)
            return dt.strftime("%-d %b %Y %H:%M")
        except Exception:
            return self.data_ora

    @property
    def ora_display(self) -> str:
        """Ora leggibile (vuoto per eventi tutto-giorno)."""
        if self.tutto_giorno:
            return "Tutto il giorno"
        try:
            dt = datetime.fromisoformat(self.data_ora)
            fine = dt + timedelta(minutes=self.durata_minuti)
            return f"{dt.strftime('%H:%M')} – {fine.strftime('%H:%M')}"
        except Exception:
            return ""


# ──────────────────────────────────────────── helpers parsing

def _unfold(text: str) -> str:
    """
    RFC 5545 §3.1 — Rimuove il line-folding (CRLF/CR/LF + spazio/tab iniziali).
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", text)


def _parse_property(line: str) -> Tuple[str, Dict[str, str], str]:
    """
    Analizza una riga iCal:   NOME;PARAM=VAL:valore
    Restituisce (nome, params_dict, valore).
    """
    # Separa nome+params dal valore (primo ':' non dentro un parametro quotato)
    colon_idx = -1
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif ch == ':' and not in_quote:
            colon_idx = i
            break
    if colon_idx == -1:
        return line.strip(), {}, ""

    left  = line[:colon_idx]
    value = line[colon_idx + 1:]

    # Separa nome dai parametri
    parts = left.split(";")
    name  = parts[0].upper()
    params: Dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
        else:
            params[p.upper()] = ""
    return name, params, value


def _tz_from_tzid(tzid: str) -> ZoneInfo:
    """Risolve TZID → ZoneInfo, con fallback su alias e poi su Rome."""
    if not tzid:
        return _ROME
    # Prova diretto
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, KeyError):
        pass
    # Prova alias
    mapped = _TZID_ALIAS.get(tzid)
    if mapped:
        try:
            return ZoneInfo(mapped)
        except (ZoneInfoNotFoundError, KeyError):
            pass
    # Fallback
    return _ROME


def _parse_dt(value: str, params: Dict[str, str]) -> Tuple[Optional[datetime], bool]:
    """
    Analizza DTSTART / DTEND.
    Restituisce (datetime_utc_naive_equivalente_o_rome, tutto_giorno).

    Formati gestiti:
      - DATE:        YYYYMMDD              → tutto_giorno=True
      - DATETIME UTC: YYYYMMDDTHHMMSSZ     → convertito da UTC
      - DATETIME TZID: YYYYMMDDTHHMMSS + TZID param  → convertito dal TZ
      - DATETIME naive: YYYYMMDDTHHMMSS    → trattato come Europe/Rome
    """
    value = value.strip()

    # Tutto il giorno
    if params.get("VALUE") == "DATE" or (len(value) == 8 and "T" not in value):
        try:
            d = datetime.strptime(value, "%Y%m%d")
            return d, True
        except ValueError:
            return None, True

    # Rimuovi eventuali caratteri extra
    value = value.rstrip("Z") if value.endswith("Z") else value
    is_utc = value.endswith("Z") or params.get("VALUE", "").upper() == "DATE-TIME"

    # Parsing del datetime
    fmt_candidates = ["%Y%m%dT%H%M%S", "%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%S"]
    dt = None
    for fmt in fmt_candidates:
        try:
            dt = datetime.strptime(value.rstrip("Z"), fmt.rstrip("Z"))
            break
        except ValueError:
            continue

    if dt is None:
        return None, False

    # Aggiunge timezone
    if "Z" in (params.get("VALUE", "") + value + "") or value.upper().endswith("Z"):
        # UTC → converti in Rome (naive per storage)
        dt = dt.replace(tzinfo=timezone.utc).astimezone(_ROME).replace(tzinfo=None)
    elif "TZID" in params:
        tz = _tz_from_tzid(params["TZID"])
        dt = dt.replace(tzinfo=tz).astimezone(_ROME).replace(tzinfo=None)
    # else: naive → trattato come Rome, non serve conversione

    return dt, False


def _parse_duration(value: str) -> int:
    """
    Analizza DURATION (RFC 5545 §3.3.6) → minuti interi.
    Esempi: PT1H, PT30M, P1D, P1DT2H30M, -PT15M
    """
    value = value.strip().lstrip("+-")
    total = 0
    m = re.match(
        r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?",
        value,
    )
    if m:
        weeks   = int(m.group(1) or 0)
        days    = int(m.group(2) or 0)
        hours   = int(m.group(3) or 0)
        minutes = int(m.group(4) or 0)
        seconds = int(m.group(5) or 0)
        total = weeks * 7 * 24 * 60 + days * 24 * 60 + hours * 60 + minutes + seconds // 60
    return max(total, 1)


def _unescape(s: str) -> str:
    """Inverte l'escape iCal: \\n → \n, \\; → ;, \\, → , ecc."""
    return (
        s.replace("\\n", "\n")
         .replace("\\N", "\n")
         .replace("\\;", ";")
         .replace("\\,", ",")
         .replace("\\\\", "\\")
    )


# ──────────────────────────────────────────── parser principale

def _iter_vevents(text: str) -> Iterator[Dict[str, Tuple[Dict[str, str], str]]]:
    """
    Itera sui blocchi VEVENT di un testo iCal già unfolded.
    Ogni VEVENT è un dict: { nome_prop: (params, value), ... }
    Nel caso di proprietà duplicate (es. EXDATE), tiene solo la prima.
    """
    inside  = False
    current: Dict[str, Tuple[Dict[str, str], str]] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.upper() == "BEGIN:VEVENT":
            inside  = True
            current = {}
            continue

        if line.upper() == "END:VEVENT":
            if inside:
                yield current
            inside  = False
            current = {}
            continue

        if inside:
            name, params, value = _parse_property(line)
            if name and name not in current:
                current[name] = (params, value)


def parse_ics(testo: str) -> List[EventoImportato]:
    """
    Analizza un file .ics (stringa testo) e restituisce la lista degli eventi.

    Gestisce:
    - Google Calendar export (UTF-8, timezone TZID)
    - Apple Calendar .ics (UTF-8 e UTF-16)
    - Outlook .ics (Windows TZID alias, CRLF)
    - Thunderbird Lightning
    - Qualsiasi file RFC 5545 conforme

    Non espande le ricorrenze (RRULE): gli eventi ricorrenti sono importati
    come singola occorrenza (data di inizio) con nota sulla ricorrenza.
    """
    unfolded = _unfold(testo)
    eventi: List[EventoImportato] = []

    for props in _iter_vevents(unfolded):

        def get(name: str) -> Tuple[Dict[str, str], str]:
            return props.get(name, ({}, ""))

        # ── SUMMARY
        _, summary = get("SUMMARY")
        titolo = _unescape(summary).strip() or "(Senza titolo)"

        # ── DTSTART
        dt_params, dt_value = get("DTSTART")
        if not dt_value:
            continue  # evento senza data → saltiamo
        dt_start, tutto_giorno = _parse_dt(dt_value, dt_params)
        if dt_start is None:
            continue

        # ── DTEND / DURATION
        dt_end = None
        durata = 0

        end_params, end_value = get("DTEND")
        if end_value:
            dt_end, _ = _parse_dt(end_value, end_params)

        dur_params, dur_value = get("DURATION")
        if not dt_end and dur_value:
            durata = _parse_duration(dur_value)

        if dt_end:
            delta = dt_end - dt_start
            durata = max(int(delta.total_seconds() / 60), 1)
        elif not durata:
            durata = 1440 if tutto_giorno else 60  # default

        # ── UID
        _, uid = get("UID")

        # ── LOCATION
        _, location = get("LOCATION")
        luogo = _unescape(location).strip()

        # ── DESCRIPTION
        _, desc = get("DESCRIPTION")
        descrizione = _unescape(desc).strip()

        # ── STATUS
        _, status = get("STATUS")
        stato_ical = status.upper() or "CONFIRMED"

        # ── ORGANIZER
        org_params, org_value = get("ORGANIZER")
        organizzatore = ""
        if org_value:
            # mailto:nome@dominio.com  o  CN=Nome:MAILTO:...
            cn = org_params.get("CN", "")
            organizzatore = cn or org_value.replace("mailto:", "").replace("MAILTO:", "")

        # ── RRULE (ricorrenza — solo info)
        _, rrule = get("RRULE")

        # ── data_ora per storage: ISO 8601
        if tutto_giorno:
            data_ora = dt_start.strftime("%Y-%m-%d")
        else:
            data_ora = dt_start.strftime("%Y-%m-%dT%H:%M:%S")

        eventi.append(EventoImportato(
            uid=uid,
            titolo=titolo,
            data_ora=data_ora,
            durata_minuti=durata,
            tutto_giorno=tutto_giorno,
            luogo=luogo,
            descrizione=descrizione,
            stato_ical=stato_ical,
            organizzatore=organizzatore,
            rrule=rrule,
        ))

    return eventi


def evento_to_dict(e: EventoImportato) -> dict:
    """Serializza EventoImportato in dict JSON (per trasporto nel form)."""
    return {
        "uid":           e.uid,
        "titolo":        e.titolo,
        "data_ora":      e.data_ora,
        "durata_minuti": e.durata_minuti,
        "tutto_giorno":  e.tutto_giorno,
        "luogo":         e.luogo,
        "descrizione":   e.descrizione,
        "stato_ical":    e.stato_ical,
        "organizzatore": e.organizzatore,
        "rrule":         e.rrule,
    }


def dict_to_evento(d: dict) -> EventoImportato:
    """Deserializza dict JSON → EventoImportato."""
    return EventoImportato(
        uid=d.get("uid", ""),
        titolo=d.get("titolo", ""),
        data_ora=d.get("data_ora", ""),
        durata_minuti=int(d.get("durata_minuti", 60)),
        tutto_giorno=bool(d.get("tutto_giorno", False)),
        luogo=d.get("luogo", ""),
        descrizione=d.get("descrizione", ""),
        stato_ical=d.get("stato_ical", "CONFIRMED"),
        organizzatore=d.get("organizzatore", ""),
        rrule=d.get("rrule", ""),
    )
