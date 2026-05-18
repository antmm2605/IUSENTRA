"""Ricerca web governata di Lex su domini ufficiali riconosciuti."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from lxml import html as lxml_html

from lex.research.source_registry import get_source_registry
from pct.legal_intelligence import FONTI_UFFICIALI, USER_AGENT, fonti_per_query

DEFAULT_WEB_SOURCE_IDS: tuple[str, ...] = (
    "normattiva",
    "gazzetta_ufficiale",
    "pst_giustizia",
    "cassazione",
    "corte_costituzionale",
    "corte_conti",
    "agenzia_entrate",
)

_OFFICIAL_SEARCH_URL = "https://html.duckduckgo.com/html/"
_CASSAZIONE_PENALE_LIST_URL = "https://www.cortedicassazione.it/it/giurisprudenza_penale.page"
_GAZZETTA_ARCHIVE_URL = "https://www.gazzettaufficiale.it/showArchivioNews"
_DIRECT_URL_RE = re.compile(r"https?://[^\s<>'\")\]]+")
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
    "corte_conti": ("corteconti.it", "banchedati.corteconti.it"),
    "giustizia_amministrativa": ("giustizia-amministrativa.it",),
    "giustizia_amministrativa_decisioni_pareri": ("giustizia-amministrativa.it",),
    "eur_lex": ("eur-lex.europa.eu",),
    "curia": ("curia.europa.eu",),
    "cedu": ("echr.coe.int", "hudoc.echr.coe.int"),
    "agenzia_entrate": ("agenziaentrate.gov.it", "agenziaentrate.it"),
    "anac": ("anticorruzione.it",),
    "anac_documenti": ("anticorruzione.it",),
    "agcom": ("agcom.it",),
    "agcom_provvedimenti": ("agcom.it",),
    "inps": ("inps.it",),
    "inps_circolari": ("inps.it",),
    "inps_messaggi": ("inps.it",),
    "inps_sentenze": ("inps.it",),
    "inail": ("inail.it",),
    "banca_italia": ("bancaditalia.it",),
    "banca_italia_normativa": ("bancaditalia.it",),
    "cnf": ("consiglionazionaleforense.it",),
    "registro_mediazione": ("giustizia.it", "mediazione.giustizia.it"),
    "studiocataldi_codice_civile": ("studiocataldi.it",),
    "studiocataldi_codice_penale": ("studiocataldi.it",),
    "avvocatoandreani_codice_procedura_civile": ("avvocatoandreani.it",),
    "avvocatoandreani_codice_strada": ("avvocatoandreani.it",),
    "iussearch": ("iussearch.it",),
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
        if (
            normalized not in FONTI_UFFICIALI
            and registry.get(normalized) is None
            and normalized not in _SOURCE_DOMAIN_ALIASES
        ):
            return
        seen.add(normalized)
        selected.append(normalized)

    for source_id in explicit_values:
        _push(source_id)
        if len(selected) >= limit:
            return selected[:limit]

    question_text = _clean_spaces(question).lower()
    if re.search(r"\b(?:sentenza|ordinanza|decreto)\s+n[°\.\s]*\d+", question_text) or "cassazione" in question_text:
        _push("cassazione")
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


def _is_public_web_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = _normalize_domain(parsed.hostname or "")
    if not host:
        return False
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


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


def _parse_cassazione_exact_reference(question: str) -> dict[str, str]:
    try:
        from lex.research.case_law_reference_parser import parse_case_law_reference
    except Exception:
        return {}
    reference = parse_case_law_reference(question)
    if not bool(getattr(reference, "is_exact_reference", False)):
        return {}
    kind = _clean_spaces(getattr(reference, "kind", "")).lower()
    number = _clean_spaces(getattr(reference, "number", ""))
    year = _clean_spaces(getattr(reference, "year", ""))
    date = _clean_spaces(getattr(reference, "date", ""))
    if kind not in {"sentenza", "ordinanza", "decreto", "provvedimento"} or not number or not (year or date):
        return {}
    return {"kind": kind, "number": number, "year": year, "date": date}


def _date_matches(text: str, expected_date: str) -> bool:
    if not expected_date:
        return True
    normalized = re.sub(r"\D+", "", text or "")
    expected = re.sub(r"\D+", "", expected_date)
    return bool(expected and expected in normalized)


def _is_cassazione_requested(source_ids: list[str], candidate_domains: list[str]) -> bool:
    if any(str(source_id or "").strip() == "cassazione" for source_id in source_ids):
        return True
    return any("cortedicassazione.it" in domain for domain in candidate_domains)


def _is_gazzetta_requested(source_ids: list[str], candidate_domains: list[str]) -> bool:
    if any(str(source_id or "").strip() == "gazzetta_ufficiale" for source_id in source_ids):
        return True
    return any("gazzettaufficiale.it" in domain for domain in candidate_domains)


def _gazzetta_code_year(code: str) -> str:
    match = re.match(r"(?P<yy>\d{2})[A-Z]\d{5}$", str(code or "").strip().upper())
    if not match:
        return ""
    yy = int(match.group("yy"))
    return str(2000 + yy if yy < 80 else 1900 + yy)


def _parse_gazzetta_reference(question: str) -> dict[str, str]:
    text = _clean_spaces(question)
    lower = text.lower()
    code_match = re.search(r"\b\d{2}[A-Z]\d{5}\b", text.upper())
    date_match = re.search(
        r"\b(?P<day>\d{1,2})\s+"
        r"(?P<month>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
        r"\s+(?P<year>20\d{2}|19\d{2})\b",
        lower,
    )
    number_match = re.search(r"\b(?:n\.?|numero)\s*(?P<number>\d{1,5})\b", lower)
    slash_number_match = re.search(r"\b(?P<number>\d{1,5})\s*/\s*(?P<year>20\d{2}|19\d{2})\b", lower)
    kind = ""
    if "d.lgs" in lower or "decreto legislativo" in lower:
        kind = "decreto legislativo"
    elif re.search(r"\bl\.\s*\d+|\blegge\b", lower):
        kind = "legge"
    elif "decreto-legge" in lower or "d.l." in lower:
        kind = "decreto-legge"
    elif "decreto" in lower:
        kind = "decreto"
    code = code_match.group(0) if code_match else ""
    year = code and _gazzetta_code_year(code) or (
        date_match.group("year") if date_match else slash_number_match.group("year") if slash_number_match else ""
    )
    number = number_match.group("number") if number_match else slash_number_match.group("number") if slash_number_match else ""
    if not code and not (kind and year and number):
        return {}
    return {
        "code": code,
        "year": year,
        "kind": kind,
        "day": str(int(date_match.group("day"))) if date_match else "",
        "month": date_match.group("month") if date_match else "",
        "number": number,
    }


def _gazzetta_card_matches(card_text: str, hrefs_text: str, reference: dict[str, str]) -> bool:
    combined = _clean_spaces(f"{card_text} {hrefs_text}")
    lower = combined.lower()
    code = reference.get("code", "")
    if code:
        return code.lower() in lower
    kind = reference.get("kind", "")
    if kind == "decreto legislativo":
        if "d.lgs" not in lower and "decreto legislativo" not in lower:
            return False
    elif kind and kind not in lower:
        return False
    day = reference.get("day", "")
    month = reference.get("month", "")
    year = reference.get("year", "")
    if day and month and year and f"{day} {month} {year}" not in lower:
        padded_day = day.zfill(2)
        if f"{padded_day} {month} {year}" not in lower:
            return False
    number = reference.get("number", "")
    if number and not re.search(rf"\bn\.\s*{re.escape(number)}\b", lower):
        return False
    return True


def _secure_gazzetta_url(url: str) -> str:
    cleaned = _clean_spaces(url)
    return re.sub(r"^http://(www\.)?gazzettaufficiale\.it", "https://www.gazzettaufficiale.it", cleaned, flags=re.I)


def _gazzetta_archive_fallback(
    question: str,
    *,
    source_ids: list[str],
    candidate_domains: list[str],
    fetch: Callable[..., Any],
    limit_results: int,
) -> list[dict[str, Any]]:
    """Fallback diretto sull'archivio news Gazzetta per riferimenti normativi esatti.

    Il motore esterno puo' non indicizzare subito pagine ELI gia' pubbliche.
    Quando la domanda contiene un codice redazionale o un riferimento normativo
    puntuale, leggiamo l'archivio annuale ufficiale e accettiamo solo la scheda
    che contiene lo stesso codice oppure tipo, data e numero dell'atto.
    """
    reference = _parse_gazzetta_reference(question)
    if not reference or not _is_gazzetta_requested(source_ids, candidate_domains):
        return []
    year = reference.get("year", "")
    if not re.fullmatch(r"\d{4}", year or ""):
        return []
    try:
        response = fetch(
            _GAZZETTA_ARCHIVE_URL,
            params={"anno": year},
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
    except Exception:
        return []
    if int(getattr(response, "status_code", 0) or 0) >= 400:
        return []
    body = str(getattr(response, "text", "") or "")
    if not body.strip():
        return []
    try:
        document = lxml_html.fromstring(body)
    except Exception:
        return []
    cards = document.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' notizie_singola ')]")
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for card in cards:
        links = card.xpath(".//a[@href]")
        hrefs_text = " ".join(str(link.get("href") or "") for link in links)
        card_text = _clean_spaces(card.text_content())
        if not _gazzetta_card_matches(card_text, hrefs_text, reference):
            continue
        official_link = None
        for link in links:
            href = str(link.get("href") or "")
            if "eli/id" in href or (reference.get("code") and reference["code"].lower() in href.lower()):
                official_link = link
                break
        if official_link is None:
            continue
        url = _secure_gazzetta_url(urljoin(_GAZZETTA_ARCHIVE_URL, official_link.get("href") or ""))
        if not _is_allowed_result(url, "gazzettaufficiale.it") or url in seen_urls:
            continue
        seen_urls.add(url)
        title_nodes = card.xpath(".//h6")
        date_nodes = card.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' subtitolo_grid ')]")
        title = _clean_spaces(title_nodes[0].text_content()) if title_nodes else _clean_spaces(official_link.text_content())
        date_text = _clean_spaces(date_nodes[0].text_content()) if date_nodes else ""
        reference_label = _clean_spaces(official_link.text_content())
        excerpt = _clean_spaces(" ".join(part for part in (date_text, reference_label) if part))
        results.append(
            {
                "id": f"gazzetta-archive:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}",
                "title": title or "Gazzetta Ufficiale",
                "url": url,
                "official_url": url,
                "source_home_url": "https://www.gazzettaufficiale.it/",
                "domain": _normalize_domain(urlparse(url).netloc),
                "source_id": "gazzetta_ufficiale",
                "source_name": "Gazzetta Ufficiale",
                "kind": "html",
                "excerpt": excerpt,
                "source_access_status": "public",
                "source_access_label": "Pubblica",
                "source_category": "normativa",
                "source_priority": "primary",
                "source_requires_credentials": False,
                "source_restricted": False,
                "source_supports_web_search": True,
            }
        )
        if len(results) >= limit_results:
            return results
    return results


def _direct_url_fallback(
    question: str,
    *,
    source_ids: list[str],
    candidate_domains: list[str],
    limit_results: int,
) -> list[dict[str, Any]]:
    """Return directly provided public source URLs when they match governed domains."""
    registry = get_source_registry()
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for match in _DIRECT_URL_RE.finditer(str(question or "")):
        url = _clean_spaces(match.group(0).rstrip(".,;:"))
        parsed = urlparse(url)
        domain = _normalize_domain(parsed.netloc)
        if parsed.scheme not in {"http", "https"} or not domain:
            continue
        allowed_domain = next(
            (candidate for candidate in candidate_domains if _is_allowed_result(url, candidate)),
            "",
        )
        if not allowed_domain or url in seen_urls:
            continue
        seen_urls.add(url)
        matched_source_id = _match_source_id_for_domain(source_ids, allowed_domain)
        source = FONTI_UFFICIALI.get(matched_source_id)
        registry_source = registry.get(matched_source_id) or registry.find_by_host(domain)
        source_name = source.nome if source else (registry_source.label if registry_source else domain)
        rows.append(
            {
                "id": f"direct-source-url:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}",
                "title": source_name,
                "url": url,
                "official_url": url,
                "source_home_url": source.official_url if source else (registry_source.base_url if registry_source else ""),
                "domain": domain,
                "source_id": matched_source_id or (registry_source.key if registry_source else domain),
                "source_name": source_name,
                "kind": "pdf" if parsed.path.lower().endswith(".pdf") else "html",
                "excerpt": "URL indicato direttamente e appartenente a una fonte governata.",
                "source_access_status": registry_source.status if registry_source else "",
                "source_access_label": registry_source.access_label if registry_source else "",
                "source_category": registry_source.category if registry_source else "",
                "source_priority": "P0" if source else (registry_source.priority if registry_source else ""),
                "source_requires_credentials": registry_source.requires_credentials if registry_source else False,
                "source_restricted": registry_source.is_restricted_source if registry_source else False,
                "source_supports_web_search": registry_source.supports_public_web_search if registry_source else True,
            }
        )
        if len(rows) >= limit_results:
            break
    return rows


def _direct_free_url_fallback(question: str, *, limit_results: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for match in _DIRECT_URL_RE.finditer(str(question or "")):
        url = _clean_spaces(match.group(0).rstrip(".,;:"))
        if not _is_public_web_url(url) or url in seen_urls:
            continue
        seen_urls.add(url)
        parsed = urlparse(url)
        domain = _normalize_domain(parsed.netloc)
        rows.append(
            {
                "id": f"free-direct-url:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}",
                "title": domain,
                "url": url,
                "official_url": url,
                "source_home_url": f"{parsed.scheme}://{domain}",
                "domain": domain,
                "source_id": domain,
                "source_name": domain,
                "kind": "pdf" if parsed.path.lower().endswith(".pdf") else "html",
                "excerpt": "URL indicato direttamente dall'utente nella ricerca web libera.",
                "source_access_status": "public",
                "source_access_label": "Web libero",
                "source_category": "ricerca_web",
                "source_priority": "web_libero",
                "source_requires_credentials": False,
                "source_restricted": False,
                "source_supports_web_search": True,
                "trust_score": 0.55,
            }
        )
        if len(rows) >= limit_results:
            break
    return rows


def _card_text_for_link(link_node) -> str:
    cards = link_node.xpath("ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' card-news ')][1]")
    if cards:
        return _clean_spaces(cards[0].text_content())
    parents = link_node.xpath("ancestor::*[self::div or self::article][1]")
    if parents:
        return _clean_spaces(parents[0].text_content())
    return _clean_spaces(link_node.text_content())


def _cassazione_listing_fallback(
    question: str,
    *,
    source_ids: list[str],
    candidate_domains: list[str],
    fetch: Callable[..., Any],
    limit_results: int,
) -> list[dict[str, Any]]:
    """Fallback ufficiale stretto per riferimenti esatti presenti nelle pagine Cassazione.

    DuckDuckGo HTML puo' non restituire risultati per query molto puntuali gia'
    pubblicate nel portale della Corte. In quel caso interroghiamo solo le prime
    pagine pubbliche della sezione penale e accettiamo il risultato solo se
    titolo/testo contengono numero e anno/data richiesti.
    """
    reference = _parse_cassazione_exact_reference(question)
    if not reference or not _is_cassazione_requested(source_ids, candidate_domains):
        return []

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    number = reference["number"]
    year = reference["year"]
    expected_date = reference["date"]
    kind = reference["kind"]

    for page in range(1, 6):
        try:
            response = fetch(
                _CASSAZIONE_PENALE_LIST_URL,
                params={"frame3_item": page},
                headers={"User-Agent": USER_AGENT},
                timeout=5,
            )
        except Exception:
            continue
        if int(getattr(response, "status_code", 0) or 0) >= 400:
            continue
        body = str(getattr(response, "text", "") or "")
        if not body.strip():
            continue
        try:
            document = lxml_html.fromstring(body)
        except Exception:
            continue

        links = document.xpath(
            "//a[contains(@href, 'penale_dettaglio.page') "
            "and contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), $kind)]",
            kind=kind,
        )
        for link in links:
            title = _clean_spaces(link.text_content())
            card_text = _card_text_for_link(link)
            combined = f"{title} {card_text}"
            if not re.search(rf"\b{re.escape(number)}\b", combined):
                continue
            if year and year not in combined:
                continue
            if not _date_matches(combined, expected_date):
                continue
            url = urljoin("https://www.cortedicassazione.it/", link.get("href") or "")
            if not _is_allowed_result(url, "cortedicassazione.it") or url in seen_urls:
                continue
            seen_urls.add(url)
            excerpt = card_text.replace(title, "", 1).strip(" -:\n\t")
            results.append(
                {
                    "id": f"cassazione-listing:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}",
                    "title": title,
                    "url": url,
                    "official_url": url,
                    "domain": _normalize_domain(urlparse(url).netloc),
                    "source_id": "cassazione",
                    "source_name": "Corte Suprema di Cassazione",
                    "kind": "html",
                    "excerpt": excerpt,
                    "source_access_status": "public",
                    "source_access_label": "Pubblica",
                    "source_category": "giurisprudenza",
                    "source_priority": "primary",
                    "source_requires_credentials": False,
                    "source_restricted": False,
                    "source_supports_web_search": True,
                }
            )
            if len(results) >= limit_results:
                return results
    return results


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

    direct_results = _direct_url_fallback(
        query,
        source_ids=selected_source_ids,
        candidate_domains=candidate_domains,
        limit_results=limit_results,
    )
    if not direct_results:
        direct_results = _gazzetta_archive_fallback(
            query,
            source_ids=selected_source_ids,
            candidate_domains=candidate_domains,
            fetch=fetch,
            limit_results=limit_results,
        )
    if not direct_results:
        direct_results = _cassazione_listing_fallback(
            query,
            source_ids=selected_source_ids,
            candidate_domains=candidate_domains,
            fetch=fetch,
            limit_results=limit_results,
        )
    if direct_results:
        _SEARCH_CACHE[cache_key] = (now, [dict(item) for item in direct_results])
        return [dict(item) for item in direct_results]

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
                    "official_url": url,
                    "source_home_url": source.official_url if source else (registry_source.base_url if registry_source else ""),
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


def search_free_public_web(
    question: str,
    *,
    request_get: Callable[..., Any] | None = None,
    limit_results: int = 8,
) -> list[dict[str, Any]]:
    """Ricerca web manuale non vincolata alla allowlist delle fonti ufficiali.

    Non crea job, non scrive code e non promuove automaticamente il risultato a
    fonte ufficiale: restituisce URL pubblici da usare nella singola risposta Lex.
    """
    query = _clean_spaces(question)
    limit = max(0, int(limit_results or 0))
    if not query or limit <= 0:
        return []

    cache_key = _cache_key(query, ["__free_web__"], limit)
    cached = _SEARCH_CACHE.get(cache_key)
    now = time.time()
    if cached and now - cached[0] < _SEARCH_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    direct_results = _direct_free_url_fallback(query, limit_results=limit)
    if direct_results:
        _SEARCH_CACHE[cache_key] = (now, [dict(item) for item in direct_results])
        return [dict(item) for item in direct_results]

    fetch = request_get
    if fetch is None:
        import requests

        fetch = requests.get

    try:
        response = fetch(
            _OFFICIAL_SEARCH_URL,
            params={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=6,
        )
    except Exception:
        return []

    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code >= 400:
        return []

    body = str(getattr(response, "text", "") or "")
    if not body.strip():
        return []

    try:
        document = lxml_html.fromstring(body)
    except Exception:
        return []

    nodes = document.xpath("//div[contains(@class, 'result')]")
    if not nodes:
        nodes = document.xpath("//article")

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for node in nodes:
        link_nodes = node.xpath(".//a[contains(@class, 'result__a')] | .//h2//a | .//a[@href]")
        if not link_nodes:
            continue
        link = link_nodes[0]
        url = _extract_result_url(link.get("href") or "")
        if not _is_public_web_url(url) or url in seen_urls:
            continue
        seen_urls.add(url)
        parsed = urlparse(url)
        domain = _normalize_domain(parsed.netloc)
        title = _clean_spaces(link.text_content()) or domain
        snippet_nodes = node.xpath(
            ".//*[contains(@class, 'result__snippet')] | "
            ".//*[contains(@class, 'snippet')] | "
            ".//a[contains(@class, 'result__snippet')]"
        )
        snippet = _clean_spaces(snippet_nodes[0].text_content()) if snippet_nodes else ""
        results.append(
            {
                "id": f"free-web-search:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}",
                "title": title,
                "url": url,
                "official_url": url,
                "source_home_url": f"{parsed.scheme}://{domain}",
                "domain": domain,
                "source_id": domain,
                "source_name": domain,
                "kind": "pdf" if parsed.path.lower().endswith(".pdf") else "html",
                "excerpt": snippet,
                "source_access_status": "public",
                "source_access_label": "Web libero",
                "source_category": "ricerca_web",
                "source_priority": "web_libero",
                "source_requires_credentials": False,
                "source_restricted": False,
                "source_supports_web_search": True,
                "trust_score": 0.55,
            }
        )
        if len(results) >= limit:
            break

    _SEARCH_CACHE[cache_key] = (now, [dict(item) for item in results])
    return [dict(item) for item in results]


__all__ = [
    "DEFAULT_WEB_SOURCE_IDS",
    "build_source_registry_context",
    "resolve_official_source_ids_for_query",
    "search_free_public_web",
    "search_recognized_official_web",
]
