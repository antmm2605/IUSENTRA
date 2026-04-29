"""Bridge dati per la pagina Fascicoli della shell React.

Il bridge normalizza i repository esistenti senza introdurre una source of truth
frontend e resta in sola lettura durante la migrazione progressiva.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Callable

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or fallback).split())
    return text


def _short(value: Any, limit: int = 110) -> str:
    text = _text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            return datetime.fromisoformat(sample).date()
        except ValueError:
            continue
    return None


def _format_date(value: Any) -> str:
    parsed = _parse_date(value)
    if not parsed:
        return ""
    today = date.today()
    if parsed == today:
        return "oggi"
    if parsed == today + _delta(1):
        return "domani"
    if parsed == today - _delta(1):
        return "ieri"
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]}"
    return parsed.strftime("%d/%m/%Y")


def _delta(days: int):
    from datetime import timedelta

    return timedelta(days=days)


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _matter_list(repo: Any) -> list[Any]:
    items: list[Any] = []
    seen: set[str] = set()
    candidates: list[Any] = []
    for getter in (
        lambda: repo.tutti(archiviati=False),
        lambda: repo.tutti(archiviati=True),
        lambda: repo.tutti(),
    ):
        value = _safe("fascicoli", getter, [])
        if isinstance(value, list):
            candidates.extend(value)
    for item in candidates:
        item_id = _text(getattr(item, "id", "")) or _text(getattr(item, "numero", ""))
        if item_id in seen:
            continue
        seen.add(item_id)
        items.append(item)
    return items


def _status(fascicolo: Any, next_deadline: Any | None) -> str:
    raw = _enum_value(getattr(fascicolo, "stato", "")).lower()
    archiviato = bool(getattr(fascicolo, "archiviato", False) or getattr(fascicolo, "is_archived", False))
    if archiviato or "archiv" in raw:
        return "archiviato"
    if "sosp" in raw:
        return "sospeso"
    if "defin" in raw or "chius" in raw:
        return "definito"
    if "corso" in raw:
        return "in_corso"
    if not next_deadline and ("def" in raw or bool(getattr(fascicolo, "definito", False))):
        return "da_archiviare"
    return "aperto"


def _type(fascicolo: Any) -> str:
    raw = " ".join([
        _enum_value(getattr(fascicolo, "tipo", "")),
        _text(getattr(fascicolo, "materia", "")),
        _text(getattr(fascicolo, "rg_completo", "")),
    ]).lower()
    if "civ" in raw:
        return "civile"
    if "pen" in raw or "rgnr" in raw:
        return "penale"
    if "amm" in raw or "tar" in raw or "consiglio" in raw:
        return "amministrativo"
    if "trib" in raw or "sigit" in raw or "ptt" in raw:
        return "tributario"
    if "stragiud" in raw or "mediazione" in raw or "negoziazione" in raw:
        return "stragiudiziale"
    return "altro"


def _tone(status: str) -> str:
    return {
        "aperto": "primary",
        "in_corso": "success",
        "definito": "info",
        "da_archiviare": "warning",
        "archiviato": "neutral",
        "sospeso": "orange",
    }.get(status, "neutral")


def _rg(fascicolo: Any) -> str:
    complete = _text(getattr(fascicolo, "rg_completo", ""))
    if complete:
        return complete
    numero = _text(getattr(fascicolo, "numero_rg", ""))
    anno = _text(getattr(fascicolo, "anno_rg", ""))
    if numero and anno:
        return f"RG {numero}/{anno}"
    return numero or _text(getattr(fascicolo, "numero", "")) or "n.d."


def _documents_count(fascicolo: Any) -> int:
    for attr in ("numero_documenti", "documenti_count", "docs_count", "allegati_count"):
        value = getattr(fascicolo, attr, None)
        if isinstance(value, int):
            return max(0, value)
    documents = getattr(fascicolo, "documenti", None)
    if isinstance(documents, list):
        return len(documents)
    return 0


def _alerts_count(fascicolo: Any, deadlines: list[Any]) -> int:
    explicit = getattr(fascicolo, "alert", None) or getattr(fascicolo, "criticita", None)
    if isinstance(explicit, int):
        return max(0, explicit)
    today = date.today()
    count = 0
    for deadline in deadlines:
        due = _parse_date(getattr(deadline, "data_scadenza", "") or getattr(deadline, "data", ""))
        priority = _enum_value(getattr(deadline, "priorita", "")).lower()
        if due and due <= today + _delta(7):
            count += 1
        elif "alta" in priority or "crit" in priority:
            count += 1
    return count


def _deadline_groups(scadenziario: Any) -> dict[str, list[Any]]:
    deadlines = _safe("scadenziario", lambda: scadenziario.tutte(solo_aperte=True), [])
    groups: dict[str, list[Any]] = defaultdict(list)
    for item in deadlines:
        fascicolo_id = _text(getattr(item, "id_fascicolo", ""))
        if fascicolo_id:
            groups[fascicolo_id].append(item)
    for values in groups.values():
        values.sort(key=lambda item: _parse_date(getattr(item, "data_scadenza", "") or getattr(item, "data", "")) or date.max)
    return groups


def _facet_rows(items: list[dict[str, Any]], key: str, labels: dict[str, str], all_label: str) -> list[dict[str, Any]]:
    rows = [{"value": "tutti", "label": all_label, "count": len(items)}]
    for value, label in labels.items():
        rows.append({"value": value, "label": label, "count": sum(1 for item in items if item.get(key) == value)})
    return rows


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    today = date.today()
    horizon = today + _delta(30)
    deadlines30 = 0
    for item in items:
        due = _parse_date(item.get("nextDeadlineIso"))
        if due and today <= due <= horizon:
            deadlines30 += 1
    return {
        "total": len(items),
        "active": sum(1 for item in items if item.get("status") != "archiviato"),
        "inProgress": sum(1 for item in items if item.get("status") == "in_corso"),
        "toArchive": sum(1 for item in items if item.get("status") in {"definito", "da_archiviare"}),
        "archived": sum(1 for item in items if item.get("status") == "archiviato"),
        "deadlines30": deadlines30,
        "documentsToClassify": sum(int(item.get("alerts") or 0) for item in items),
        "unreadCommunications": sum(int(item.get("unreadCommunications") or 0) for item in items),
    }


def build_react_fascicoli_payload(*, get_fascicoli: Callable[[], Any], get_scadenziario: Callable[[], Any]) -> dict[str, Any]:
    fascicoli_repo = get_fascicoli()
    scadenziario = get_scadenziario()
    groups = _deadline_groups(scadenziario)
    items: list[dict[str, Any]] = []
    for index, fascicolo in enumerate(_matter_list(fascicoli_repo)):
        item_id = _text(getattr(fascicolo, "id", "")) or f"fascicolo-{index}"
        deadlines = groups.get(item_id, [])
        next_deadline = deadlines[0] if deadlines else None
        next_deadline_iso = ""
        if next_deadline:
            due = _parse_date(getattr(next_deadline, "data_scadenza", "") or getattr(next_deadline, "data", ""))
            next_deadline_iso = due.isoformat() if due else ""
        status = _status(fascicolo, next_deadline)
        title = _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "oggetto", "")) or "Fascicolo"
        rg = _rg(fascicolo)
        items.append(
            {
                "id": item_id,
                "ref": rg,
                "internalRef": _text(getattr(fascicolo, "numero", "")) or _text(getattr(fascicolo, "codice_interno", "")) or "n.d.",
                "title": _short(title, 120),
                "subtitle": _short(getattr(fascicolo, "descrizione", "") or getattr(fascicolo, "materia", "") or getattr(fascicolo, "tribunale", ""), 120),
                "type": _type(fascicolo),
                "client": _text(getattr(fascicolo, "nome_cliente", "")) or _text(getattr(fascicolo, "cliente", "")) or "Cliente non collegato",
                "court": _text(getattr(fascicolo, "tribunale", "")) or _text(getattr(fascicolo, "ufficio", "")) or "Ufficio non impostato",
                "rg": rg,
                "nextDeadline": _format_date(next_deadline_iso) or "n.d.",
                "nextDeadlineIso": next_deadline_iso,
                "status": status,
                "documents": _documents_count(fascicolo),
                "unreadCommunications": int(getattr(fascicolo, "comunicazioni_non_lette", 0) or 0),
                "alerts": _alerts_count(fascicolo, deadlines),
                "href": f"/fascicoli/{item_id}",
                "editHref": f"/fascicoli/{item_id}/modifica",
                "tone": _tone(status),
            }
        )
    type_labels = {
        "civile": "Civile",
        "penale": "Penale",
        "amministrativo": "Amministrativo",
        "tributario": "Tributario",
        "stragiudiziale": "Stragiudiziale",
        "altro": "Altro",
    }
    status_labels = {
        "aperto": "Aperto",
        "in_corso": "In corso",
        "definito": "Definito",
        "da_archiviare": "Da archiviare",
        "archiviato": "Archiviato",
        "sospeso": "Sospeso",
    }
    return {
        "source": "repository_reali",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "contracts": {"mock_fallback": False, "read_only": True},
        "summary": _summary(items),
        "items": items,
        "facets": {
            "types": _facet_rows(items, "type", type_labels, "Tutti i tipi"),
            "statuses": _facet_rows(items, "status", status_labels, "Tutti gli stati"),
        },
    }
