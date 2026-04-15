"""Retrieval telematico per Lex."""

from __future__ import annotations

from lex.schemas import LexSource
from web.helpers import get_legal_intelligence


def search_pst_sources(message: str) -> list[LexSource]:
    route = get_legal_intelligence().resolve_telematico_route(message)
    rows: list[LexSource] = []
    for row in list(route.get("action_rows") or [])[:3]:
        rows.append(
            LexSource(
                source_type="telematico",
                source_id=str(row.get("action_id") or ""),
                title=str(row.get("label") or row.get("action_id") or "Azione telematica"),
                excerpt=(
                    f"Canale {row.get('channel') or 'n.d.'}; "
                    f"fonte di verita {row.get('source_of_truth') or 'n.d.'}; "
                    f"note {row.get('notes') or 'n.d.'}."
                ),
                score=0.8,
                metadata={"requires_certificate": bool(row.get("requires_certificate"))},
            )
        )
    return rows
