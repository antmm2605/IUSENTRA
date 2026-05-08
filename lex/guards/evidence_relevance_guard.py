"""Guardia pertinenza evidenze — filtra fonti irrilevanti per il workflow corrente."""

from __future__ import annotations

from typing import Any

from lex.contracts import GuardVerdict


_DRAFTING_WORKFLOWS = {"drafting_legal_letter", "lettera", "bozza_lettera", "atto", "bozza_atto"}

_IRRELEVANT_FOR_DRAFTING = (
    "sentenza n.",
    "cass. civ.",
    "cass. pen.",
    "corte cost.",
    "tar ",
    "cons. stato",
    "massima",
    "rassegna giurisprudenza",
    "gazzetta ufficiale",
    "d.lgs.",
    "d.m.",
    "legge n.",
    "art. ",
    "c.p.c.",
    "c.p.p.",
)

_RELEVANT_FOR_DRAFTING = (
    "diffida",
    "messa in mora",
    "lettera",
    "sollecito",
    "pec",
    "modello",
    "fac-simile",
    "formula",
    "art. 1219",
    "art. 1206",
    "art. 1207",
    "costituzione in mora",
    "intimazione",
)


def _text_of(item: Any) -> str:
    if isinstance(item, dict):
        return " ".join(str(v) for v in (
            item.get("title", ""),
            item.get("excerpt", ""),
            item.get("text", ""),
            item.get("content", ""),
        )).lower()
    return str(getattr(item, "text", getattr(item, "content", "")) or "").lower()


class EvidenceRelevanceGuard:
    """Rileva se le evidenze recuperate sono pertinenti al workflow di redazione."""

    def check(self, **kwargs: Any) -> GuardVerdict:
        workflow = str(kwargs.get("workflow") or "chat").strip().lower()
        if workflow not in _DRAFTING_WORKFLOWS:
            return GuardVerdict(allowed=True)

        evidence = kwargs.get("evidence") or {}
        items = list(
            (evidence.get("items") if isinstance(evidence, dict) else getattr(evidence, "items", None)) or []
        )
        if not items:
            return GuardVerdict(allowed=True)

        irrelevant = []
        relevant_found = False
        for item in items:
            text = _text_of(item)
            if any(token in text for token in _RELEVANT_FOR_DRAFTING):
                relevant_found = True
            elif any(token in text for token in _IRRELEVANT_FOR_DRAFTING):
                title = str(
                    (item.get("title") if isinstance(item, dict) else getattr(item, "title", "")) or "fonte"
                )
                irrelevant.append(title)

        if irrelevant and not relevant_found:
            return GuardVerdict(
                allowed=True,
                warnings=[
                    f"Evidenze recuperate non pertinenti alla redazione della lettera "
                    f"({len(irrelevant)} fonti irrilevanti: {', '.join(irrelevant[:3])}). "
                    f"La bozza è generata senza riferimenti a queste fonti."
                ],
                risk_level="medium",
            )

        return GuardVerdict(allowed=True)
