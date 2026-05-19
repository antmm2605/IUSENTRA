"""Retrieval normativa per Lex."""

from __future__ import annotations

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


def search_normativa_sources(message: str) -> list[LexSource]:
    rows: list[LexSource] = []
    try:
        route = get_legal_intelligence().resolve_lex_legal_route(message)
    except Exception:
        route = {}
    for row in list(route.get("source_rows") or [])[:4]:
        rows.append(
            LexSource(
                source_type="fonte_ufficiale",
                source_id=str(row.get("source_id") or ""),
                title=str(row.get("nome") or row.get("source_id") or "Fonte ufficiale"),
                excerpt=(
                    f"Area {row.get('area') or 'n.d.'}; "
                    f"motore {row.get('motore') or 'n.d.'}; "
                    f"capacita {row.get('capability') or 'n.d.'}."
                ),
                score=0.9,
                metadata={"official_url": row.get("official_url") or ""},
            )
        )
    rows.extend(_official_archive_sources(message))
    return _dedupe_sources(rows)


def _official_archive_sources(message: str) -> list[LexSource]:
    query = str(message or "").strip()
    if not query:
        return []
    sources: list[LexSource] = []
    if _search_normattiva is not None:
        try:
            for row in _search_normattiva(query, limit=4):
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


def _archive_row_to_source(row: dict[str, Any], *, source_type: str, default_title: str) -> LexSource:
    title = str(row.get("titolo") or default_title)
    excerpt = str(row.get("testo") or row.get("excerpt") or "")[:1600]
    source_id = str(row.get("chunk_id") or row.get("document_id") or title)
    return LexSource(
        source_type=source_type,
        source_id=source_id,
        title=title,
        excerpt=excerpt,
        score=0.96 if source_type == "normativa_normattiva" else 0.9,
        metadata={
            "official_url": row.get("url_origine") or row.get("url") or "",
            "authority": row.get("fonte") or default_title,
            "published_at": row.get("data") or "",
            "verified_reference": True,
            "archive_context": True,
        },
    )


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
