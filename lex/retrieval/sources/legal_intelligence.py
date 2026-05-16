"""Adapter legal intelligence per il retrieval applicativo Lex."""

from __future__ import annotations

from web.helpers import get_legal_intelligence

from . import row_to_evidence


class LegalIntelligenceSource:
    source_name = "legal_intelligence"

    def search(self, queries, request, context):
        query = queries[0] if queries else request.query
        intelligence = get_legal_intelligence()
        route = intelligence.resolve_lex_legal_route(query)
        rows = list(route.get("engine_rows") or [])[:4]
        evidences = []
        if hasattr(intelligence, "lex_mediazione_registry_sources"):
            evidences.extend(
                row_to_evidence(row, "registro_mediazione")
                for row in intelligence.lex_mediazione_registry_sources(query, limit=8)
            )
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
