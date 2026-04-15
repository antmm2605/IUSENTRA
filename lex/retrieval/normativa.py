"""Retrieval normativa per Lex."""

from __future__ import annotations

from lex.schemas import LexSource
from web.helpers import get_legal_intelligence


def search_normativa_sources(message: str) -> list[LexSource]:
    route = get_legal_intelligence().resolve_lex_legal_route(message)
    rows: list[LexSource] = []
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
    return rows
