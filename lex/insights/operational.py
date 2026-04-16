"""Insight operativi derivati dai result pack di Lex."""

from __future__ import annotations

from lex.contracts import InsightItem


class OperationalInsights:
    def build(self, *, request, workflow: str, module_packs):
        insights = []
        for pack in list(module_packs or []):
            if str(getattr(pack, "module", "")) == "cabina":
                for fact in list(getattr(pack, "facts", []) or []):
                    if str(getattr(fact, "fact_type", "")) == "headline.alert_aperti" and int(getattr(fact, "value", 0) or 0) > 0:
                        insights.append(
                            InsightItem(
                                insight_type="operational",
                                title="Alert operativi aperti",
                                detail=f"Il cockpit segnala {int(getattr(fact, 'value', 0) or 0)} alert da presidiare.",
                                module="cabina",
                                severity="medium",
                            )
                        )
            if getattr(pack, "warnings", None):
                insights.append(
                    InsightItem(
                        insight_type="operational",
                        title=f"Verifica {getattr(pack, 'module', 'modulo')}",
                        detail=str((getattr(pack, "warnings", []) or [""])[0] or ""),
                        module=str(getattr(pack, "module", "cabina") or "cabina"),
                        severity="medium",
                    )
                )
        return insights[:4]