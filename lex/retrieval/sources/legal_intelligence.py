"""Adapter legal intelligence per il retrieval applicativo Lex."""

from __future__ import annotations

from web.helpers import get_legal_intelligence

from . import row_to_evidence


class LegalIntelligenceSource:
    source_name = "legal_intelligence"

    def search(self, queries, request, context):
        route = get_legal_intelligence().resolve_lex_legal_route(queries[0] if queries else request.query)
        rows = list(route.get("engine_rows") or [])[:4]
        evidences = []
        for row in rows:
            evidences.append(
                row_to_evidence(
                    {
                        "type": "legal_intelligence",
                        "id": row.get("engine_id") or row.get("motore") or "",
                        "title": row.get("label") or row.get("engine_id") or "Motore intelligence",
                        "excerpt": (
                            f"Area {row.get('area') or 'n.d.'}; "
                            f"capability {row.get('capability') or 'n.d.'}; "
                            f"cadence {row.get('cadence') or 'n.d.'}."
                        ),
                        "score": 0.82,
                        "authority": "knowledge_base",
                    },
                    "legal_intelligence",
                )
            )
        return evidences
