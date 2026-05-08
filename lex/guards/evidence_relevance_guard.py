"""Guardia pertinenza evidenze — filtra fonti irrilevanti per il workflow corrente."""

from __future__ import annotations

from typing import Any

from lex.contracts import GuardVerdict


_DRAFTING_WORKFLOWS = {
    "drafting_legal_letter", "lettera", "bozza_lettera", "atto", "bozza_atto", "pec_comunicazioni",
}

_TERMINI_WORKFLOWS = {"termini_processuali"}
_TELEMATICO_WORKFLOWS = {"deposito_telematico", "telematico_status", "compliance"}

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
    "legge n.",
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
    "bozza",
    "schema",
    "facsimile",
)

_RELEVANT_FOR_TERMINI = (
    "termine",
    "scadenza",
    "giorni",
    "art. 325",
    "art. 641",
    "c.p.c.",
    "decadenza",
    "perentorio",
)

_IRRELEVANT_FOR_TERMINI = (
    "giurisprudenza",
    "sentenza",
    "massima",
    "rassegna",
)

_RELEVANT_FOR_TELEMATICO = (
    "deposito telematico",
    "pst",
    "pdp",
    "pat",
    "ptt",
    "busta",
    "firma",
    "cades",
    "pdf/a",
    "datiatto",
    "polisweb",
    "checklist",
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


def _item_title(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("title") or "fonte").strip()
    return str(getattr(item, "title", "fonte") or "fonte").strip()


class EvidenceRelevanceGuard:
    """Rileva se le evidenze recuperate sono pertinenti al workflow corrente."""

    def check(self, **kwargs: Any) -> GuardVerdict:  # noqa: C901
        workflow = str(kwargs.get("workflow") or "chat").strip().lower()

        evidence = kwargs.get("evidence") or {}
        items = list(
            (evidence.get("items") if isinstance(evidence, dict) else getattr(evidence, "items", None)) or []
        )
        if not items:
            return GuardVerdict(allowed=True)

        # ---- Workflow redazione ----
        if workflow in _DRAFTING_WORKFLOWS:
            irrelevant = []
            relevant_found = False
            for item in items:
                text = _text_of(item)
                if any(token in text for token in _RELEVANT_FOR_DRAFTING):
                    relevant_found = True
                elif any(token in text for token in _IRRELEVANT_FOR_DRAFTING):
                    irrelevant.append(_item_title(item))
            if irrelevant and not relevant_found:
                return GuardVerdict(
                    allowed=True,
                    warnings=[
                        f"Evidenze recuperate non pertinenti alla redazione "
                        f"({len(irrelevant)} fonti irrilevanti: {', '.join(irrelevant[:3])}). "
                        "La bozza è generata senza queste fonti."
                    ],
                    risk_level="medium",
                )
            return GuardVerdict(allowed=True)

        # ---- Workflow termini processuali ----
        if workflow in _TERMINI_WORKFLOWS:
            relevant_found = any(
                any(token in _text_of(item) for token in _RELEVANT_FOR_TERMINI)
                for item in items
            )
            irrelevant = [
                _item_title(item)
                for item in items
                if any(token in _text_of(item) for token in _IRRELEVANT_FOR_TERMINI)
            ]
            if irrelevant and not relevant_found:
                return GuardVerdict(
                    allowed=True,
                    warnings=[
                        "Fonti giurisprudenziali recuperate non pertinenti al calcolo dei termini processuali."
                    ],
                    risk_level="low",
                )
            return GuardVerdict(allowed=True)

        # ---- Workflow telematico ----
        if workflow in _TELEMATICO_WORKFLOWS:
            relevant_found = any(
                any(token in _text_of(item) for token in _RELEVANT_FOR_TELEMATICO)
                for item in items
            )
            if not relevant_found and items:
                return GuardVerdict(
                    allowed=True,
                    warnings=[
                        "Le fonti recuperate non sembrano specifiche per il deposito telematico richiesto."
                    ],
                    risk_level="low",
                )
            return GuardVerdict(allowed=True)

        return GuardVerdict(allowed=True)
