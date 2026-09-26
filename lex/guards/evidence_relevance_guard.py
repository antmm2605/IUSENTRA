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


_KNOWLEDGE_WORKFLOWS = {"question_answering", "normativa", "giurisprudenza", "prassi", "fonti", "research", "chat"}

_STOPWORDS = frozenset(
    """alla alle allo agli anche avere come cosa cose dalla dalle dallo degli della delle dello dell dopo dove
    essere fare gli hanno questa queste questo questi quale quali quando quanto quanti quella quelle quello
    sono sulla sulle sullo sugli tutto tutti tutte una uno nella nelle nello negli perche perché però sempre
    ancora molto poco solo dice dicono prevede previsto prevista secondo mentre oppure senza verso
    termine termini lex dammi dimmi spiegami vorrei sapere puoi potresti devo deve posso""".split()
)


def _parole_chiave(domanda: str) -> tuple[set[str], set[str]]:
    import re as _re

    testo = str(domanda or "").lower()
    articoli = set(_re.findall(r"\bart(?:icol[oi]|t)?\.?\s*(\d{1,4}(?:-(?:bis|ter|quater))?)", testo))
    numeri = articoli | {n for n in _re.findall(r"\b\d{3,5}\b", testo) if not (n.startswith(("19", "20")) and len(n) == 4)}
    parole = {p[:6] for p in _re.findall(r"[a-zàèéìòù]{5,}", testo) if p not in _STOPWORDS}
    return parole, numeri


def evidenza_pertinente(domanda: str, testo_evidenza: str) -> bool:
    """Una fonte è pertinente se cita l'articolo chiesto o condivide le parole centrali della domanda."""
    parole, numeri = _parole_chiave(domanda)
    if not parole and not numeri:
        return True
    testo = str(testo_evidenza or "").lower()
    if numeri and any(n in testo for n in numeri):
        return True
    if not parole:
        return False
    trovate = sum(1 for p in parole if p in testo)
    return trovate >= min(2, len(parole))


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


class PertinenzaFontiGuard:
    """Domande di conoscenza: se nessuna fonte riguarda la domanda, Lex si astiene.

    Gira dopo le guardie specifiche (citazioni, riferimenti, allucinazioni), così
    il loro motivo, più preciso, resta quello mostrato quando bloccano.
    """

    def check(self, **kwargs: Any) -> GuardVerdict:
        workflow = str(kwargs.get("workflow") or "chat").strip().lower()
        if workflow not in _KNOWLEDGE_WORKFLOWS:
            return GuardVerdict(allowed=True)
        evidence = kwargs.get("evidence") or {}
        items = list(
            (evidence.get("items") if isinstance(evidence, dict) else getattr(evidence, "items", None)) or []
        )
        if not items:
            return GuardVerdict(allowed=True)
        request = kwargs.get("request")
        domanda = str(getattr(request, "query", "") or (request.get("query") if isinstance(request, dict) else "") or "")
        if domanda and not any(evidenza_pertinente(domanda, _text_of(item)) for item in items):
            return GuardVerdict(
                allowed=False,
                reasons=["Le fonti trovate non riguardano la domanda: Lex non risponde senza una fonte pertinente."],
                risk_level="medium",
            )
        return GuardVerdict(allowed=True)
