"""Adapter workspace registry per il retrieval applicativo Lex."""

from __future__ import annotations

from web.helpers import get_applicazioni_repository

from . import row_to_evidence


class ApplicazioniSource:
    source_name = "applicazioni"

    def search(self, queries, request, context):
        route = get_applicazioni_repository().resolve_workspace_for_request(queries[0] if queries else request.query, limit=3)
        rows = list(route.get("candidate_apps") or [])[:3]
        return [
            row_to_evidence(
                {
                    "type": "applicazioni",
                    "id": row.get("app_id") or row.get("id") or "",
                    "title": row.get("title") or "Modulo",
                    "excerpt": (
                        f"Sezione {row.get('section_title') or 'n.d.'}; "
                        f"accesso {row.get('access_mode_label') or row.get('access_mode') or 'n.d.'}; "
                        f"endpoint {row.get('endpoint') or 'n.d.'}."
                    ),
                    "score": 0.55,
                    "authority": "workspace_registry",
                },
                "applicazioni",
            )
            for row in rows
        ]
