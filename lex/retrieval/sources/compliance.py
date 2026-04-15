"""Adapter compliance per il retrieval applicativo Lex."""

from __future__ import annotations

from lex.contracts import EvidenceItem


class ComplianceSource:
    source_name = "compliance"

    def search(self, queries, request, context):
        query = queries[0] if queries else request.query
        return [
            EvidenceItem(
                source_type="compliance",
                source_id="guard-rail-telematico",
                title="Regole di conformita operative",
                content=f"Applicare guard rail di conformita e verifica ufficiale su: {query}",
                score=0.7,
                metadata={"authority": "compliance_engine"},
            )
        ]
