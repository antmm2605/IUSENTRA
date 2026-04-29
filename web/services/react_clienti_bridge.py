"""Bridge dati per la pagina Anagrafica Clienti della shell React.

Normalizza i repository esistenti senza introdurre una seconda source of truth
frontend. La pagina resta in sola lettura durante la migrazione progressiva.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any, Callable


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value or fallback).split())


def _short(value: Any, limit: int = 120) -> str:
    text = _text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


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


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _status(cliente: Any) -> str:
    raw = _enum_value(getattr(cliente, "stato", "")).lower()
    if "archiv" in raw:
        return "archiviato"
    if "potenzial" in raw:
        return "potenziale"
    if "inatt" in raw:
        return "inattivo"
    return "attivo"


def _type(cliente: Any) -> str:
    raw = _enum_value(getattr(cliente, "tipo", "")).lower()
    if "giurid" in raw or "societ" in raw or raw == "pg":
        return "pg"
    return "pf"


def _tone(status: str) -> str:
    return {"attivo": "success", "potenziale": "warning", "archiviato": "neutral", "inattivo": "orange"}.get(status, "neutral")


def _recapiti(cliente: Any) -> tuple[str, str, str]:
    recapiti = getattr(cliente, "recapiti", None)
    phone = _text(getattr(recapiti, "cellulare", "") or getattr(recapiti, "telefono", ""))
    email = _text(getattr(recapiti, "email", ""))
    pec = _text(getattr(recapiti, "pec", ""))
    return phone, email, pec


def _fiscal_id(cliente: Any) -> str:
    return _text(getattr(cliente, "identificativo_fiscale", "") or getattr(cliente, "codice_fiscale", "") or getattr(cliente, "partita_iva", ""))


def _document_expired(cliente: Any) -> bool:
    documento = getattr(cliente, "documento", None)
    try:
        explicit = getattr(documento, "scaduto", None)
        if isinstance(explicit, bool):
            return explicit
    except Exception:
        explicit = None
    due = _parse_date(getattr(documento, "data_scadenza", ""))
    return bool(due and due < date.today())


def _cliente_key(value: Any) -> str:
    return _text(value).lower()


def _matter_groups(fascicoli_repo: Any) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    by_client_id: dict[str, list[Any]] = defaultdict(list)
    by_client_name: dict[str, list[Any]] = defaultdict(list)
    seen: set[str] = set()
    candidates: list[Any] = []
    for getter in (lambda: fascicoli_repo.tutti(archiviati=False), lambda: fascicoli_repo.tutti(archiviati=True), lambda: fascicoli_repo.tutti()):
        value = _safe("fascicoli", getter, [])
        if isinstance(value, list):
            candidates.extend(value)
    for item in candidates:
        item_id = _text(getattr(item, "id", "")) or _text(getattr(item, "numero", ""))
        if item_id in seen:
            continue
        seen.add(item_id)
        id_cliente = _text(getattr(item, "id_cliente", "") or getattr(item, "cliente_id", ""))
        nome_cliente = _cliente_key(getattr(item, "nome_cliente", "") or getattr(item, "cliente", ""))
        if id_cliente:
            by_client_id[id_cliente].append(item)
        if nome_cliente:
            by_client_name[nome_cliente].append(item)
    return by_client_id, by_client_name


def _matters_for(cliente: Any, by_client_id: dict[str, list[Any]], by_client_name: dict[str, list[Any]]) -> list[Any]:
    cliente_id = _text(getattr(cliente, "id", ""))
    nome = _cliente_key(getattr(cliente, "nome_completo", ""))
    items = list(by_client_id.get(cliente_id, []))
    known = {_text(getattr(item, "id", "")) for item in items}
    for item in by_client_name.get(nome, []):
        item_id = _text(getattr(item, "id", ""))
        if item_id not in known:
            items.append(item)
            known.add(item_id)
    return items


def _active_matter_count(items: list[Any]) -> int:
    total = 0
    for item in items:
        raw = _enum_value(getattr(item, "stato", "")).lower()
        archived = bool(getattr(item, "archiviato", False) or getattr(item, "is_archived", False) or "archiv" in raw)
        if not archived:
            total += 1
    return total


def _missing_fields(cliente: Any) -> list[str]:
    explicit = getattr(cliente, "campi_mancanti_per_conferimento", []) or []
    if isinstance(explicit, list):
        return [_text(item) for item in explicit if _text(item)]
    return []


def _subtitle(cliente: Any) -> str:
    parts = [_text(getattr(cliente, "provenienza", "")), _text(getattr(cliente, "forma_giuridica", "")), _short(getattr(cliente, "note", ""), 70)]
    return " - ".join(part for part in parts if part)


def _facet_rows(items: list[dict[str, Any]], key: str, labels: dict[str, str], all_label: str) -> list[dict[str, Any]]:
    rows = [{"value": "tutti", "label": all_label, "count": len(items)}]
    for value, label in labels.items():
        rows.append({"value": value, "label": label, "count": sum(1 for item in items if item.get(key) == value)})
    return rows


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    statuses = Counter(item.get("status") for item in items)
    return {
        "total": len(items),
        "active": int(statuses.get("attivo", 0)),
        "potential": int(statuses.get("potenziale", 0)),
        "archived": int(statuses.get("archiviato", 0)),
        "withMatters": sum(1 for item in items if int(item.get("matters") or 0) > 0),
        "incomplete": sum(1 for item in items if item.get("missingFields")),
        "withoutContacts": sum(1 for item in items if not (item.get("email") or item.get("phone") or item.get("pec"))),
        "privacyMissing": sum(1 for item in items if not item.get("privacyOk")),
        "documentsExpired": sum(1 for item in items if item.get("documentExpired")),
    }


def build_react_clienti_payload(*, get_clienti: Callable[[], Any], get_fascicoli: Callable[[], Any]) -> dict[str, Any]:
    clienti_repo = get_clienti()
    fascicoli_repo = get_fascicoli()
    by_client_id, by_client_name = _matter_groups(fascicoli_repo)
    clienti = _safe("clienti", lambda: clienti_repo.tutti(), [])
    items: list[dict[str, Any]] = []

    for index, cliente in enumerate(clienti):
        item_id = _text(getattr(cliente, "id", "")) or f"cliente-{index}"
        status = _status(cliente)
        tipo = _type(cliente)
        phone, email, pec = _recapiti(cliente)
        linked_matters = _matters_for(cliente, by_client_id, by_client_name)
        procedimenti = getattr(cliente, "procedimenti", []) or []
        matters_count = max(len(linked_matters), len(procedimenti) if isinstance(procedimenti, list) else 0)
        active_count = max(_active_matter_count(linked_matters), len(getattr(cliente, "procedimenti_attivi", []) or []))
        tags = getattr(cliente, "tag", []) or []
        if not isinstance(tags, list):
            tags = []
        items.append({
            "id": item_id,
            "name": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
            "subtitle": _subtitle(cliente),
            "type": tipo,
            "fiscalId": _fiscal_id(cliente) or "-",
            "email": email,
            "phone": phone,
            "pec": pec,
            "attorney": _text(getattr(cliente, "avvocato_referente", "")) or "-",
            "matters": matters_count,
            "activeMatters": active_count,
            "status": status,
            "missingFields": _missing_fields(cliente),
            "privacyOk": bool(getattr(cliente, "consenso_trattamento", False)),
            "documentExpired": _document_expired(cliente),
            "tags": [_text(tag) for tag in tags if _text(tag)],
            "lastUpdated": _text(getattr(cliente, "modificato_il", "") or getattr(cliente, "creato_il", "")),
            "href": f"/clienti/{item_id}",
            "editHref": f"/clienti/{item_id}/modifica",
            "folderHref": f"/clienti/{item_id}/cartella",
            "tone": _tone(status),
        })

    type_labels = {"pf": "Persone fisiche", "pg": "Persone giuridiche"}
    status_labels = {"attivo": "Attivi", "potenziale": "Potenziali", "archiviato": "Archiviati", "inattivo": "Inattivi"}
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": True},
        "summary": _summary(items),
        "items": items,
        "facets": {"types": _facet_rows(items, "type", type_labels, "Tutti i tipi"), "statuses": _facet_rows(items, "status", status_labels, "Tutti gli stati")},
    }
