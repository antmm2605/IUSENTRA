"""Modifica di un termine già presidiato comunicata dalla cancelleria via PEC.

Base normativa:
- art. 16 D.L. 179/2012 e D.M. 44/2011: la comunicazione telematica di cancelleria
  riporta l'evento registrato nel registro di cancelleria (Data Evento, Tipo
  Evento, Oggetto, Descrizione), qui «MODIFICA TERMINE ...»;
- art. 154 c.p.c.: il giudice può abbreviare o prorogare i termini ordinatori;
- art. 127-ter c.p.c.: il termine per il deposito delle note scritte in
  sostituzione dell'udienza è fissato (e modificato) con provvedimento del giudice.

Quando la cancelleria comunica che un termine è stato modificato, il presidio non
deve creare un secondo termine lasciando aperto quello superato: individua nello
stesso fascicolo il termine aperto della stessa attività e lo sposta alla nuova
data, conservando la data precedente e il testo della comunicazione. Se il
termine precedente non è individuabile con certezza, il presidio crea il nuovo
termine dichiarando che deriva da una modifica.

Il modulo è puro: niente I/O. L'applicazione su scadenziario, agenda, calendari
e notifiche resta in ``pct.pec_pipeline``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

MODIFICATION_LINE_PREFIX = "PEC_MODIFICA_TERMINE"
HUMAN_LINE_PREFIX = "Modifica termine:"
COMMUNICATION_LINE_PREFIX = "Comunicazione di cancelleria:"

_VERB = (
    r"MODIFICAT[OAIE]|MODIFICA|VARIAZIONE|VARIAT[OAIE]|DIFFERIMENTO|DIFFERIT[OAIE]|"
    r"PROROGA|PROROGAT[OAIE]|ANTICIPAZIONE|ANTICIPAT[OAIE]|SPOSTAMENTO|SPOSTAT[OAIE]|"
    r"RIDETERMINAZIONE|RIDETERMINAT[OAIE]|NUOVO"
)
_MODIFICATION_RE = re.compile(
    rf"\b(?P<verb>{_VERB})\s+(?:(?:DEL|DELLA|DELL'|DEI|DI)\s*)?(?P<obj>TERMINE|TERMINI|SCADENZA)\b"
    rf"(?P<what>(?:(?!\b(?:{_VERB})\s+(?:(?:DEL|DELLA|DELL'|DEI|DI)\s*)?(?:TERMINE|TERMINI|SCADENZA)\b)(?!\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{4}}).){{0,140}}?)"
    r"\b(?:IL|AL|ALLA\s+DATA\s+DEL|AL\s+GIORNO|PER\s+IL|FINO\s+AL|ENTRO\s+IL|A)\s+"
    r"(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{4})"
    r"(?:\s+(?:ORE\s+)?(?P<time>\d{1,2}[:.]\d{2}))?",
    flags=re.I,
)

FAMILY_LABELS = {
    "note_scritte": "Deposito note scritte ex art. 127-ter c.p.c.",
    "memorie": "Deposito memorie",
    "conclusionali": "Deposito comparse conclusionali e repliche",
    "costituzione": "Costituzione in giudizio",
    "ctu": "Termine consulenza tecnica",
    "deposito": "Deposito",
    "generico": "Termine processuale",
}


def _fold(value: Any) -> str:
    text = " ".join(str(value or "").split()).lower()
    return (
        text.replace("à", "a").replace("è", "e").replace("é", "e").replace("ì", "i").replace("ò", "o").replace("ù", "u")
    )


def activity_family(*texts: Any) -> str:
    """Attività a cui si riferisce un termine, letta da titolo, descrizione o evento."""

    folded = _fold(" ".join(str(item or "") for item in texts)).replace("-", " ")
    if "note" in folded and any(token in folded for token in ("sostituzione", "scritte", "trattazione scritta")):
        return "note_scritte"
    if "127 ter" in folded or "trattazione scritta" in folded:
        return "note_scritte"
    if any(token in folded for token in ("conclusional", "repliche", "190 c.p.c")):
        return "conclusionali"
    if any(token in folded for token in ("memori", "171 ter", "183 c.p.c")):
        return "memorie"
    if "costituzion" in folded or "comparsa di risposta" in folded:
        return "costituzione"
    if any(token in folded for token in ("ctu", "consulen", "perizia", "relazione peritale")):
        return "ctu"
    if "deposit" in folded:
        return "deposito"
    return "generico"


def _iso_from_it(raw: str) -> str:
    match = re.match(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", str(raw or "").strip())
    if not match:
        return ""
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
    except ValueError:
        return ""


def date_label_it(value: str) -> str:
    try:
        return date.fromisoformat(str(value or "")[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(value or "")


@dataclass(frozen=True)
class TermModification:
    new_date: str
    new_time: str
    family: str
    phrase: str
    event_date: str
    communication: str

    @property
    def family_label(self) -> str:
        return FAMILY_LABELS.get(self.family, FAMILY_LABELS["generico"])

    def audit_line(self, *, old_date: str, message_id: str) -> str:
        return "|".join((MODIFICATION_LINE_PREFIX, old_date[:10], self.new_date, self.family, message_id))

    def human_summary(self, old_date: str = "") -> str:
        event = f" con evento del {date_label_it(self.event_date)}" if self.event_date else ""
        if old_date:
            return (
                f"termine modificato dalla cancelleria{event}: dal {date_label_it(old_date)} "
                f"al {date_label_it(self.new_date)} ({self.phrase})."
            )
        return f"termine fissato al {date_label_it(self.new_date)} per modifica comunicata dalla cancelleria{event} ({self.phrase})."


def _profile_sources(report: dict[str, Any] | None, parsed: dict[str, Any] | None) -> tuple[list[str], str, dict[str, Any]]:
    """Testi in ordine di precisione: descrizione evento, oggetto, corpo PEC, XML ministeriali."""

    report = report if isinstance(report, dict) else {}
    parsed = parsed if isinstance(parsed, dict) else {}
    profile = report.get("procedural_profile") if isinstance(report.get("procedural_profile"), dict) else {}
    if not profile and isinstance(parsed.get("procedural_profile"), dict):
        profile = parsed["procedural_profile"]
    body = parsed.get("body") if isinstance(parsed.get("body"), dict) else {}
    body_text = " ".join(str(body.get("text") or body.get("html_text") or "").split())
    xml_texts = [
        " ".join(str(item.get("text") or item.get("contenuto") or item.get("content") or "").split())
        for item in list(parsed.get("xml_documents") or [])
        if isinstance(item, dict)
    ]
    sources = [
        " ".join(str(profile.get("descrizione_evento") or "").split()),
        " ".join(f"{profile.get('oggetto_evento') or ''} {profile.get('descrizione_evento') or ''}".split()),
        body_text,
        *xml_texts,
    ]
    return [source for source in sources if source], body_text, profile


def _communication_excerpt(body_text: str, phrase: str) -> str:
    lower = body_text.lower()
    start = lower.find("si da' atto")
    if start < 0:
        start = lower.find("si da atto")
    lead = body_text[start : start + 420].strip() if start >= 0 else ""
    parts = [part for part in (lead, phrase) if part]
    return " … ".join(parts)[:900]


def detect_term_modification(
    parsed: dict[str, Any] | None,
    report: dict[str, Any] | None,
) -> TermModification | None:
    """Riconosce la comunicazione di modifica di un termine e ne estrae la nuova data."""

    sources, body_text, profile = _profile_sources(report, parsed)
    for text in sources:
        for match in _MODIFICATION_RE.finditer(text):
            new_date = _iso_from_it(match.group("date"))
            if not new_date:
                continue
            verb = match.group("verb").strip().upper()
            what = " ".join(match.group("what").split()).strip(" ,.;:-")
            if verb == "NUOVO" and not what:
                continue
            phrase = " ".join(match.group(0).split())
            time_value = (match.group("time") or "").replace(".", ":")
            if time_value in {"00:00", "0:00"}:
                time_value = ""
            event_date = _iso_from_it(str(profile.get("data_evento") or ""))
            if not event_date:
                event_match = re.search(r"Data\s+Evento\s*:\s*(\d{1,2}/\d{1,2}/\d{4})", " ".join(sources), flags=re.I)
                event_date = _iso_from_it(event_match.group(1)) if event_match else ""
            return TermModification(
                new_date=new_date,
                new_time=time_value,
                family=activity_family(what, profile.get("oggetto_evento")),
                phrase=phrase[:220],
                event_date=event_date,
                communication=_communication_excerpt(body_text, phrase),
            )
    return None


def _note_lines(item: Any) -> list[str]:
    return [line.strip() for line in str(getattr(item, "note", "") or "").splitlines() if line.strip()]


def modification_lines(item: Any) -> list[dict[str, str]]:
    """Righe di modifica persistite nelle note di una scadenza o di un appuntamento."""

    rows: list[dict[str, str]] = []
    for line in _note_lines(item):
        if not line.startswith(f"{MODIFICATION_LINE_PREFIX}|"):
            continue
        parts = line.split("|", 5)
        if len(parts) < 5:
            continue
        rows.append({"old_date": parts[1], "new_date": parts[2], "family": parts[3], "message_id": parts[4]})
    return rows


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _item_family(item: Any) -> str:
    return activity_family(
        getattr(item, "titolo", ""),
        getattr(item, "descrizione", ""),
        getattr(item, "deadline_profile_code", ""),
        getattr(item, "source_event_type", ""),
    )


def find_deadline_to_modify(
    items: Iterable[Any],
    *,
    fascicolo_id: str,
    modification: TermModification,
    message_id: str,
) -> Any | None:
    """Termine aperto dello stesso fascicolo e della stessa attività da spostare.

    Fail-closed: con attività generica serve un solo termine automatico aperto;
    con più candidati della stessa attività vince quello più vicino alla data
    dell'evento di cancelleria.
    """

    fascicolo = str(fascicolo_id or "").strip()
    if not fascicolo:
        return None
    marker = f"PEC_AUDIT:{message_id}"
    candidates: list[Any] = []
    for item in items:
        if str(getattr(item, "id_fascicolo", "") or "").strip() != fascicolo:
            continue
        if _enum_value(getattr(item, "stato", "")) not in {"APERTO", "SCADUTO"}:
            continue
        if marker in _note_lines(item):
            continue
        if _enum_value(getattr(item, "tipo", "")) == "UDIENZA":
            continue
        due = str(getattr(item, "data_scadenza", "") or "")[:10]
        if not due or due == modification.new_date:
            continue
        family = _item_family(item)
        if modification.family != "generico":
            if family != modification.family:
                continue
        elif "PEC_AUDIT:" not in str(getattr(item, "note", "") or ""):
            continue
        candidates.append(item)
    if not candidates:
        return None
    if modification.family == "generico" and len(candidates) != 1:
        return None
    reference = modification.event_date or date.today().isoformat()

    def _distance(item: Any) -> tuple[int, int]:
        due = str(getattr(item, "data_scadenza", "") or "")[:10]
        try:
            delta = (date.fromisoformat(due) - date.fromisoformat(reference)).days
        except ValueError:
            return (1, 10**6)
        return (0 if delta >= 0 else 1, abs(delta))

    return sorted(candidates, key=_distance)[0]


def find_superseding_modification(
    items: Iterable[Any],
    *,
    fascicolo_id: str,
    target_date: str,
    family: str,
) -> dict[str, str] | None:
    """Una data già superata da una modifica non deve essere ricreata da letture successive."""

    fascicolo = str(fascicolo_id or "").strip()
    if not fascicolo or not target_date:
        return None
    for item in items:
        if str(getattr(item, "id_fascicolo", "") or "").strip() != fascicolo:
            continue
        for row in modification_lines(item):
            if row["old_date"] != target_date[:10]:
                continue
            if family in {"generico", row["family"]} or row["family"] == "generico":
                return {**row, "deadline_id": str(getattr(item, "id", "") or "")}
    return None


def title_with_new_date(title: str, *, old_date: str, new_date: str, family_label: str) -> str:
    old_label = date_label_it(old_date)
    new_label = date_label_it(new_date)
    if old_label and old_label in str(title or ""):
        return str(title).replace(old_label, new_label)
    base = str(title or "").strip() or family_label
    return f"{base} - {new_label}"
