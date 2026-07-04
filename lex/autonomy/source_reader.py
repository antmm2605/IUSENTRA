"""Lettura governata di una fonte: fetch cortese → testo → citazioni → termini.

In modalità offline il candidato porta `content` inline (StaticSearchProvider)
e non si tocca la rete; in modalità web il fetch passa SEMPRE dal
`PoliteFetcher` (robots + rate-limit + max_bytes). Il testo viene estratto con
`lex.sources.extractors.extract_text_from_bytes` (riuso, niente file temporanei)
e analizzato con i motori di `lex.learning`.
"""

from __future__ import annotations

from lex.learning.citation_extractor import extract_citations
from lex.learning.legal_language_analyzer import extract_term_observations
from lex.learning.models import LegalCitation, LegalTermObservation, SourceReadingResult
from lex.sources.models import SourceCandidate
from lex.sources.polite_fetcher import PoliteFetcher

# Tetto dell'estratto persistito in memoria: abbastanza per rispondere a una
# domanda puntuale (testo di un articolo, massima) senza far crescere i JSONL.
EXCERPT_MAX_CHARS = 1800


def read_source(
    candidate: SourceCandidate,
    *,
    area: str,
    fetcher: PoliteFetcher | None,
    iso_now: str = "",
) -> tuple[SourceReadingResult, list[LegalCitation], list[LegalTermObservation]]:
    """Legge la fonte e restituisce (lettura, citazioni, termini osservati)."""

    warnings: list[str] = []
    if candidate.content:
        text = " ".join(candidate.content.split())
    elif fetcher is None:
        return (
            SourceReadingResult(
                url=candidate.url,
                title=candidate.title,
                area=area,
                status="network_error",
                source_id=candidate.source_id,
                fetched_at=iso_now,
                warnings=["Nessun contenuto inline e nessun fetcher: lettura non eseguita (modalità offline)."],
            ),
            [],
            [],
        )
    else:
        fetch = fetcher.fetch(candidate.url)
        warnings.extend(fetch.warnings)
        if fetch.status != "ok" or not fetch.content:
            return (
                SourceReadingResult(
                    url=candidate.url,
                    title=candidate.title,
                    area=area,
                    status=fetch.status if fetch.status != "ok" else "empty_text",
                    source_id=candidate.source_id,
                    fetched_at=fetch.fetched_at or iso_now,
                    warnings=warnings,
                ),
                [],
                [],
            )
        # Riuso dell'estrattore esistente, senza file temporanei.
        from lex.sources.extractors import extract_text_from_bytes

        text = extract_text_from_bytes(fetch.content, fetch.content_type, filename=candidate.url)
        iso_now = fetch.fetched_at or iso_now

    if not text.strip():
        return (
            SourceReadingResult(
                url=candidate.url,
                title=candidate.title,
                area=area,
                status="empty_text",
                source_id=candidate.source_id,
                fetched_at=iso_now,
                warnings=[*warnings, "Testo vuoto dopo l'estrazione: nessun apprendimento dalla fonte."],
            ),
            [],
            [],
        )

    citations = extract_citations(text, source_url=candidate.url)
    terms = extract_term_observations(text, area, source_ids=[candidate.url], citations=citations)
    reading = SourceReadingResult(
        url=candidate.url,
        title=candidate.title,
        area=area,
        status="ok",
        source_id=candidate.source_id,
        text_characters=len(text),
        citations_normalized=sorted({citation.normalized_text for citation in citations}),
        terms_normalized=sorted({term.normalized for term in terms}),
        # La memoria conserva il CONTENUTO letto (non solo i conteggi): è ciò
        # che la sorgente retrieval lex_memory serve alle risposte, con
        # l'ancora ufficiale dell'URL.
        excerpt=" ".join(text.split())[:EXCERPT_MAX_CHARS],
        fetched_at=iso_now,
        warnings=warnings,
    )
    return reading, citations, terms


__all__ = ["EXCERPT_MAX_CHARS", "read_source"]
