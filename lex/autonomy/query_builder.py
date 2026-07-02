"""Costruttore deterministico di query verso fonti ufficiali.

Le query nascono SOLO da campi strutturati della ResearchQuestion (norma
normalizzata, termine, area): mai dal testo libero dei campioni, quindi niente
PII per costruzione. I domini `site:` vengono dalla policy governata
(`allowed_domains(area, mode)` del Source Policy System); i riferimenti
giurisprudenziali riusano le varianti di `parse_case_law_reference` (che già
emette query `site:cortedicassazione.it`).
"""

from __future__ import annotations

import re

from lex.autonomy.models import ResearchQuestion

# Instradamenti fissi per tipo di riferimento normativo (fonti certe).
_EU_REFERENCE_RE = re.compile(r"\b(?:UE|CELEX|Regolamento|Direttiva)\b", re.IGNORECASE)


def build_queries(
    question: ResearchQuestion,
    *,
    source_mode: str = "strict",
    max_queries: int = 3,
) -> list[str]:
    """Query ordinate e deduplicate per la domanda, con tetto rigido."""

    queries: list[str] = []
    if question.target_citation:
        queries.extend(_citation_queries(question.target_citation, question.area, source_mode))
    if question.target_term:
        queries.extend(_term_queries(question.target_term, question.area, source_mode))
    if not queries:
        queries.extend(_area_queries(question.area, source_mode))
    queries.extend(_case_law_variants(question.question))

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        clean = " ".join(str(query or "").split())
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            deduped.append(clean)
    return deduped[: max(1, int(max_queries))]


def _citation_queries(citation: str, area: str, source_mode: str) -> list[str]:
    if _EU_REFERENCE_RE.search(citation):
        primary = ["eur-lex.europa.eu"]
    else:
        primary = ["normattiva.it", "gazzettaufficiale.it"]
    if (area or "").casefold() == "privacy":
        primary.append("garanteprivacy.it")
    return [f"{citation} site:{domain}" for domain in primary] + [citation]


def _term_queries(term: str, area: str, source_mode: str) -> list[str]:
    domains = _top_official_domains(area, source_mode, limit=2)
    base = f'"{term}"' + (f" {area}" if area else "")
    return [f"{base} site:{domain}" for domain in domains] + [base]


def _area_queries(area: str, source_mode: str) -> list[str]:
    if not area:
        return []
    domains = _top_official_domains(area, source_mode, limit=2)
    base = f"fonti normative primarie {area}"
    return [f"{base} site:{domain}" for domain in domains] + [base]


def _top_official_domains(area: str, source_mode: str, *, limit: int) -> list[str]:
    # Import pigro del Source Policy System (dati + funzioni pure).
    from lex.research.source_policy.inference import allowed_domains

    try:
        domains = allowed_domains(area or "civile", source_mode)
    except Exception:
        domains = []
    return [domain for domain in domains if "*" not in domain][: max(1, limit)]


def _case_law_variants(question_text: str) -> list[str]:
    # Riuso del parser giurisprudenziale esistente: se la domanda contiene un
    # riferimento esatto, le sue varianti (già con site: ufficiali) hanno priorità.
    try:
        from lex.research.case_law_reference_parser import parse_case_law_reference

        reference = parse_case_law_reference(question_text)
        if getattr(reference, "is_exact_reference", False):
            return [str(item) for item in getattr(reference, "all_query_variants", []) or []][:3]
    except Exception:
        pass
    return []


__all__ = ["build_queries"]
