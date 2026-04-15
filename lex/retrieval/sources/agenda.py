"""Adapter agenda per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.contracts import EvidenceItem


class AgendaSource:
    source_name = "agenda"

    def search(self, queries, request, context):
        rows = list((context.get("agenda") or context.get("structured_context", {}).get("agenda") or []))[:3]
        return [
            EvidenceItem(
                source_type="agenda",
                source_id=str(index + 1),
                title=str(row.get("titolo") or row.get("title") or "Voce agenda"),
                content=str(row.get("descrizione") or row.get("note") or "").strip(),
                score=0.45,
                metadata={"authority": "internal_agenda"},
            )
            for index, row in enumerate(rows)
        ]
