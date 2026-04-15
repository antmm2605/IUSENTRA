"""Valutazione di grounding e affidabilita' delle risposte."""

from __future__ import annotations

from lex.schemas import LexGroundingResult


class GroundingGuard:
    def evaluate(self, *, sources: list[dict[str, object]] | None) -> LexGroundingResult:
        rows = list(sources or [])
        has_sources = bool(rows)
        enough_sources = len(rows) >= 2
        confidence = 0.85 if enough_sources else 0.45 if has_sources else 0.1
        warnings = [] if enough_sources else (["Base documentale limitata"] if has_sources else ["Nessuna fonte disponibile"])
        return LexGroundingResult(
            grounded=has_sources,
            enough_sources=enough_sources,
            confidence=confidence,
            warnings=warnings,
        )
