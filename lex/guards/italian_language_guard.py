"""Guardia linguistica post-generazione — blocca o riscrive risposte Lex in inglese."""

from __future__ import annotations

from typing import Any

from lex.contracts import GuardVerdict
from .italian_response_guard import detect_non_italian_response, rewrite_or_reject_non_italian_response


_DRAFTING_WORKFLOWS = {"drafting_legal_letter", "lettera", "atto"}
_ALWAYS_ITALIAN_WORKFLOWS = {
    "drafting_legal_letter",
    "lettera",
    "atto",
    "udienza",
    "fascicolo",
    "chat",
    "question_answering",
    "normativa",
    "giurisprudenza",
    "prassi",
    "fonti",
    "economico",
    "compliance",
    "cabina",
    "next_action",
    "intelligence",
    "telematico_status",
}


class ItalianLanguageGuard:
    """Verifica che la risposta generata sia in italiano e la riscrive o blocca in caso contrario."""

    def check(self, **kwargs: Any) -> GuardVerdict:
        draft = kwargs.get("draft")
        workflow = str(kwargs.get("workflow") or "chat").strip().lower()
        context = kwargs.get("context") or {}

        text = str(getattr(draft, "text", draft) or "").strip()
        if not text:
            return GuardVerdict(allowed=True)

        if not detect_non_italian_response(text):
            return GuardVerdict(allowed=True)

        ctx_info = {"workflow": workflow}
        rewritten = rewrite_or_reject_non_italian_response(text, ctx_info)

        if rewritten != text and not detect_non_italian_response(rewritten):
            return GuardVerdict(
                allowed=True,
                warnings=["Risposta riscritta in italiano dal guardrail linguistico."],
                rewritten_draft=rewritten,
            )

        is_drafting = workflow in _DRAFTING_WORKFLOWS
        if is_drafting:
            from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
            try:
                query = str(getattr(kwargs.get("request"), "query", "") or "").lower()
                if any(kw in query for kw in ("diffida", "messa in mora", "sollecito", "lettera", "pec")):
                    fallback = build_diffida_messa_in_mora_template({})
                    return GuardVerdict(
                        allowed=True,
                        warnings=[
                            "La risposta AI era in inglese: sostituita con bozza italiana deterministica."
                        ],
                        rewritten_draft=fallback,
                    )
            except Exception:
                pass

        return GuardVerdict(
            allowed=False,
            warnings=["Risposta generata in inglese: non conforme ai requisiti di Lex."],
            reasons=[
                "La risposta conteneva testo prevalentemente in inglese. "
                "Lex deve rispondere sempre in italiano."
            ],
            risk_level="high",
        )
