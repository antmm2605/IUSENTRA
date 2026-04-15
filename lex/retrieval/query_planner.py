"""Pianificazione query per il retrieval Lex."""

from __future__ import annotations


class QueryPlanner:
    def plan(self, request, context, workflow: str) -> list[str]:
        query = request.query.strip()
        queries = [query] if query else []

        if request.fascicolo_id:
            queries.append(f"fascicolo {request.fascicolo_id} {query}".strip())

        if workflow == "telematico":
            queries.append(f"errore telematico {query}".strip())

        if workflow == "udienza":
            queries.append(f"preparazione udienza {query}".strip())

        return [item for item in queries if item]
