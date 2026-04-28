"""Guardia qualita' per risposte legali Lex."""

from __future__ import annotations

from typing import Any

from lex.contracts import GuardVerdict


LEGAL_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}
GENERIC_MARKERS = (
    "ciao",
    "allora iniziamo",
    "iniziamo",
    "il fascicolo e' in fase di analisi",
    "il fascicolo è in fase di analisi",
    "ci sono diverse aree chiave",
    "bisogna considerare diversi aspetti",
    "ti consiglio di consultare un avvocato",
    "non posso fornire consulenza legale",
)
SOURCE_MARKERS = ("fonte", "fonti", "evidenz", "norma", "sentenza", "art.", "articolo")
LIMIT_MARKERS = ("limiti", "verific", "non determinabile", "non disponibile", "da controllare")


def _evidence_items(evidence: Any) -> list[Any]:
    if isinstance(evidence, dict):
        return list(evidence.get("items") or [])
    return list(getattr(evidence, "items", None) or [])


def _source_titles(evidence: Any) -> list[str]:
    titles: list[str] = []
    for item in _evidence_items(evidence):
        if isinstance(item, dict):
            title = str(item.get("title") or "").strip()
        else:
            title = str(getattr(item, "title", "") or "").strip()
        if title:
            titles.append(title)
    return titles


class LegalAnswerQualityGuard:
    """Blocca le risposte vaghe quando Lex sta operando su fonti legali."""

    def check(self, **kwargs):
        workflow = str(kwargs.get("workflow") or "").strip()
        draft = kwargs.get("draft")
        evidence = kwargs.get("evidence") or {}
        text = str(getattr(draft, "text", "") or "").strip()
        normalized = " ".join(text.lower().split())
        warnings: list[str] = []
        reasons: list[str] = []

        if not text:
            return GuardVerdict(
                allowed=False,
                reasons=["Risposta vuota prodotta dal provider."],
                risk_level="high",
            )

        generic_hits = [marker for marker in GENERIC_MARKERS if marker in normalized]
        if generic_hits:
            warnings.append("Risposta generica o conversazionale non adatta a Lex legale.")
            reasons.append("Generic legal answer")

        if workflow in LEGAL_WORKFLOWS:
            has_evidence = bool(_evidence_items(evidence))
            has_sources = any(marker in normalized for marker in SOURCE_MARKERS)
            has_limits = any(marker in normalized for marker in LIMIT_MARKERS)
            if has_evidence and not has_sources:
                warnings.append("La risposta non rende riconoscibili le fonti usate.")
            if not has_limits and not has_evidence:
                warnings.append("Mancano limiti/verifiche nonostante l'assenza di evidenze.")
            if generic_hits:
                _mark_draft(draft, warnings)
                return GuardVerdict(
                    allowed=False,
                    warnings=warnings,
                    reasons=reasons,
                    risk_level="high",
                )

        if warnings:
            _mark_draft(draft, warnings)
            return GuardVerdict(allowed=True, warnings=warnings, risk_level="medium")
        return GuardVerdict(allowed=True)


def _mark_draft(draft: Any, warnings: list[str]) -> None:
    try:
        metadata = dict(getattr(draft, "metadata", {}) or {})
        metadata["legal_quality_guard_applied"] = True
        metadata["legal_quality_warnings"] = list(warnings)
        setattr(draft, "metadata", metadata)
    except Exception:
        return
