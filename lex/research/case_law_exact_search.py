"""Ricerca exact-match per riferimenti giurisprudenziali puntuali.

Il modulo trasforma una richiesta come "Sentenza n. 7919 del 31/03/2026"
in query pubbliche governate e classifica i risultati senza inventare fonti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Any

from lex.guards.exact_case_law_guard import check_exact_case_law
from lex.research.case_law_reference_parser import parse_case_law_reference as _parse_reference


@dataclass(slots=True)
class CaseLawReference:
    raw_query: str
    kind: str = ""
    number: str = ""
    date: str = ""
    year: str = ""
    court: str = ""
    jurisdiction: str = ""
    is_exact_reference: bool = False
    normalized_queries: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CaseLawCompletionResult:
    local_fragment_found: bool = False
    local_fragment_summary: str = ""
    official_search_run: bool = False
    exact_match_found: bool = False
    possible_match_found: bool = False
    related_results: list[dict[str, Any]] = field(default_factory=list)
    official_url: str = ""
    official_title: str = ""
    official_court: str = ""
    official_date: str = ""
    official_number: str = ""
    has_full_text: bool = False
    has_pdf: bool = False
    has_dispositivo: bool = False
    has_motivazione: bool = False
    completed_from_web: bool = False
    missing_parts: list[str] = field(default_factory=list)
    confidence_cap: float = 0.45
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    searched_domains: list[str] = field(default_factory=list)
    web_blocked_reason: str = ""


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _ascii_upper(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().upper()


def _extract_local_object(local_fragment: Any) -> str:
    if not local_fragment:
        return ""
    if isinstance(local_fragment, dict):
        text = " ".join(
            _clean_spaces(local_fragment.get(key))
            for key in ("title", "content", "excerpt", "text", "summary")
            if local_fragment.get(key)
        )
    else:
        text = " ".join(
            _clean_spaces(getattr(local_fragment, key, ""))
            for key in ("title", "content", "excerpt", "text", "summary")
            if getattr(local_fragment, key, "")
        )
    match = re.search(r"famiglia\s*:\s*([A-ZÀ-Ù' ]{6,})", text, re.IGNORECASE)
    if not match:
        return ""
    subject = match.group(1).split(".")[0].split("-")[0]
    return _ascii_upper(subject)


def _build_normalized_queries(reference: CaseLawReference, local_fragment: Any = None) -> list[str]:
    if not reference.number:
        return []
    queries: list[str] = []
    if reference.date:
        queries.append(f'"{reference.kind.capitalize()} n. {reference.number} del {reference.date}"')
        queries.append(f'"{reference.number}" "{reference.date}" "Cassazione"')
        queries.append(f'site:cortedicassazione.it "{reference.number}" "{reference.date}"')
    if reference.year:
        queries.append(f'site:cortedicassazione.it "{reference.number}" "{reference.year}"')
    subject = _extract_local_object(local_fragment)
    if subject and reference.year:
        queries.append(f'"{subject}" "{reference.number}" "{reference.year}"')
    return list(dict.fromkeys(queries))


def parse_case_law_reference(query: str) -> CaseLawReference:
    parsed = _parse_reference(query)
    court = parsed.court or "Corte di Cassazione"
    reference = CaseLawReference(
        raw_query=query,
        kind=parsed.kind or "sentenza",
        number=parsed.number,
        date=parsed.date,
        year=parsed.year,
        court=court,
        jurisdiction=parsed.jurisdiction,
        is_exact_reference=bool(parsed.is_exact_reference),
    )
    reference.normalized_queries = _build_normalized_queries(reference)
    return reference


def _row_text(row: Any, *keys: str) -> str:
    for key in keys:
        value = row.get(key) if isinstance(row, dict) else getattr(row, key, "")
        if value:
            return _clean_spaces(value)
    return ""


def _row_to_item(row: dict[str, Any]) -> dict[str, Any]:
    url = _row_text(row, "url", "official_url")
    return {
        "title": _row_text(row, "title", "source_name") or "Fonte ufficiale",
        "content": _row_text(row, "excerpt", "content", "text"),
        "official_url": url,
        "url": url,
        "authority": _row_text(row, "source_name", "domain") or "Fonte ufficiale",
    }


def search_exact_case_law_reference(
    reference: CaseLawReference,
    local_fragment: Any = None,
) -> CaseLawCompletionResult:
    result = CaseLawCompletionResult()
    if local_fragment:
        result.local_fragment_found = True
        result.local_fragment_summary = _clean_spaces(_row_text(local_fragment, "title", "content", "excerpt", "text"))[:500]
    if not reference.is_exact_reference:
        result.web_blocked_reason = "Riferimento non esatto: mancano numero e anno/data."
        result.missing_parts = ["numero", "data o anno"]
        return result

    queries = _build_normalized_queries(reference, local_fragment)
    result.searched_domains = ["cortedicassazione.it", "giustizia.it", "cortecostituzionale.it"]
    rows: list[dict[str, Any]] = []
    result.official_search_run = True
    try:
        from lex.retrieval.official_web import search_recognized_official_web

        for query in queries:
            for row in search_recognized_official_web(query, limit_results=4) or []:
                if isinstance(row, dict):
                    rows.append(row)
                else:
                    rows.append(vars(row))
    except Exception as exc:
        result.web_blocked_reason = str(exc)
        result.warnings.append(f"Ricerca ufficiale non disponibile: {exc}")
        result.next_actions.append("Verifica manualmente sul portale ufficiale.")
        return result

    items = [_row_to_item(row) for row in rows]
    check = check_exact_case_law(
        items,
        exact_number=reference.number,
        exact_year=reference.year,
        exact_date=reference.date,
        exact_court=reference.court,
    )
    result.exact_match_found = check.match_status == "exact_match"
    result.possible_match_found = check.match_status == "possible_match"
    result.official_url = check.official_url
    result.has_full_text = check.has_full_text
    result.has_dispositivo = check.has_dispositivo
    result.has_pdf = result.official_url.lower().endswith(".pdf")
    result.completed_from_web = bool(result.exact_match_found and result.official_url)
    result.confidence_cap = check.confidence_cap
    result.warnings.extend(check.warnings)
    result.next_actions.extend(check.next_actions)
    result.official_number = reference.number
    result.official_date = reference.date
    result.official_court = reference.court
    if result.exact_match_found:
        result.official_title = next((_row_text(item, "title") for item in items if item.get("official_url") == result.official_url), "")
    else:
        result.related_results = items[:2]
    if not result.has_full_text:
        result.missing_parts.extend(["testo integrale", "dispositivo"])
    if not result.has_motivazione:
        result.missing_parts.append("motivazione")
    if not result.official_url:
        result.missing_parts.append("URL/PDF ufficiale")
    result.missing_parts = list(dict.fromkeys(result.missing_parts))
    return result


__all__ = [
    "CaseLawCompletionResult",
    "CaseLawReference",
    "parse_case_law_reference",
    "search_exact_case_law_reference",
]
