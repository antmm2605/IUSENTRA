"""Insight economici derivati dai facts di Lex."""

from __future__ import annotations

from lex.contracts import InsightItem


class EconomicInsights:
    def build(self, *, request, workflow: str, economic_facts):
        insights = []
        for fact in list(economic_facts or []):
            fact_type = str(getattr(fact, "fact_type", "") or "")
            value = getattr(fact, "value", None)
            if fact_type in {"saldo_aperto", "residuo"} and value not in (None, "", 0, 0.0):
                insights.append(
                    InsightItem(
                        insight_type="economic",
                        title="Saldo aperto",
                        detail=f"La pratica presenta ancora un saldo aperto pari a {value}.",
                        module="fatture",
                        severity="medium",
                    )
                )
            if fact_type == "fatture_da_emettere" and int(value or 0) > 0:
                insights.append(
                    InsightItem(
                        insight_type="economic",
                        title="Fatture da emettere",
                        detail=f"Risultano {int(value or 0)} fatture ancora da emettere.",
                        module="fatture",
                        severity="medium",
                    )
                )
        return insights[:3]