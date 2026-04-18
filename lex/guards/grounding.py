"""Valutazione di grounding e affidabilita' delle risposte."""

from __future__ import annotations

from lex.schemas import LexGroundingResult


class GroundingGuard:
    def evaluate(self, *, sources: list[dict[str, object]] | None) -> LexGroundingResult:
        rows = list(sources or [])
        has_sources = bool(rows)
        has_policy_metadata = any(
            str(row.get("source_reliability_label") or "").strip()
            or str(row.get("source_policy_tier") or "").strip()
            or bool(row.get("verified_reference"))
            for row in rows
        )
        high = sum(1 for row in rows if str(row.get("source_reliability_label") or "").strip() == "high")
        medium = sum(1 for row in rows if str(row.get("source_reliability_label") or "").strip() == "medium")
        tier_1 = sum(1 for row in rows if str(row.get("source_policy_tier") or "").strip() == "tier_1")
        verified = sum(1 for row in rows if bool(row.get("verified_reference")))
        if not has_policy_metadata:
            enough_sources = len(rows) >= 2
            confidence = 0.85 if enough_sources else 0.45 if has_sources else 0.1
            confidence_label = "alta" if enough_sources else "media" if has_sources else "bassa"
            reasoning = (
                f"Base tradizionale: {len(rows)} fonti disponibili senza classificazione avanzata."
                if has_sources
                else "Nessuna fonte disponibile per sostenere la risposta."
            )
            warnings = [] if enough_sources else (["Base documentale limitata"] if has_sources else ["Nessuna fonte disponibile"])
        else:
            enough_sources = high >= 2 or (high >= 1 and medium >= 1) or (tier_1 >= 1 and verified >= 1)
            if enough_sources:
                confidence = 0.9
                confidence_label = "alta"
                reasoning = (
                    f"Base forte: fonti alta affidabilita {high}, media {medium}, primarie {tier_1}, riferimenti verificati {verified}."
                )
                warnings = []
            elif has_sources:
                confidence = 0.58 if (high >= 1 or medium >= 2 or tier_1 >= 1) else 0.34
                confidence_label = "media" if confidence >= 0.45 else "bassa"
                reasoning = (
                    f"Base intermedia: fonti alta affidabilita {high}, media {medium}, primarie {tier_1}, riferimenti verificati {verified}."
                )
                warnings = ["Base documentale limitata"]
                if tier_1 == 0:
                    warnings.append("Mancano fonti primarie chiaramente riconosciute")
            else:
                confidence = 0.1
                confidence_label = "bassa"
                reasoning = "Nessuna fonte disponibile per sostenere la risposta."
                warnings = ["Nessuna fonte disponibile"]
        return LexGroundingResult(
            grounded=has_sources,
            enough_sources=enough_sources,
            confidence=confidence,
            warnings=warnings,
            confidence_label=confidence_label,
            reasoning=reasoning,
        )
