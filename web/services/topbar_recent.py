"""Recenti operativi esposti dalla top bar React."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from flask import session

from web.helpers import get_clienti, get_fascicoli
from web.services.topbar_operational import ROME_TZ, TopbarApiError, _clean_text, _react_href, _require_any_permission


def recent_payload(user: Any) -> dict[str, Any]:
    _require_any_permission(user, ["fascicoli.leggi", "clienti.leggi"])
    raw = session.get("recenti", [])
    items: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        href = _react_href(item.get("url") or item.get("href") or "") or ""
        title = _clean_text(item.get("titolo") or item.get("title") or "")
        entity_type = _recent_type_to_api(item.get("tipo") or item.get("entityType"))
        entity_id = _clean_text(item.get("id") or item.get("entityId") or "")
        if not href or not title:
            continue
        items.append(
            {
                "id": entity_id or href,
                "type": entity_type,
                "title": title,
                "subtitle": _clean_text(item.get("subtitle") or item.get("sottotitolo") or "") or None,
                "href": href,
                "lastAccessedAt": _clean_text(item.get("lastAccessedAt") or item.get("ultimo_accesso") or "") or None,
            }
        )
    deduped_items = _dedupe_recent_items(items)[:10]
    searches = _recent_searches()[:8]
    return {"ok": True, "items": deduped_items, "searches": searches, "totalCount": len(deduped_items) + len(searches)}


def track_recent_payload(user: Any, entity_type: str, entity_id: str) -> dict[str, Any]:
    _require_any_permission(user, ["fascicoli.leggi", "clienti.leggi"])
    etype = _recent_type_to_api(entity_type)
    eid = _clean_text(entity_id, limit=120)
    if not eid:
        raise TopbarApiError("entityId obbligatorio.", 400)
    resolved = _resolve_recent_entity(etype, eid)
    if not resolved:
        payload = recent_payload(user)
        payload.update({"tracked": False, "message": "Elemento non disponibile nei dati dello studio."})
        return payload
    current = session.get("recenti", [])
    rows = [row for row in current if isinstance(row, dict)] if isinstance(current, list) else []
    rows = [row for row in rows if not (_recent_type_to_api(row.get("tipo")) == etype and str(row.get("id")) == eid)]
    rows.insert(0, resolved)
    session["recenti"] = rows[:10]
    session.modified = True
    return recent_payload(user)


def track_recent_search_payload(user: Any, query: str, total: Any = None) -> dict[str, Any]:
    _require_any_permission(
        user,
        ["fascicoli.leggi", "clienti.leggi", "agenda.leggi", "scadenziario.leggi", "messaggi.leggi"],
    )
    clean_query = _clean_text(query, limit=120)
    if len(clean_query) < 2:
        raise TopbarApiError("Inserisci almeno 2 caratteri.", 400)
    try:
        result_count = max(0, int(total or 0))
    except (TypeError, ValueError):
        result_count = 0
    now = datetime.now(ROME_TZ).isoformat(timespec="seconds")
    href = "/global-search?" + urlencode({"q": clean_query})
    current = _recent_searches()
    dedupe_key = clean_query.casefold()
    rows = [row for row in current if str(row.get("query") or "").casefold() != dedupe_key]
    rows.insert(
        0,
        {
            "id": f"search:{dedupe_key}",
            "query": clean_query,
            "title": clean_query,
            "subtitle": f"{result_count} risultati" if result_count else "Ricerca Studio",
            "href": href,
            "searchedAt": now,
            "total": result_count,
        },
    )
    session["ricerche_recenti"] = rows[:8]
    session.modified = True
    return recent_payload(user)


def _recent_type_to_api(value: Any) -> str:
    text = str(value or "").strip().lower()
    return {
        "fascicolo": "case",
        "fascicoli": "case",
        "case": "case",
        "matter": "matter",
        "pratica": "matter",
        "cliente": "client",
        "client": "client",
        "documento": "document",
        "document": "document",
    }.get(text, "matter")


def _dedupe_recent_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            _clean_text(item.get("type"), limit=80).lower(),
            _clean_text(item.get("id"), limit=180).lower(),
            _clean_text(item.get("href"), limit=500).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _recent_searches() -> list[dict[str, Any]]:
    raw = session.get("ricerche_recenti", [])
    rows = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        query = _clean_text(row.get("query") or row.get("title") or "", limit=120)
        if len(query) < 2:
            continue
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            total = max(0, int(row.get("total") or 0))
        except (TypeError, ValueError):
            total = 0
        result.append(
            {
                "id": _clean_text(row.get("id") or f"search:{key}", limit=160),
                "query": query,
                "title": _clean_text(row.get("title") or query, limit=160),
                "subtitle": _clean_text(row.get("subtitle") or (f"{total} risultati" if total else "Ricerca Studio"), limit=160),
                "href": _react_href(row.get("href") or ("/global-search?" + urlencode({"q": query}))) or "/global-search",
                "searchedAt": _clean_text(row.get("searchedAt") or row.get("searched_at") or "", limit=80) or None,
                "total": total,
            }
        )
    return result


def _resolve_recent_entity(entity_type: str, entity_id: str) -> dict[str, Any] | None:
    now = datetime.now(ROME_TZ).isoformat(timespec="seconds")
    if entity_type in {"case", "matter"}:
        fascicolo = get_fascicoli().get(entity_id)
        if not fascicolo:
            return None
        return {
            "tipo": "fascicolo",
            "id": fascicolo.id,
            "titolo": _clean_text(fascicolo.titolo or fascicolo.numero),
            "url": f"/fascicoli/{fascicolo.id}",
            "icona": "bi-folder2-open",
            "lastAccessedAt": now,
            "subtitle": _clean_text(getattr(fascicolo, "nome_cliente", "")) or None,
        }
    if entity_type == "client":
        cliente = get_clienti().get(entity_id)
        if not cliente:
            return None
        return {
            "tipo": "cliente",
            "id": cliente.id,
            "titolo": _clean_text(cliente.nome_completo),
            "url": f"/clienti/{cliente.id}/cartella",
            "icona": "bi-person-vcard",
            "lastAccessedAt": now,
            "subtitle": _clean_text(getattr(cliente, "identificativo_fiscale", "")) or None,
        }
    if entity_type == "document":
        for fascicolo in get_fascicoli().tutti(archiviati=True):
            for document in getattr(fascicolo, "documenti", []) or []:
                if getattr(document, "id", "") != entity_id:
                    continue
                title = _clean_text(getattr(document, "nome_file", "") or getattr(document, "titolo", "Documento"))
                return {
                    "tipo": "documento",
                    "id": entity_id,
                    "titolo": title,
                    "url": f"/fascicoli/{fascicolo.id}/documenti/{entity_id}/editor",
                    "icona": "bi-file-earmark-text",
                    "lastAccessedAt": now,
                    "subtitle": _clean_text(fascicolo.titolo),
                }
    return None
