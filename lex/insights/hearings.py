"""Insight per udienze e scadenze."""

from __future__ import annotations

from lex.contracts import InsightItem


class HearingInsights:
    def build(self, *, request, workflow: str, module_packs):
        if workflow != "udienza":
            return []
        agenda_count = 0
        deadlines_count = 0
        for pack in list(module_packs or []):
            module = str(getattr(pack, "module", "") or "")
            for fact in list(getattr(pack, "facts", []) or []):
                if module == "agenda" and str(getattr(fact, "fact_type", "")) == "eventi_count":
                    agenda_count = int(getattr(fact, "value", 0) or 0)
                if module == "scadenziario" and str(getattr(fact, "fact_type", "")) == "scadenze_count":
                    deadlines_count = int(getattr(fact, "value", 0) or 0)
        detail = f"Agenda: {agenda_count} eventi. Scadenziario: {deadlines_count} scadenze collegate."
        return [
            InsightItem(
                insight_type="hearing",
                title="Quadro udienza pronto",
                detail=detail,
                module="agenda",
                severity="low",
            )
        ]