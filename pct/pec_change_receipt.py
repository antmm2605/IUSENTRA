"""Comunicazioni di cancelleria che cambiano un'udienza o un termine: ricezione in agenda.

Regola dello studio: quando la cancelleria comunica via PEC un rinvio, un differimento,
un'anticipazione o la revoca di un'udienza, oppure la modifica di un termine, l'agenda
riporta la comunicazione **nel giorno e all'ora in cui la PEC è stata consegnata**, in ora
italiana (Europe/Rome). L'avvocato vede così, alla data giusta, che è arrivato il cambio e
qual è la nuova data; l'udienza superata resta in agenda come «rinviata».

Riferimenti:
- art. 16, commi 4 e 6, D.L. 179/2012: comunicazioni di cancelleria per via telematica
  all'indirizzo PEC del difensore;
- art. 6 D.P.R. 68/2005 e art. 45 D.Lgs. 82/2005: la ricevuta di avvenuta consegna attesta
  il momento in cui il messaggio è disponibile nella casella del destinatario;
- art. 81 disp. att. c.p.c. e art. 175 c.p.c.: rinvio dell'udienza disposto dal giudice;
- art. 154 c.p.c.: proroga o abbreviazione dei termini ordinatori.

Il modulo è puro: niente I/O. Scrittura su agenda e scadenziario in ``pct.pec_pipeline``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")

RECEIPT_UID_PREFIX = "PEC_RICEZIONE"
RECEIPT_PROFILE_ID = "pec_ricezione"
RESCHEDULE_MARKER_PREFIX = "PEC_RINVIO"
RECEIPT_KIND_LINE = "Comunicazione ricevuta:"
RECEIPT_AT_LINE = "Ricevuta il:"
NEW_DATE_LINE = "Nuova data:"
PREVIOUS_DATE_LINE = "Data precedente:"

KIND_LABELS = {
    "termine_modificato": "Termine modificato",
    "udienza_revocata": "Udienza revocata",
    "udienza_anticipata": "Udienza anticipata",
    "udienza_differita": "Udienza differita",
    "rinvio_udienza": "Rinvio udienza",
}

_NOT_A_CHANGE = re.compile(r"\bSENTENZA\b|\bESTINZIONE\b|\bESTINTO\b|\bDESIGNAZIONE\b|\bCOSTITUZIONE\b", re.I)
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("termine_modificato", re.compile(r"\b(?:MODIFIC\w*|PROROG\w*|VARIAZIONE|VARIAT\w*|RIDETERMINA\w*)\s+(?:DEL\s+|DEI\s+)?TERMIN", re.I)),
    ("udienza_revocata", re.compile(r"\bREVOC\w*\s+(?:DELL['’]\s*|L['’]\s*)?UDIENZ", re.I)),
    ("udienza_anticipata", re.compile(r"\bANTICIPA\w*\b.{0,40}\bUDIENZ|\bUDIENZ\w*\b.{0,40}\bANTICIPAT", re.I)),
    ("udienza_differita", re.compile(r"\b(?:DIFFERI\w*|SPOSTA\w*|POSTICIPA\w*)\b.{0,40}\bUDIENZ|\bUDIENZ\w*\b.{0,40}\b(?:DIFFERIT|SPOSTAT|POSTICIPAT)", re.I)),
    ("rinvio_udienza", re.compile(r"\bRINVI(?:O|AT[OAIE])\b", re.I)),
)
_NEW_DATE_RE = re.compile(
    r"\b(?:AL|IL|ALLA\s+DATA\s+DEL|PER\s+IL|FINO\s+AL|ENTRO\s+IL|A)\s+"
    r"(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{4})"
    r"(?:[,\s]+(?:ORE\s+)?(?P<time>\d{1,2}[:.]\d{2}))?",
    re.I,
)
_RG_RE = re.compile(r"\b(\d{1,7})\s*/\s*(\d{4})\b")


@dataclass(frozen=True)
class ScheduleChange:
    kind: str
    new_date: str
    new_time: str
    event_date: str
    event: str
    description: str

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, "Cambio udienza")

    @property
    def is_term(self) -> bool:
        return self.kind == "termine_modificato"


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _iso_from_it(raw: str) -> str:
    match = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", str(raw or "").strip())
    if not match:
        return ""
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
    except ValueError:
        return ""


def date_it(value: str) -> str:
    try:
        return date.fromisoformat(str(value or "")[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(value or "")


def normalize_rg(value: Any) -> str:
    match = _RG_RE.search(str(value or ""))
    return f"{int(match.group(1))}/{match.group(2)}" if match else ""


def _profile_line(text: str, label: str) -> str:
    match = re.search(rf"^\s*{re.escape(label)}\s*:\s*(.+)$", text, flags=re.I | re.M)
    return _text(match.group(1)) if match else ""


def detect_schedule_change(
    profile: dict[str, Any] | None,
    *,
    body_text: str = "",
    fallback_date: str = "",
    fallback_time: str = "",
) -> ScheduleChange | None:
    """Riconosce il cambio di udienza o di termine dall'evento di cancelleria.

    Fonte primaria: «Oggetto» e «Descrizione» dell'evento del registro (Comunicazione.xml o
    corpo PEC). Fail-closed: senza parola di cambio o senza nuova data non c'è ricezione.
    """

    profile = profile if isinstance(profile, dict) else {}
    event = _text(profile.get("oggetto_evento")) or _profile_line(body_text, "Oggetto")
    description = _text(profile.get("descrizione_evento")) or _profile_line(body_text, "Descrizione")
    joined = f"{event} {description}".strip()
    if not joined or _NOT_A_CHANGE.search(event):
        return None
    kind = next((name for name, pattern in _PATTERNS if pattern.search(joined)), "")
    if not kind:
        return None
    new_date, new_time = "", ""
    for source in (description, event):
        match = _NEW_DATE_RE.search(source)
        if match and _iso_from_it(match.group("date")):
            new_date = _iso_from_it(match.group("date"))
            new_time = (match.group("time") or "").replace(".", ":")
            break
    if not new_date:
        new_date = str(fallback_date or "")[:10]
        new_time = str(fallback_time or "")
    if not new_date:
        return None
    if new_time in {"00:00", "0:00", "23:59"}:
        new_time = ""
    if new_time and len(new_time) == 4:
        new_time = f"0{new_time}"
    event_date = _iso_from_it(_text(profile.get("data_evento")) or _profile_line(body_text, "Data Evento"))
    return ScheduleChange(
        kind=kind,
        new_date=new_date,
        new_time=new_time,
        event_date=event_date,
        event=event[:220],
        description=description[:320],
    )


def receipt_datetime_rome(*values: Any) -> datetime | None:
    """Primo istante valido, convertito in ora italiana (naive, come l'agenda)."""

    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            # Gli istanti PEC sono salvati in UTC: un valore senza fuso è trattato come UTC.
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(ROME_TZ).replace(tzinfo=None, microsecond=0)
    return None


def receipt_uid(message_id: str) -> str:
    return f"{RECEIPT_UID_PREFIX}:{message_id}"


def reschedule_marker(message_id: str, new_date: str) -> str:
    return f"{RESCHEDULE_MARKER_PREFIX}:{message_id}|{str(new_date or '')[:10]}"


def reschedule_markers(note: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in str(note or "").splitlines():
        line = line.strip()
        if not line.startswith(f"{RESCHEDULE_MARKER_PREFIX}:"):
            continue
        payload = line.split(":", 1)[1]
        message_id, _, new_date = payload.partition("|")
        rows.append({"message_id": message_id, "new_date": new_date})
    return rows


def new_date_label(change: ScheduleChange) -> str:
    return f"{date_it(change.new_date)} ore {change.new_time}" if change.new_time else date_it(change.new_date)


def change_summary(change: ScheduleChange) -> str:
    """«rinvio udienza al 14/04/2027 ore 09:00», «udienza revocata: note scritte entro il 09/09/2026»."""

    if change.kind == "udienza_revocata" and re.search(r"\bNOTE\b", change.description, flags=re.I):
        return f"udienza revocata: note scritte entro il {new_date_label(change)}"
    return f"{change.label.lower()} al {new_date_label(change)}"


def receipt_title(change: ScheduleChange, *, rg: str = "") -> str:
    base = f"PEC ricevuta: {change_summary(change)}"
    return f"{base} - RG {rg}" if rg else base


def lawyer_activity(change: ScheduleChange) -> str:
    if change.is_term:
        return (
            f"leggere il provvedimento, aggiornare il termine al {date_it(change.new_date)} nel fascicolo "
            "e avvisare il cliente; verificare se cambiano anche le attività collegate."
        )
    return (
        f"leggere il provvedimento, verificare data e ora della nuova udienza ({new_date_label(change)}), "
        "aggiornare fascicolo e calendario e avvisare il cliente del rinvio."
    )


def _appointment_date(item: Any) -> date | None:
    raw = str(getattr(item, "data_ora", "") or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _is_hearing_like(item: Any) -> bool:
    title = _text(getattr(item, "titolo", "")).lower()
    tipo = str(getattr(getattr(item, "tipo", ""), "value", getattr(item, "tipo", "")) or "").upper()
    if any(token in title for token in ("opposizion", "notifica legale", "pec ricevuta", "sentenza")):
        return False
    if tipo == "UDIENZA":
        return True
    return "udienza" in title or ("note" in title and "sostituzione" in title)


def appointment_matches_fascicolo(item: Any, *, fascicolo_id: str, rg: str) -> bool:
    note = str(getattr(item, "note", "") or "")
    if fascicolo_id and re.search(rf"^\s*Fascicolo\s*:\s*{re.escape(fascicolo_id)}\s*$", note, flags=re.M | re.I):
        return True
    if rg:
        for value in (getattr(item, "procedimento", ""), getattr(item, "titolo", "")):
            if normalize_rg(value) == rg:
                return True
    return False


def select_rescheduled_appointments(
    appointments: Iterable[Any],
    *,
    fascicolo_id: str,
    rg: str,
    change: ScheduleChange,
    received_on: date,
    message_id: str,
    window_days: int = 60,
) -> tuple[list[Any], str]:
    """Udienze (o termini in sostituzione) superate dal cambio comunicato.

    Fail-closed: si considerano solo gli impegni aperti dello stesso fascicolo/RG, precedenti
    la nuova data. Vince la data dell'evento di cancelleria; altrimenti serve un'unica data
    candidata nella finestra attorno alla ricezione.
    """

    try:
        new_day = date.fromisoformat(change.new_date[:10])
    except ValueError:
        return [], "nuova data non leggibile"
    own_markers = (f"PEC_AUDIT:{message_id}", receipt_uid(message_id))
    candidates: list[tuple[date, Any]] = []
    for item in appointments:
        status = str(getattr(getattr(item, "stato", ""), "value", getattr(item, "stato", "")) or "").upper()
        if status not in {"PROGRAMMATO", "CONFERMATO"}:
            continue
        uid = str(getattr(item, "external_uid", "") or "")
        note = str(getattr(item, "note", "") or "")
        if uid.startswith(f"{RECEIPT_UID_PREFIX}:") or any(marker in uid or marker in note for marker in own_markers):
            continue
        if not _is_hearing_like(item) or not appointment_matches_fascicolo(item, fascicolo_id=fascicolo_id, rg=rg):
            continue
        day = _appointment_date(item)
        if day is None or day >= new_day:
            continue
        candidates.append((day, item))
    if not candidates:
        return [], "nessuna udienza precedente dello stesso fascicolo in agenda"
    if change.event_date:
        try:
            event_day = date.fromisoformat(change.event_date)
        except ValueError:
            event_day = None
        if event_day is not None:
            same_day = [item for day, item in candidates if day == event_day]
            if same_day:
                return same_day, f"udienza del {date_it(event_day.isoformat())} indicata dall'evento di cancelleria"
    window_start = received_on - timedelta(days=max(window_days, 1))
    in_window = [(day, item) for day, item in candidates if day >= window_start]
    days = sorted({day for day, _item in in_window})
    if len(days) == 1:
        return [item for _day, item in in_window], f"unica udienza aperta del fascicolo prima del {date_it(change.new_date)}"
    if not days:
        return [], "nessuna udienza aperta vicina alla data di ricezione"
    return [], "più udienze aperte nello stesso fascicolo: verificare quale è stata rinviata"
