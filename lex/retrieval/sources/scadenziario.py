"""Adapter scadenziario per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.contracts import EvidenceItem


class ScadenziarioSource:
    source_name = "scadenziario"

    def search(self, queries, request, context):
        rows = list(context.get("scadenziario") or context.get("structured_context", {}).get("scadenze") or [])[:3]
        return [
            EvidenceItem(
                source_type="scadenziario",
                source_id=str(index + 1),
                title=str(row.get("titolo") or row.get("title") or "Scadenza"),
                content=str(row.get("descrizione") or row.get("note") or "").strip(),
                score=0.5,
                metadata={"authority": "internal_deadline"},
            )
            for index, row in enumerate(rows)
        ]
