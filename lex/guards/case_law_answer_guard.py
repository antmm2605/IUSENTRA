"""Guardia anti-risposta generica per analisi giurisprudenziale."""

from __future__ import annotations

from typing import Any


_FORBIDDEN_GENERIC_PHRASES = (
    "il fascicolo e' in fase di analisi",
    "il fascicolo è in fase di analisi",
    "iniziamo",
    "ci sono diverse aree chiave",
    "bisogna considerare diversi aspetti",
    "non posso fornire consulenza legale",
    "ti consiglio di consultare un avvocato",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


class CaseLawAnswerGuard:
    def evaluate(self, answer: str, evidence_items: list[Any]) -> tuple[bool, list[str]]:
        normalized = _clean(answer)
        warnings: list[str] = []
        if not normalized:
            return False, ["Risposta giurisprudenziale vuota."]

        for phrase in _FORBIDDEN_GENERIC_PHRASES:
            if phrase in normalized:
                warnings.append(f"Risposta generica non ammessa: {phrase}.")

        has_pronuncia = "pronuncia" in normalized or "sentenza" in normalized
        has_question = "questione" in normalized or "oggetto" in normalized
        has_decision = "decisione" in normalized or "dispositivo" in normalized
        has_sources = "fonti" in normalized or "fonte" in normalized

        if not has_pronuncia:
            warnings.append("Manca la sezione Pronuncia/Sentenza.")
        if not has_question:
            warnings.append("Manca la sezione Questione/Oggetto.")
        if not has_decision:
            warnings.append("Manca la sezione Decisione/Dispositivo.")
        if not has_sources:
            warnings.append("Manca la sezione Fonti considerate.")

        if list(evidence_items or []) and len(normalized) < 220:
            warnings.append("Risposta troppo breve rispetto alle evidenze disponibili.")

        missing_required = sum(
            1
            for present in (has_pronuncia, has_question, has_decision, has_sources)
            if not present
        )
        allowed = not warnings or (not any("Risposta generica" in item for item in warnings) and missing_required <= 1)
        return allowed, warnings
