from __future__ import annotations

import re

from .contracts import LexRequest
from .types import WorkflowType


class LexRouter:
    _NORMATIVA_HINTS = (
        "norma",
        "normativa",
        "decreto",
        "legge",
        "articolo",
        "gazzetta ufficiale",
        "normattiva",
        "vigente",
    )
    _GIURISPRUDENZA_HINTS = (
        "sentenza",
        "sentenze",
        "giurisprudenza",
        "massima",
        "pronuncia",
        "cassazione",
        "tribunale",
        "tar",
        "consiglio di stato",
        "corte costituzionale",
    )
    _PRASSI_HINTS = (
        "circolare",
        "prassi",
        "interpello",
        "provvedimento",
        "linea guida",
        "faq ufficiale",
    )
    _ECONOMICO_HINTS = (
        "preventivo",
        "parcella",
        "fattura",
        "compenso",
        "onorario",
        "tariffa",
        "scaglione",
        "saldo",
        "incasso",
        "pagamento",
    )
    _COMPLIANCE_HINTS = (
        "conforme",
        "compliance",
        "pdf/a",
        "firma",
        "metadati",
        "allegati obbligatori",
        "controllo",
        "verifica deposito",
    )
    _FONTI_HINTS = ("fonte", "fonti", "riferimento", "citazione", "link ufficiale")

    def resolve_workflow(self, request: LexRequest) -> WorkflowType:
        hint = str(getattr(request, "workflow_hint", "") or "").strip().lower()
        if hint:
            return hint  # type: ignore[return-value]

        intent = str(getattr(request, "intent", "") or "").strip()
        if intent == "prepare_udienza":
            return "udienza"
        if intent in {"draft_act_support", "validate_draft"}:
            return "atto"
        if intent in {"summarize_fascicolo", "suggest_fascicolo_updates"}:
            return "fascicolo"
        if intent == "explain_telematico_error":
            return "telematico_status"
        if intent == "suggest_next_action":
            return "next_action"
        if intent in {"analyze_document", "compare_documents"}:
            return "documento"
        if intent == "research_normativa":
            return "normativa"
        if intent == "research_giurisprudenza":
            return "giurisprudenza"
        if intent == "research_prassi":
            return "prassi"
        if intent == "research_sources":
            return "fonti"
        if intent == "check_compliance":
            return "compliance"
        if intent in {"evaluate_preventivo", "evaluate_tariffario", "evaluate_fatturazione"}:
            return "economico"
        if intent in {"explain_normative_change", "summarize_legal_update"}:
            return "intelligence"
        if intent == "resolve_operational_question":
            return "cabina"

        text = self._normalize(" ".join(
            [
                str(getattr(request, "query", "") or ""),
                str((getattr(request, "metadata", {}) or {}).get("module") or ""),
                str((getattr(request, "metadata", {}) or {}).get("topic") or ""),
            ]
        ))
        if self._has_any(text, self._COMPLIANCE_HINTS):
            return "compliance"
        if self._has_any(text, self._ECONOMICO_HINTS):
            return "economico"
        if self._has_any(text, self._PRASSI_HINTS):
            return "prassi"
        if self._has_any(text, self._GIURISPRUDENZA_HINTS):
            return "giurisprudenza"
        if self._has_any(text, self._NORMATIVA_HINTS):
            return "normativa"
        if self._has_any(text, self._FONTI_HINTS):
            return "fonti"
        if self._looks_like_telematico(text):
            return "telematico_status"
        if getattr(request, "fascicolo_id", None):
            return "fascicolo"
        return "question_answering"

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip().lower()

    @staticmethod
    def _has_any(text: str, hints: tuple[str, ...]) -> bool:
        return any(hint in text for hint in hints)

    @staticmethod
    def _looks_like_telematico(text: str) -> bool:
        return any(
            token in text
            for token in (
                "pst",
                "pat",
                "ptt",
                "sigit",
                "siga",
                "pdp",
                "deposito telematico",
                "errore telematico",
                "poli sweb",
                "polisweb",
            )
        )