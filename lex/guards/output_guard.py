"""Pulizia finale dell'output di Lex."""

from __future__ import annotations

from lex.schemas import LexGroundingResult


class OutputGuard:
    def clean(self, *, answer: str, grounding: LexGroundingResult) -> str:
        text = str(answer or "").strip()
        if text:
            return text
        if not grounding.grounded:
            return (
                "Non ho una base documentale o normativa sufficiente per darti "
                "una risposta affidabile su questa richiesta."
            )
        return "Non ho ancora un output utilizzabile da mostrarti."
