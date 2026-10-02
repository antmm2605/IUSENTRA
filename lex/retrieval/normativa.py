"""Retrieval normativa per Lex."""

from __future__ import annotations

import logging
from typing import Any

from lex.schemas import LexSource
from web.helpers import get_legal_intelligence

try:
    from lex.retrieval.official_sources_retriever import (
        search_gazzetta as _search_gazzetta,
    )
    from lex.retrieval.official_sources_retriever import (
        search_normattiva as _search_normattiva,
    )
except Exception:  # pragma: no cover - modulo opzionale in ambienti ridotti
    _search_gazzetta = None
    _search_normattiva = None


logger = logging.getLogger(__name__)


def catalogo_fonti_ufficiali(message: str) -> list[dict[str, Any]]:
    """Righe di catalogo delle fonti ufficiali (dove cercare). NON sono evidenze giuridiche."""

    try:
        route = get_legal_intelligence().resolve_lex_legal_route(message)
    except Exception:
        return []
    return [dict(row) for row in list(route.get("source_rows") or [])[:4]]


def search_normativa_sources(message: str) -> list[LexSource]:
    """Evidenze normative: solo testo di norma dell'archivio Normattiva (e Gazzetta).

    Le righe di catalogo ("Area ...; motore ...; capacita ...") non sono evidenze:
    non dicono nulla sulla domanda e, con punteggio alto, scavalcavano le norme.
    """

    return _dedupe_sources(_official_archive_sources(message))


def _official_archive_sources(message: str) -> list[LexSource]:
    query = str(message or "").strip()
    if not query:
        return []
    sources: list[LexSource] = []
    if _search_normattiva is not None:
        try:
            for row in _search_normattiva(query, limit=4):
                if not _riga_pertinente(query, row):
                    continue
                sources.append(_archive_row_to_source(row, source_type="normativa_normattiva", default_title="Normattiva"))
        except Exception:
            pass
    if _search_gazzetta is not None:
        try:
            for row in _search_gazzetta(query, limit=2):
                sources.append(_archive_row_to_source(row, source_type="normativa_gazzetta", default_title="Gazzetta Ufficiale"))
        except Exception:
            pass
    return sources


def _riga_pertinente(query: str, row: dict[str, Any]) -> bool:
    """Scarta i risultati dell'indice che non coprono i termini della domanda."""

    if "pertinenza" not in row:  # ricerca precedente (LIKE in AND): ogni termine e' presente
        return True
    try:
        from lex.ricerca_giuridica.pertinenza import e_pertinente

        testo = " ".join(str(row.get(k) or "") for k in ("titolo", "testo", "excerpt"))
        return e_pertinente(query, testo, riferimento_esatto=bool(row.get("riferimento_esatto")))
    except Exception:
        return True


def _archive_row_to_source(row: dict[str, Any], *, source_type: str, default_title: str) -> LexSource:
    title = str(row.get("titolo") or default_title)
    excerpt = str(row.get("testo") or row.get("excerpt") or "")[:1600]
    source_id = str(row.get("chunk_id") or row.get("document_id") or title)
    return LexSource(
        source_type=source_type,
        source_id=source_id,
        title=title,
        excerpt=excerpt,
        score=_score_riga(row, source_type),
        metadata={
            "official_url": row.get("url_origine") or row.get("url") or "",
            "authority": row.get("fonte") or default_title,
            "published_at": row.get("data") or "",
            "verified_reference": True,
            "archive_context": True,
        },
    )


def _score_riga(row: dict[str, Any], source_type: str) -> float:
    """Punteggio guidato dalla pertinenza della ricerca (non da un valore fisso per tipo di fonte)."""

    if "pertinenza" in row:
        base = 0.45 + 0.5 * float(row.get("pertinenza") or 0.0)
        if row.get("riferimento_esatto"):
            base = max(base, 0.97)
        return round(min(0.99, base), 4)
    return 0.96 if source_type == "normativa_normattiva" else 0.9


def _dedupe_sources(rows: list[LexSource]) -> list[LexSource]:
    seen: set[str] = set()
    output: list[LexSource] = []
    for row in rows:
        key = f"{row.source_type}:{row.source_id}:{row.title}"
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output
