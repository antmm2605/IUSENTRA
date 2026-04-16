"""Normalizzazione delle query per il pacchetto di ricerca Lex."""

from __future__ import annotations


class ResearchQueryPlanner:
    def build(self, request, context, workflow: str, queries):
        studio = dict(context.get("studio") or {})
        normalized = []
        for item in [studio.get("effective_question"), request.query, *(queries or [])]:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized[:6]