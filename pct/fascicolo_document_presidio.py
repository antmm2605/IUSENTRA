from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from pct.formatting import format_date_it


_DATE_RE = re.compile(r"\b(?P<day>[0-3]?\d)[./-](?P<month>[01]?\d)[./-](?P<year>(?:19|20)\d{2})\b")
_ISO_RE = re.compile(r"\b(?P<year>(?:19|20)\d{2})-(?P<month>[01]\d)-(?P<day>[0-3]\d)\b")
_TIME_RE = re.compile(r"\b(?:ore|h\.?)\s*(?P<hour>[0-2]?\d)[:.,](?P<minute>[0-5]\d)\b", re.IGNORECASE)
_RG_RE = re.compile(r"\b(?:r\.?\s*g\.?|rgl|n\.?\s*r\.?\s*g\.?)\s*(?:n\.?)?\s*(?P<num>\d{1,7})\s*/\s*(?P<year>(?:19|20)\d{2})\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[^a-z0-9]+")


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _value(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return ""


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", _text(value))
    ascii_text = "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()
    return _WORD_RE.sub(" ", ascii_text).strip()


def _compact_key(value: Any) -> str:
    return _WORD_RE.sub("", _fold(value))


def _client_duplicate_key(value: Any) -> str:
    folded = _fold(value)
    tokens = [token for token in folded.split() if token]
    for index, token in enumerate(tokens):
        if token in {"c", "contro", "vs", "versus", "avverso"} and index >= 2:
            tokens = tokens[:index]
            break
    if 2 <= len(tokens) <= 6:
        return "".join(sorted(tokens))
    return _compact_key(folded)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = _text(value)
    if not text:
        return None
    iso = _ISO_RE.search(text)
    if iso:
        try:
            return date(int(iso.group("year")), int(iso.group("month")), int(iso.group("day")))
        except ValueError:
            return None
    match = _DATE_RE.search(text)
    if match:
        try:
            return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
        except ValueError:
            return None
    return None


def _date_iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def _date_label(value: date | None) -> str:
    return format_date_it(value) if value else ""


def _short(value: Any, limit: int = 220) -> str:
    raw = re.sub(r"\s+", " ", _text(value))
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "..."


def _snippet(text: str, pattern: str, radius: int = 180) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return _short(text, radius)
    start = max(0, match.start() - radius // 2)
    end = min(len(text), match.end() + radius // 2)
    return _short(text[start:end], radius)


def _date_near(text: str, pattern: str, *, after: bool = True, radius: int = 260) -> date | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    if after:
        window = text[match.start() : min(len(text), match.end() + radius)]
    else:
        window = text[max(0, match.start() - radius) : match.end()]
    return _parse_date(window)


def _time_near(text: str, anchor_date: date | None) -> str:
    if not anchor_date:
        return ""
    date_text = anchor_date.strftime("%d/%m/%Y")
    index = text.find(date_text)
    if index < 0:
        date_text = f"{anchor_date.day}/{anchor_date.month}/{anchor_date.year}"
        index = text.find(date_text)
    window = text[max(0, index) : min(len(text), index + 180)] if index >= 0 else text[:260]
    match = _TIME_RE.search(window)
    if not match:
        return ""
    return f"{int(match.group('hour')):02d}:{int(match.group('minute')):02d}"


def _document_source(metadata: dict[str, Any], document_id: str) -> str:
    source = _text(
        metadata.get("filename")
        or metadata.get("safe_filename")
        or metadata.get("nome")
        or metadata.get("name")
        or document_id,
        "Documento fascicolo",
    )
    marker = source.casefold()
    if marker.startswith(("document_id:", "documento_id:", "docai-", "docai_", "doc-", "doc_", "pst:")):
        return "Documento indicizzato del fascicolo"
    return source


def _make_action(
    *,
    action_type: str,
    title: str,
    due: date | None,
    source: str,
    document_id: str,
    description: str,
    tone: str = "warning",
    priority: str = "important",
    peremptory: bool = False,
    time_value: str = "",
    requires_communication_date: bool = False,
) -> dict[str, Any]:
    date_label = _date_label(due)
    if time_value and date_label:
        date_label = f"{date_label} {time_value}"
    return {
        "id": f"{action_type}-{document_id}-{_date_iso(due) or 'senza-data'}",
        "type": action_type,
        "title": title,
        "label": title,
        "dateIso": _date_iso(due),
        "date": date_label,
        "time": time_value,
        "tone": tone,
        "priority": priority,
        "peremptory": peremptory,
        "requiresCommunicationDate": requires_communication_date,
        "source": source,
        "documentId": document_id,
        "description": _short(description, 260),
    }


def _contains_fascicolo_references(text: str, fascicolo: Any) -> bool:
    folded = _fold(text)
    rg = normalise_rg_parts(fascicolo)
    if rg and f"{rg[0]} {rg[1]}" in folded.replace("/", " "):
        return True
    for value in (
        _value(fascicolo, "nome_cliente", "client", "cliente"),
        _value(fascicolo, "titolo", "title"),
        _value(fascicolo, "oggetto", "subtitle", "object"),
        _value(fascicolo, "controparte", "counterparty"),
    ):
        folded_value = _fold(value)
        if folded_value and len(folded_value) >= 5 and folded_value in folded:
            return True
    return False


def normalise_rg_parts(fascicolo: Any) -> tuple[str, str] | None:
    number = _text(_value(fascicolo, "numero_rg", "rgNumber", "numeroRg", "rg_number"))
    year = _text(_value(fascicolo, "anno_rg", "rgYear", "annoRg", "rg_year"))
    rg_full = _text(_value(fascicolo, "rg_completo", "rg", "ref", "numero_causa"))
    if not number or not year:
        match = _RG_RE.search(rg_full)
        if match:
            number = number or match.group("num")
            year = year or match.group("year")
    if not number or not year:
        match = re.search(r"(?P<num>\d{1,7})\s*/\s*(?P<year>(?:19|20)\d{2})", rg_full)
        if match:
            number = number or match.group("num")
            year = year or match.group("year")
    number_match = re.search(r"\d{1,7}", number)
    year_match = re.search(r"(?:19|20)\d{2}", year)
    if not number_match or not year_match:
        return None
    return str(int(number_match.group(0))), year_match.group(0)


def normalise_practice_duplicate_key(fascicolo: Any) -> str:
    rg = normalise_rg_parts(fascicolo)
    if not rg:
        return ""
    client = (
        _text(_value(fascicolo, "nome_cliente", "client", "cliente"))
    )
    client_key = _client_duplicate_key(client)
    if not client_key:
        return ""
    return f"{client_key}|rg:{rg[0]}/{rg[1]}"


def duplicate_practice_groups(fascicoli: Iterable[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for fascicolo in fascicoli or []:
        key = normalise_practice_duplicate_key(fascicolo)
        if key:
            grouped[key].append(fascicolo)
    out: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        if len(rows) < 2:
            continue
        first = rows[0]
        rg = normalise_rg_parts(first) or ("", "")
        client = (
            _text(_value(first, "nome_cliente", "client", "cliente"))
            or "Cliente non collegato"
        )
        ids = [_text(_value(row, "id")) for row in rows if _text(_value(row, "id"))]
        refs = [_text(_value(row, "numero", "ref", "id")) for row in rows]
        out.append(
            {
                "key": key,
                "client": client,
                "rg": f"RG {rg[0]}/{rg[1]}" if rg[0] and rg[1] else "RG n.d.",
                "count": len(rows),
                "ids": ids,
                "refs": refs,
                "label": f"{client} - RG {rg[0]}/{rg[1]}" if rg[0] and rg[1] else client,
            }
        )
    out.sort(key=lambda item: (_fold(item.get("client")), _text(item.get("rg"))))
    return out


def _analyze_127_ter(text: str, *, source: str, document_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    if "127 ter" not in _fold(text).replace("-", " "):
        return actions, warnings
    notes_date = (
        _date_near(text, r"(?:termine|scadenza).*?(?:deposito\s+di\s+)?note\s+scritte", after=False)
        or _date_near(text, r"(?:note\s+scritte).*?(?:termine|scadenza)", after=True)
        or _date_near(text, r"(?:fissa|assegna).*?(?:127\s*ter|sostituzione\s+dell'?udienza)", after=True)
    )
    if notes_date:
        actions.append(
            _make_action(
                action_type="note_127_ter",
                title="Deposito note scritte ex art. 127-ter c.p.c.",
                due=notes_date,
                source=source,
                document_id=document_id,
                peremptory=True,
                tone="danger",
                priority="urgent",
                description=(
                    "Il decreto fissa la sostituzione dell'udienza con note scritte. "
                    "Il giorno di scadenza è trattato come data dell'udienza: preparare istanze, conclusioni e allegati prima del deposito."
                ),
            )
        )
        if re.search(r"30\s+giorn[io]\s+prima", text, flags=re.IGNORECASE):
            notify_date = notes_date - timedelta(days=30)
            actions.append(
                _make_action(
                    action_type="notifica_ricorso_decreto",
                    title="Notifica ricorso e decreto entro 30 giorni prima",
                    due=notify_date,
                    source=source,
                    document_id=document_id,
                    tone="warning",
                    priority="important",
                    description="Dal decreto risulta l'onere di notificare ricorso e decreto almeno 30 giorni prima della data fissata.",
                )
            )
        if re.search(r"10\s+giorn[io]\s+prima.*(?:scadenza|udienza|termine)|(?:scadenza|udienza|termine).*10\s+giorn[io]\s+prima", text, flags=re.IGNORECASE | re.DOTALL):
            constitution_date = notes_date - timedelta(days=10)
            actions.append(
                _make_action(
                    action_type="costituzione_resistente",
                    title="Verifica costituzione resistente entro 10 giorni prima",
                    due=constitution_date,
                    source=source,
                    document_id=document_id,
                    tone="info",
                    priority="normal",
                    description="Il decreto assegna alla parte resistente un termine sino a 10 giorni prima della scadenza per la costituzione.",
                )
            )
    else:
        warnings.append(f"{source}: rilevato art. 127-ter c.p.c. ma non una data certa del termine note.")
    return actions, warnings


def _analyze_127_bis(text: str, *, source: str, document_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    if "127 bis" not in _fold(text).replace("-", " ") and "audiovisiv" not in _fold(text):
        return actions, warnings
    hearing_date = _date_near(text, r"(?:udienza|comparizione|discussione)", after=True) or _parse_date(text)
    hearing_time = _time_near(text, hearing_date)
    if hearing_date:
        actions.append(
            _make_action(
                action_type="udienza_127_bis",
                title="Udienza audiovisiva ex art. 127-bis c.p.c.",
                due=hearing_date,
                source=source,
                document_id=document_id,
                tone="warning",
                priority="important",
                time_value=hearing_time,
                description=(
                    "Il decreto dispone la comparizione con collegamento audiovisivo. "
                    "Verificare stanza virtuale, deposito note operative e procura/difese prima dell'udienza."
                ),
            )
        )
        if re.search(r"(?:almeno\s+)?10\s+giorn[io]\s+prima.*(?:costituzion|costituirs)|(?:costituzion|costituirs).*?(?:almeno\s+)?10\s+giorn[io]\s+prima", text, flags=re.IGNORECASE | re.DOTALL):
            actions.append(
                _make_action(
                    action_type="costituzione_convenuto",
                    title="Verifica costituzione convenuto entro 10 giorni prima",
                    due=hearing_date - timedelta(days=10),
                    source=source,
                    document_id=document_id,
                    tone="info",
                    priority="normal",
                    description="Il decreto richiama il termine di costituzione almeno 10 giorni prima dell'udienza.",
                )
            )
    else:
        warnings.append(f"{source}: rilevato art. 127-bis c.p.c. ma non una data certa di udienza.")
    if re.search(r"5\s+giorn[io]\s+dalla\s+comunicazione|cinque\s+giorn[io]\s+dalla\s+comunicazione", text, flags=re.IGNORECASE):
        actions.append(
            _make_action(
                action_type="richiesta_presenza_127_bis",
                title="Valutare richiesta di udienza in presenza entro 5 giorni dalla comunicazione",
                due=None,
                source=source,
                document_id=document_id,
                tone="warning",
                priority="important",
                requires_communication_date=True,
                description="Il decreto collega il termine alla data di comunicazione: serve acquisire o confermare la comunicazione di cancelleria.",
            )
        )
    return actions, warnings


def _analyze_generic_procedural_text(text: str, *, source: str, document_id: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    folded = _fold(text)
    if "127 ter" in folded.replace("-", " ") or "127 bis" in folded.replace("-", " "):
        return actions
    for match in _DATE_RE.finditer(text):
        due = _parse_date(match.group(0))
        if not due:
            continue
        window = text[max(0, match.start() - 130) : min(len(text), match.end() + 130)]
        folded_window = _fold(window)
        if "udienza" in folded_window:
            action_type = "udienza_documento"
            title = "Udienza letta dai documenti del fascicolo"
            tone = "warning"
        elif any(token in folded_window for token in ("termine", "deposito", "costituzione", "notifica", "scadenza")):
            action_type = "termine_documento"
            title = "Termine processuale letto dai documenti del fascicolo"
            tone = "warning"
        else:
            continue
        if action_type == "udienza_documento":
            description = (
                "Data di udienza rilevata in un documento indicizzato del fascicolo; "
                "verificare rito, modalità di trattazione e adempimenti prima di aggiornare agenda o scadenziario."
            )
        else:
            description = (
                "Termine processuale rilevato in un documento indicizzato del fascicolo; "
                "verificare atto, parte onerata e decorrenza prima di registrare l'adempimento."
            )
        actions.append(
            _make_action(
                action_type=action_type,
                title=title,
                due=due,
                source=source,
                document_id=document_id,
                tone=tone,
                priority="important",
                description=description,
            )
        )
    return actions[:3]


def analyze_fascicolo_document_texts(
    fascicolo: Any,
    texts_by_document: dict[str, str],
    metadata_by_document: dict[str, dict[str, Any]] | None = None,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    metadata_by_document = metadata_by_document or {}
    procedural_actions: list[dict[str, Any]] = []
    review_actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    sources: list[dict[str, str]] = []
    for document_id, raw_text in (texts_by_document or {}).items():
        text = _text(raw_text)
        if not text:
            continue
        metadata = metadata_by_document.get(document_id) or {}
        source = _document_source(metadata, document_id)
        # Il testo proviene già da un documento associato a questo fascicolo. La
        # mancanza di R.G./parti nel testo non autorizza a scartarlo: impedisce
        # solo di trasformare automaticamente una data in termine processuale.
        sources.append({"documentId": document_id, "name": source})
        if not _contains_fascicolo_references(text, fascicolo):
            review_actions.append(
                _make_action(
                    action_type="verifica_collegamento_documento",
                    title="Verificare il documento collegato al fascicolo",
                    due=None,
                    source=source,
                    document_id=document_id,
                    tone="warning",
                    priority="important",
                    description=(
                        "Il file è collegato a questo fascicolo, ma il testo estratto non riporta "
                        "R.G. o parti sufficienti. Apri il documento e conferma se contiene un "
                        "termine, una data di udienza o un provvedimento da registrare."
                    ),
                )
            )
            warnings.append(f"{source}: collegamento da verificare, nessun termine è stato escluso automaticamente.")
            continue
        for analyzer in (_analyze_127_ter, _analyze_127_bis):
            found, local_warnings = analyzer(text, source=source, document_id=document_id)
            procedural_actions.extend(found)
            warnings.extend(local_warnings)
        procedural_actions.extend(_analyze_generic_procedural_text(text, source=source, document_id=document_id))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for action in [*procedural_actions, *review_actions]:
        key = (_text(action.get("type")), _text(action.get("dateIso")), _compact_key(action.get("source")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    deduped.sort(
        key=lambda action: (
            _text(action.get("dateIso")) == "",
            _text(action.get("dateIso")) or "9999-12-31",
            {"urgent": 0, "important": 1, "normal": 2}.get(_text(action.get("priority")), 3),
        )
    )
    upcoming = [
        item
        for item in deduped
        if (parsed := _parse_date(item.get("dateIso"))) and parsed >= today
    ]
    next_action = upcoming[0] if upcoming else (deduped[0] if deduped else None)
    procedural_count = sum(1 for action in deduped if _text(action.get("type")) != "verifica_collegamento_documento")
    review_count = len(deduped) - procedural_count
    status = "presidiato" if procedural_count else ("da_verificare" if sources or warnings else "non_disponibile")
    tone = "success" if status == "presidiato" else ("warning" if status == "da_verificare" else "neutral")
    if procedural_count:
        summary = f"{procedural_count} adempimenti letti dai documenti del fascicolo."
        if review_count:
            summary += f" {review_count} documenti collegati richiedono una verifica manuale prima di escludere ulteriori termini."
    elif review_count:
        summary = (
            f"{review_count} documenti collegati al fascicolo richiedono verifica: il testo indicizzato "
            "non riporta R.G. o parti sufficienti. Nessun termine è escluso finché l'avvocato non conferma il contenuto."
        )
    else:
        summary = "Nessun termine processuale leggibile nei documenti indicizzati del fascicolo."
    return {
        "status": status,
        "tone": tone,
        "summary": summary,
        "nextAction": next_action,
        "actions": deduped[:12],
        "warnings": warnings[:8],
        "sources": sources[:8],
    }


__all__ = [
    "analyze_fascicolo_document_texts",
    "duplicate_practice_groups",
    "normalise_practice_duplicate_key",
    "normalise_rg_parts",
]
