"""Consultazione live e governabile di fonti ufficiali web per Lex."""

from __future__ import annotations

import html
import re
import time
from typing import Any, Callable

import requests

from pct.legal_intelligence import FONTI_UFFICIALI, USER_AGENT, fonti_per_query

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_RSS_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_WHITESPACE_RE = re.compile(r"\s+")
_LIVE_CACHE_TTL_SECONDS = 900
_LIVE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_FALLBACK_DEFAULT_SOURCE_IDS = (
    "normattiva",
    "cassazione",
    "pst_giustizia",
    "agenzia_entrate",
)
_LIVE_WEB_KEYWORDS = (
    "deposit",
    "pct",
    "pst",
    "polisweb",
    "pdp",
    "pat",
    "reginde",
    "pec",
    "firma",
    "norm",
    "art",
    "decreto",
    "giuris",
    "sentenz",
    "cassaz",
    "costituz",
    "eur",
    "fattur",
    "sdi",
    "fiscal",
    "mediazion",
    "appalt",
    "lavor",
    "compens",
    "tariff",
)


def _clean_spaces(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _truncate(value: Any, limit: int = 260) -> str:
    text = _clean_spaces(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _strip_html(value: str) -> str:
    return html.unescape(_clean_spaces(_HTML_TAG_RE.sub(" ", value or "")))


def _extract_html_title(payload: str) -> str:
    for pattern in (_TITLE_RE, _H1_RE):
        match = pattern.search(payload or "")
        if match:
            text = _strip_html(match.group(1))
            if text:
                return text
    return ""


def _extract_html_description(payload: str) -> str:
    match = _META_DESC_RE.search(payload or "")
    if match:
        text = _strip_html(match.group(1))
        if text:
            return text
    stripped = _strip_html(payload or "")
    return _truncate(stripped, 280)


def _contains_live_keyword(text: str, keyword: str) -> bool:
    haystack = _clean_spaces(text).lower()
    needle = _clean_spaces(keyword).lower()
    if not haystack or not needle:
        return False
    if len(needle) <= 4 and needle.isalpha():
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


def _extract_rss_headline(payload: str) -> str:
    titles = [_strip_html(match.group(1)) for match in _RSS_TITLE_RE.finditer(payload or "")]
    titles = [title for title in titles if title]
    if len(titles) >= 2:
        return titles[1]
    return titles[0] if titles else ""


def _content_kind(content_type: str, url: str) -> str:
    kind = str(content_type or "").lower()
    final_url = str(url or "").lower()
    if "pdf" in kind or final_url.endswith(".pdf"):
        return "pdf"
    if "rss" in kind or "xml" in kind or final_url.endswith(".xml"):
        return "rss"
    return "html"


def _should_fetch_live_web(question: str) -> bool:
    text = _clean_spaces(question).lower()
    if not text:
        return False
    return any(_contains_live_keyword(text, keyword) for keyword in _LIVE_WEB_KEYWORDS)


def _select_live_source_ids(
    question: str,
    *,
    force: bool = False,
    explicit_source_ids: list[str] | None = None,
    limit: int = 2,
) -> list[str]:
    selected: list[str] = []

    def _push(source_id: str) -> None:
        if source_id in FONTI_UFFICIALI and source_id not in selected:
            selected.append(source_id)

    for source_id in list(explicit_source_ids or []):
        _push(source_id)
    if selected:
        return selected[:limit]

    if _should_fetch_live_web(question):
        for source_id in fonti_per_query(question):
            _push(source_id)
            if len(selected) >= limit:
                return selected[:limit]

    if force:
        for source_id in fonti_per_query(question):
            _push(source_id)
            if len(selected) >= limit:
                return selected[:limit]
        for source_id in _FALLBACK_DEFAULT_SOURCE_IDS:
            _push(source_id)
            if len(selected) >= limit:
                return selected[:limit]

    return selected[:limit]


def _request_source_snapshot(
    source_id: str,
    *,
    request_get: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    source = FONTI_UFFICIALI[source_id]
    cache_key = f"{source_id}:{source.monitor_url}"
    now = time.time()
    cached = _LIVE_CACHE.get(cache_key)
    if cached and now - cached[0] < _LIVE_CACHE_TTL_SECONDS:
        return dict(cached[1])

    fetch = request_get or requests.get
    response = fetch(
        source.monitor_url,
        headers={"User-Agent": USER_AGENT},
        timeout=4,
        allow_redirects=True,
    )
    status_code = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", source.monitor_url) or source.monitor_url)
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("content-type", "") or "")
    body = getattr(response, "text", "") or ""
    kind = _content_kind(content_type, final_url)

    if kind == "pdf":
        title = source.nome
        summary = f"Documento ufficiale PDF disponibile su {final_url}."
    elif kind == "rss":
        title = _extract_rss_headline(body) or source.nome
        summary = _truncate(_strip_html(body), 280)
    else:
        title = _extract_html_title(body) or source.nome
        summary = _extract_html_description(body)

    snapshot = {
        "source_id": source.id,
        "source_name": source.nome,
        "official_url": source.official_url,
        "monitor_url": source.monitor_url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "kind": kind,
        "title": _truncate(title or source.nome, 160),
        "summary": _truncate(summary or source.capability or source.notes, 320),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _LIVE_CACHE[cache_key] = (now, snapshot)
    return dict(snapshot)


def build_live_official_web_context(
    question: str,
    *,
    request_get: Callable[..., Any] | None = None,
    force: bool = False,
    explicit_source_ids: list[str] | None = None,
) -> dict[str, Any]:
    source_ids = _select_live_source_ids(
        question,
        force=force,
        explicit_source_ids=explicit_source_ids,
        limit=2,
    )
    if not source_ids:
        return {"lines": [], "sources": [], "citations": [], "source_ids": []}

    lines = [
        "Verifica live web: Lex puo' integrare il contesto con fonti ufficiali aggiornate quando il contesto interno non basta.",
    ]
    sources: list[dict[str, Any]] = []
    citations: list[str] = []

    for source_id in source_ids:
        source = FONTI_UFFICIALI[source_id]
        try:
            snapshot = _request_source_snapshot(source_id, request_get=request_get)
            checked_at = snapshot.get("checked_at", "")[:19].replace("T", " ")
            lines.append(
                f"{source.nome}: risorsa live raggiunta ({checked_at}), titolo '{snapshot.get('title')}', URL {snapshot.get('final_url')}."
            )
            citation = f"Fonte ufficiale live - {source.nome}"
            sources.append(
                {
                    "id": f"live-web:{source.id}",
                    "title": source.nome,
                    "citation": citation,
                    "text": _truncate(
                        f"{snapshot.get('title')}. {snapshot.get('summary')} URL ufficiale: {snapshot.get('final_url')}.",
                        420,
                    ),
                }
            )
            citations.append(citation)
        except Exception as exc:
            lines.append(
                f"{source.nome}: verifica live non disponibile in questo momento ({_truncate(str(exc), 140)})."
            )
            sources.append(
                {
                    "id": f"live-web:{source.id}",
                    "title": source.nome,
                    "citation": f"Fonte ufficiale live - {source.nome}",
                    "text": _truncate(
                        f"Verifica live temporaneamente non disponibile. URL ufficiale: {source.official_url}. Nota: {source.capability or source.notes}",
                        420,
                    ),
                }
            )
            citations.append(f"Fonte ufficiale live - {source.nome}")

    return {
        "lines": lines,
        "sources": sources,
        "citations": citations,
        "source_ids": source_ids,
    }
