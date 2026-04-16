"""Insight di compliance per Lex."""

from __future__ import annotations

from lex.contracts import InsightItem


class ComplianceInsights:
    def build(self, *, request, workflow: str, module_packs, evidence_pack: dict):
        insights = []
        official_sources = list((evidence_pack or {}).get("official_sources") or [])
        for pack in list(module_packs or []):
            if str(getattr(pack, "module", "")) == "telematico" and getattr(pack, "warnings", None):
                insights.append(
                    InsightItem(
                        insight_type="compliance",
                        title="Anomalie telematiche contestualizzate",
                        detail=str((getattr(pack, "warnings", []) or [""])[0] or ""),
                        module="telematico",
                        severity="high",
                    )
                )
        if workflow in {"telematico", "atto", "udienza", "fascicolo", "chat"} and not official_sources:
            insights.append(
                InsightItem(
                    insight_type="compliance",
                    title="Fonti ufficiali da rafforzare",
                    detail="Il pacchetto corrente non contiene ancora fonti ufficiali verificate: serve prudenza nelle conclusioni operative.",
                    module="ricerca_legale",
                    severity="medium",
                )
            )
        return insights[:3]