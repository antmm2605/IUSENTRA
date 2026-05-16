"""Ricerca unificata trasversale per le pagine Legal Intelligence e Ricerca legale."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(query: str) -> List[str]:
    return [token.lower() for token in _WORD_RE.findall(query or "") if len(token) >= 2]


def _haystack(values: Iterable[Any]) -> str:
    parts: List[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            parts.append(" ".join(str(item) for item in value if item))
            continue
        if isinstance(value, dict):
            parts.append(" ".join(str(item) for item in value.values() if item))
            continue
        parts.append(str(value))
    return " \n ".join(parts).lower()


def _matches(haystack: str, tokens: List[str]) -> bool:
    if not tokens:
        return False
    return all(token in haystack for token in tokens)


def _excerpt(haystack: str, tokens: List[str], limit: int = 180) -> str:
    if not tokens:
        return ""
    lowered = haystack.lower()
    for token in tokens:
        idx = lowered.find(token)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(haystack), idx + 120)
            snippet = haystack[start:end].strip()
            if start > 0:
                snippet = "… " + snippet
            if end < len(haystack):
                snippet = snippet + " …"
            if len(snippet) > limit:
                snippet = snippet[: limit - 1] + "…"
            return snippet
    return haystack[:limit]


def build_unified_search(
    *,
    query: str,
    snapshot: Dict[str, Any],
    news_items: Iterable[Dict[str, Any]],
    mediazione_rows: Iterable[Dict[str, Any]],
    daily_updates: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """Costruisce risultati raggruppati per tipo: fonti, normativa, news, organismi, aggiornamenti."""
    tokens = _tokens(query)
    results = {
        "query": (query or "").strip(),
        "tokens": tokens,
        "totale": 0,
        "fonti": [],
        "tabelle": [],
        "riferimenti": [],
        "news": [],
        "aggiornamenti": [],
        "organismi": [],
    }
    if not tokens:
        return results

    for row in snapshot.get("source_rows", []) or []:
        haystack = _haystack([row.get("nome"), row.get("area"), row.get("summary"), row.get("warning"), row.get("connector_kind"), row.get("formats"), row.get("detected_version"), row.get("detected_reference"), row.get("detected_package"), row.get("detected_status")])
        if _matches(haystack, tokens):
            results["fonti"].append({
                "id": row.get("id"),
                "titolo": row.get("nome"),
                "area": row.get("area"),
                "stato": row.get("freshness"),
                "ultimo_check": row.get("last_check"),
                "url_ufficiale": row.get("official_url"),
                "url_documento": row.get("detected_document_url"),
                "excerpt": _excerpt(haystack, tokens),
            })

    normative_tables = snapshot.get("normative_tables", {}) or {}
    for row in normative_tables.get("tabelle", []) or []:
        haystack = _haystack([row.get("title"), row.get("id"), row.get("category"), row.get("last_warning")])
        if _matches(haystack, tokens):
            results["tabelle"].append({
                "id": row.get("id"),
                "titolo": row.get("title"),
                "categoria": row.get("category"),
                "stato": row.get("sync_status"),
                "ultimo_sync": row.get("last_synced_at"),
                "excerpt": _excerpt(haystack, tokens),
            })

    for row in normative_tables.get("riferimenti_normativi", []) or []:
        haystack = _haystack([row.get("title"), row.get("article"), row.get("reference_code"), row.get("areas"), row.get("tipologie_labels")])
        if _matches(haystack, tokens):
            results["riferimenti"].append({
                "titolo": row.get("title"),
                "articolo": row.get("article") or row.get("reference_code"),
                "aree": row.get("areas") or [],
                "url": row.get("url"),
                "excerpt": _excerpt(haystack, tokens),
            })

    for item in news_items or []:
        haystack = _haystack([item.get("title"), item.get("short_summary"), item.get("content"), item.get("matter_name"), item.get("submatter_name"), item.get("news_type")])
        if _matches(haystack, tokens):
            results["news"].append({
                "slug": item.get("slug"),
                "titolo": item.get("title"),
                "materia": item.get("matter_name"),
                "tipo": item.get("news_type"),
                "data": item.get("published_at") or item.get("created_at"),
                "excerpt": _excerpt(haystack, tokens, limit=220),
            })

    for update in daily_updates or []:
        haystack = _haystack([update.get("title"), update.get("summary"), update.get("impact_areas")])
        if _matches(haystack, tokens):
            results["aggiornamenti"].append({
                "id": update.get("id"),
                "titolo": update.get("title"),
                "sintesi": update.get("summary"),
                "stato": update.get("status"),
                "rilevato": update.get("detected_at"),
                "aree": update.get("impact_areas") or [],
            })

    for row in mediazione_rows or []:
        haystack = _haystack([row.get("name"), row.get("address"), row.get("city"), row.get("province"), row.get("registration_number"), row.get("pec"), row.get("email"), row.get("phone"), row.get("type")])
        if _matches(haystack, tokens):
            results["organismi"].append({
                "numero": row.get("registration_number"),
                "nome": row.get("name"),
                "tipo": row.get("type"),
                "citta": row.get("city"),
                "provincia": row.get("province"),
                "pec": row.get("pec"),
                "email": row.get("email"),
                "excerpt": _excerpt(haystack, tokens),
            })

    for key in ("fonti", "tabelle", "riferimenti", "news", "aggiornamenti", "organismi"):
        results["totale"] += len(results[key])
    return results
