"""Guardia qualita' per risposte legali Lex.

Blocca:
- Risposte vaghe e generiche
- Disclaimer "non sono un avvocato / consulta un avvocato"
- Output in inglese
- Output JSON/codice non richiesto
- Formule da chatbot
- Fonti irrilevanti per workflow di redazione
"""

from __future__ import annotations

from typing import Any

from lex.contracts import GuardVerdict


LEGAL_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti", "intelligence"}

DRAFTING_WORKFLOWS = {
    "drafting_legal_letter", "lettera", "bozza_lettera", "atto", "bozza_atto", "pec_comunicazioni",
}

# Formule generiche vietate
GENERIC_MARKERS = (
    "ciao",
    "allora iniziamo",
    "iniziamo",
    "il fascicolo e' in fase di analisi",
    "il fascicolo è in fase di analisi",
    "ci sono diverse aree chiave",
    "bisogna considerare diversi aspetti",
    "sono qui per aiutarti",
    "come posso aiutarti",
    "rest assured",
    "as an ai",
    "as a language model",
)

# Disclaimer vietati ("non sono avvocato" e simili)
DISCLAIMER_MARKERS = (
    "ti consiglio di consultare un avvocato",
    "consulta un avvocato",
    "rivolgiti a un avvocato",
    "si consiglia di rivolgersi",
    "non posso fornire consulenza legale",
    "non sono un avvocato",
    "non sono un legale",
    "non sostituisco la consulenza",
    "questo non costituisce consulenza",
    "questa non è consulenza legale",
    "si raccomanda di consultare",
    "è sempre consigliabile consultare",
    "per decisioni legali consultare",
    "le informazioni qui riportate non costituiscono",
    "non posso garantire l'accuratezza",
    "non posso essere ritenuto responsabile",
)

# Formule chatbot vietate
CHATBOT_MARKERS = (
    "ecco un esempio di risposta",
    "spero di essere stato utile",
    "spero che questa risposta",
    "per aiutarti ulteriormente",
    "simulazione di un sistema di chatbot",
    "resto a disposizione",
    "non esitare a contattarmi",
    "sono felice di aiutarti",
    "è stato un piacere aiutarti",
    "posso aiutarti con",
    "fammi sapere se hai altre domande",
    "se hai bisogno di ulteriori informazioni",
)

# Pattern JSON/codice indesiderato in risposta non tecnica
JSON_MARKERS = (
    '{"risposta"',
    '"answer":',
    '"text":',
    '"content":',
    "```json",
    "```python",
    "```javascript",
)

SOURCE_MARKERS = ("fonte", "fonti", "evidenz", "norma", "sentenza", "art.", "articolo")
LIMIT_MARKERS = ("limiti", "verific", "non determinabile", "non disponibile", "da controllare")

# Frammenti inglesi che NON devono comparire in risposte legali
ENGLISH_LEGAL_FRAGMENTS = (
    "dear recipient",
    "dear sir",
    "dear madam",
    "i am writing to",
    "please be advised",
    "please note that",
    "as per our",
    "in accordance with",
    "please find attached",
    "kindly note",
    "we hereby",
    "pursuant to",
    "notwithstanding",
    "whereas",
    "hereinafter",
    "the aforementioned",
    "in witness whereof",
)


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
    """Guardia qualità professionale per risposte Lex."""

    def check(self, **kwargs):  # noqa: C901
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

        # 1. Blocco disclaimer "consulta un avvocato"
        disclaimer_hits = [m for m in DISCLAIMER_MARKERS if m in normalized]
        if disclaimer_hits:
            warnings.append("Risposta contiene disclaimer vietati ('consulta un avvocato' o simili).")
            reasons.append("Disclaimer vietato: Lex risponde sempre in modo professionale senza scaricare sul cliente.")
            _mark_draft(draft, warnings)
            return GuardVerdict(
                allowed=False,
                warnings=warnings,
                reasons=reasons,
                risk_level="high",
            )

        # 2. Blocco formule chatbot
        chatbot_hits = [m for m in CHATBOT_MARKERS if m in normalized]
        if chatbot_hits:
            warnings.append("Risposta contiene formule da chatbot vietate in Lex professionale.")
            reasons.append("Chatbot markers: Lex risponde come collega esperto, non come assistente generico.")
            _mark_draft(draft, warnings)
            return GuardVerdict(
                allowed=False,
                warnings=warnings,
                reasons=reasons,
                risk_level="medium",
            )

        # 3. Blocco JSON non richiesto (solo per workflow non tecnici)
        if workflow not in {"documento_editor", "document_editor"}:
            json_hits = [m for m in JSON_MARKERS if m in text[:200]]
            if json_hits:
                warnings.append("Risposta contiene output JSON/codice non richiesto.")
                reasons.append("JSON output non atteso per questo workflow.")
                _mark_draft(draft, warnings)
                return GuardVerdict(
                    allowed=False,
                    warnings=warnings,
                    reasons=reasons,
                    risk_level="medium",
                )

        # 4. Blocco inglese in workflow di redazione
        if workflow in DRAFTING_WORKFLOWS:
            english_hits = [m for m in ENGLISH_LEGAL_FRAGMENTS if m in normalized]
            if english_hits:
                warnings.append(f"Risposta in inglese per workflow di redazione '{workflow}'.")
                reasons.append("English output in Italian drafting workflow.")
                _mark_draft(draft, warnings)
                return GuardVerdict(
                    allowed=False,
                    warnings=warnings,
                    reasons=reasons,
                    risk_level="high",
                )

        # 5. Formule generiche
        generic_hits = [marker for marker in GENERIC_MARKERS if marker in normalized]
        if generic_hits:
            warnings.append("Risposta generica o conversazionale non adatta a Lex legale.")
            reasons.append("Generic legal answer")

        # 6. Workflow legali: verifica fonti e limiti
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
