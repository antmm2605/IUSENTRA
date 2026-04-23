"""Ricerca web governata di Lex su domini ufficiali riconosciuti."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from lxml import html as lxml_html

from lex.research.source_registry import get_source_registry
from pct.legal_intelligence import FONTI_UFFICIALI, USER_AGENT, fonti_per_query

DEFAULT_WEB_SOURCE_IDS: tuple[str, ...] = (
    "normattiva",
    "gazzetta_ufficiale",
    "pst_giustizia",
    "cassazione",
    "corte_costituzionale",
    "agenzia_entrate",
)

_OFFICIAL_SEARCH_URL = "https://html.duckduckgo.com/html/"
_SEARCH_CACHE_TTL_SECONDS = 900
_SEARCH_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}

_SOURCE_DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "normattiva": ("normattiva.it", "dati.normattiva.it"),
    "gazzetta_ufficiale": ("gazzettaufficiale.it",),
    "pst_giustizia": ("pst.giustizia.it", "giustizia.it"),
    "pst_servizi_web": ("pst.giustizia.it",),
    "pst_download": ("pst.giustizia.it",),
    "pst_pdp_specifiche": ("pst.giustizia.it",),
    "cassazione": ("cortedicassazione.it",),
    "corte_costituzionale": ("cortecostituzionale.it",),
    "giustizia_amministrativa": ("giustizia-amministrativa.it",),
    "eur_lex": ("eur-lex.europa.eu",),
    "curia": ("curia.europa.eu",),
    "cedu": ("echr.coe.int", "hudoc.echr.coe.int"),
    "agenzia_entrate": ("agenziaentrate.gov.it", "agenziaentrate.it"),
    "cnf": ("consiglionazionaleforense.it",),
    "registro_mediazione": ("giustizia.it", "mediazione.giustizia.it"),
}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_domain(value: str) -> str:
    host = str(value or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _extra_domains() -> list[str]:
    raw = os.getenv("PCT_LEX_OFFICIAL_EXTRA_DOMAINS", "")
    domains: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        domain = _normalize_domain(item)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains


def _domains_for_source(source_id: str) -> list[str]:
    registry = get_source_registry()
    source = FONTI_UFFICIALI.get(str(source_id or "").strip())
    registry_source = registry.get(source_id)
    domains: list[str] = []
    seen: set[str] = set()

    def _push(value: str) -> None:
        domain = _normalize_domain(urlparse(str(value or "").strip()).netloc or value)
        if not domain or domain in seen:
            return
        seen.add(domain)
        domains.append(domain)

    if source:
        _push(source.official_url)
        _push(source.monitor_url)
    if registry_source and registry_source.supports_public_web_search:
        _push(registry_source.base_url)
        for value in registry_source.entrypoints.values():
            _push(value)
    for alias in _SOURCE_DOMAIN_ALIASES.get(str(source_id or "").strip(), ()):
        _push(alias)
    return domains


def resolve_official_source_ids_for_query(
    question: str,
    *,
    explicit_source_ids: list[str] | None = None,
    limit: int = 4,
) -> list[str]:
    registry = get_source_registry()
    if isinstance(explicit_source_ids, str):
        explicit_values = [explicit_source_ids]
    else:
        explicit_values = list(explicit_source_ids or [])
    selected: list[str] = []
    seen: set[str] = set()

    def _push(source_id: str) -> None:
        normalized = str(source_id or "").strip()
        if not normalized or normalized in seen:
            return
        if normalized not in FONTI_UFFICIALI and registry.get(normalized) is None:
            return
        seen.add(normalized)
        selected.append(normalized)

    for source_id in explicit_values:
        _push(source_id)
        if len(selected) >= limit:
            return selected[:limit]

    for source_id in fonti_per_query(question):
        _push(source_id)
        if len(selected) >= limit:
            return selected[:limit]

    for source in registry.resolve_requested_sources(question, explicit_source_ids=explicit_values, limit=limit):
        _push(source.key)
        if len(selected) >= limit:
            return selected[:limit]

    for source_id in DEFAULT_WEB_SOURCE_IDS:
        _push(source_id)
        if len(selected) >= limit:
            return selected[:limit]
    return selected[:limit]


def build_source_registry_context(
    question: str,
    *,
    explicit_source_ids: list[str] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    registry = get_source_registry()
    rows = registry.resolve_requested_sources(
        question,
        explicit_source_ids=list(explicit_source_ids or []),
        limit=limit,
    )
    summaries = [row.to_summary_dict() for row in rows]
    present_keys = {row["key"] for row in summaries}
    selected_source_ids = resolve_official_source_ids_for_query(
        question,
        explicit_source_ids=list(explicit_source_ids or []),
        limit=limit,
    )
    searchable: list[dict[str, Any]] = []
    partner: list[dict[str, Any]] = []
    restricted: list[dict[str, Any]] = []
    credentialed: list[dict[str, Any]] = []
    for row in summaries:
        if row["supports_public_web_search"]:
            searchable.append(row)
        if row["partner"]:
            partner.append(row)
        if row["restricted"]:
            restricted.append(row)
        if row["requires_credentials"]:
            credentialed.append(row)
    return {
        "requested_sources": summaries,
        "selected_source_ids": selected_source_ids,
        "searchable_sources": searchable,
        "partner_sources": partner,
        "restricted_sources": restricted,
        "credentialed_sources": credentialed,
        "matched_keys": sorted(present_keys),
    }


def _extract_result_url(raw_url: str) -> str:
    parsed = urlparse(str(raw_url or "").strip())
    if parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg", [])
        if uddg:
            return unquote(uddg[0])
    return str(raw_url or "").strip()


def _is_allowed_result(url: str, allowed_domain: str) -> bool:
    host = _normalize_domain(urlparse(str(url or "").strip()).netloc)
    domain = _normalize_domain(allowed_domain)
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def _match_source_id_for_domain(source_ids: list[str], domain: str) -> str:
    normalized = _normalize_domain(domain)
    for source_id in source_ids:
        for candidate in _domains_for_source(source_id):
            if normalized == candidate or normalized.endswith("." + candidate):
                return str(source_id or "").strip()
    return ""


def _cache_key(question: str, source_ids: list[str], limit_results: int) -> str:
    fingerprint = "|".join(
        [
            _clean_spaces(question).lower(),
            ",".join(sorted(str(item or "").strip() for item in source_ids)),
            str(int(limit_results or 0)),
        ]
    )
    return hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()


def search_recognized_official_web(
    question: str,
    *,
    source_ids: list[str] | None = None,
    request_get: Callable[..., Any] | None = None,
    limit_results: int = 4,
) -> list[dict[str, Any]]:
    registry = get_source_registry()
    query = _clean_spaces(question)
    selected_source_ids = resolve_official_source_ids_for_query(
        query,
        explicit_source_ids=source_ids,
        limit=max(int(limit_results or 0), 4),
    )
    if not query or not selected_source_ids or int(limit_results or 0) <= 0:
        return []

    cache_key = _cache_key(query, selected_source_ids, limit_results)
    cached = _SEARCH_CACHE.get(cache_key)
    now = time.time()
    if cached and now - cached[0] < _SEARCH_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    fetch = request_get
    if fetch is None:
        import requests

        fetch = requests.get

    candidate_domains: list[str] = []
    seen_domains: set[str] = set()
    for source_id in selected_source_ids:
        for domain in _domains_for_source(source_id):
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            candidate_domains.append(domain)
    for domain in _extra_domains():
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        candidate_domains.append(domain)

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for domain in candidate_domains[:8]:
        try:
            response = fetch(
                _OFFICIAL_SEARCH_URL,
                params={"q": f"site:{domain} {query}"},
                headers={"User-Agent": USER_AGENT},
                timeout=5,
            )
        except Exception:
            continue

        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            continue

        body = str(getattr(response, "text", "") or "")
        if not body.strip():
            continue

        try:
            document = lxml_html.fromstring(body)
        except Exception:
            continue

        nodes = document.xpath("//div[contains(@class, 'result')]")
        if not nodes:
            nodes = document.xpath("//article")

        for node in nodes:
            link_nodes = node.xpath(".//a[contains(@class, 'result__a')] | .//h2//a | .//a[@href]")
            if not link_nodes:
                continue
            link = link_nodes[0]
            url = _extract_result_url(link.get("href") or "")
            if not _is_allowed_result(url, domain) or url in seen_urls:
                continue
            seen_urls.add(url)

            title = _clean_spaces(link.text_content())
            snippet_nodes = node.xpath(
                ".//*[contains(@class, 'result__snippet')] | "
                ".//*[contains(@class, 'snippet')] | "
                ".//a[contains(@class, 'result__snippet')]"
            )
            snippet = _clean_spaces(snippet_nodes[0].text_content()) if snippet_nodes else ""
            matched_source_id = _match_source_id_for_domain(selected_source_ids, domain)
            source = FONTI_UFFICIALI.get(matched_source_id)
            registry_source = registry.get(matched_source_id) or registry.find_by_host(domain)
            results.append(
                {
                    "id": f"live-web-search:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}",
                    "title": title or (source.nome if source else (registry_source.label if registry_source else domain)),
                    "url": url,
                    "official_url": source.official_url if source else (registry_source.base_url if registry_source else url),
                    "domain": _normalize_domain(urlparse(url).netloc),
                    "source_id": matched_source_id or (registry_source.key if registry_source else domain),
                    "source_name": source.nome if source else (registry_source.label if registry_source else domain),
                    "kind": "pdf" if str(url).lower().endswith(".pdf") else "html",
                    "excerpt": snippet,
                    "source_access_status": registry_source.status if registry_source else "",
                    "source_access_label": registry_source.access_label if registry_source else "",
                    "source_category": registry_source.category if registry_source else "",
                    "source_priority": registry_source.priority if registry_source else "",
                    "source_requires_credentials": registry_source.requires_credentials if registry_source else False,
                    "source_restricted": registry_source.is_restricted_source if registry_source else False,
                    "source_supports_web_search": registry_source.supports_public_web_search if registry_source else True,
                }
            )
            if len(results) >= limit_results:
                _SEARCH_CACHE[cache_key] = (now, [dict(item) for item in results])
                return [dict(item) for item in results]

    _SEARCH_CACHE[cache_key] = (now, [dict(item) for item in results])
    return [dict(item) for item in results]


__all__ = [
    "DEFAULT_WEB_SOURCE_IDS",
    "build_source_registry_context",
    "resolve_official_source_ids_for_query",
    "search_recognized_official_web",
]
