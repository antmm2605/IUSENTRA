"""Tool Lex del Procedure Completion Engine (governed-only, niente raw chat).

Ogni tool restituisce il contratto governato: official_sources, citations,
compared_sources, coverage_gaps, confidence, answer_mode, needs_review,
next_actions. Con fonti insufficienti la risposta e' needs_review con azioni
successive, mai un contenuto giuridico inventato.
"""

from __future__ import annotations

import os
from typing import Any

from lex.tools.base import BaseLexTool

_FLAG_ENV = "IUSENTRA_FF_LEX_PROCEDURECOMPLETION_ENABLED"


def _engine_enabled() -> bool:
    raw = str(os.getenv(_FLAG_ENV, "1")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _service(kwargs: dict[str, Any]):
    """Service iniettabile nei test; default su repository reale."""
    service = kwargs.get("service")
    if service is not None:
        return service
    from pct.procedure_completion.repository import ProcedureCompletionRepository
    from pct.procedure_completion.service import (
        ProcedureCompletionService,
        default_template_search,
    )

    db_path = str(kwargs.get("db_path") or os.getenv("PROCEDURE_COMPLETION_DB", "./intelligence/procedure_completion.sqlite"))
    return ProcedureCompletionService(
        ProcedureCompletionRepository(db_path),
        template_search=default_template_search,
    )


def _context(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": str(kwargs.get("tenant_id") or ""),
        "user_id": str(kwargs.get("user_id") or kwargs.get("user") or ""),
        "permissions": set(kwargs.get("user_permissions") or kwargs.get("permissions") or ()),
    }


def _governed_envelope(
    *,
    card: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card = card or {}
    validation = validation or {}
    gaps = [str(gap.get("descrizione") or gap.get("codice_gap") or "") for gap in card.get("gap_evidenza") or []]
    needs_review = str(card.get("status") or "draft") not in {"approved", "published"}
    next_actions: list[str] = []
    if needs_review:
        next_actions.append("Inviare la scheda in revisione avvocato prima dell'uso.")
    next_actions.extend(
        str(gap.get("azione_suggerita"))
        for gap in card.get("gap_evidenza") or []
        if str(gap.get("azione_suggerita") or "").strip()
    )
    envelope = {
        "ok": True,
        "answer_mode": "grounded" if (card.get("citations") and not needs_review) else "needs_review",
        "needs_review": needs_review,
        "confidence": str(card.get("confidence") or "LOW"),
        "official_sources": [
            src for src in card.get("sources") or [] if str(src.get("source_type")) == "official"
        ],
        "compared_sources": [
            {"title": src.get("title"), "type": src.get("source_type"), "trust_class": src.get("trust_class")}
            for src in card.get("sources") or []
        ],
        "citations": card.get("citations") or [],
        "coverage_gaps": [gap for gap in gaps if gap],
        "next_actions": next_actions[:8],
        "validation": validation,
        "disclaimer": "Bozza per revisione avvocato: nessuna risposta giuridica senza citazioni verificate.",
    }
    envelope.update(extra or {})
    return envelope


class ProcedureCompletionPreviewTool(BaseLexTool):
    tool_name = "procedure_completion_preview"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        if not _engine_enabled():
            return {"ok": False, "reason": "feature_flag_disabled"}
        payload = {
            "codice": kwargs.get("codice"),
            "denominazione": kwargs.get("denominazione"),
            "categoria": kwargs.get("categoria"),
            "rito": kwargs.get("rito"),
            "competenza": kwargs.get("competenza"),
            "template_code": kwargs.get("template_code"),
        }
        try:
            esito = _service(kwargs).preview_completion(payload, _context(kwargs))
        except Exception as exc:
            return {"ok": False, "reason": "preview_non_riuscita", "detail": str(exc)[:200]}
        return _governed_envelope(
            card=esito.get("card"),
            validation=esito.get("validation"),
            extra={"card": esito.get("card"), "summary": esito.get("summary"), "run_id": esito.get("runId")},
        )


class ProcedureCompletionSearchTool(BaseLexTool):
    tool_name = "procedure_completion_search"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        if not _engine_enabled():
            return {"ok": False, "reason": "feature_flag_disabled"}
        try:
            cards = _service(kwargs).search_cards(
                query=str(kwargs.get("query") or kwargs.get("codice") or ""),
                status=str(kwargs.get("status") or ""),
                context=_context(kwargs),
            )
        except Exception as exc:
            return {"ok": False, "reason": "ricerca_non_riuscita", "detail": str(exc)[:200]}
        return {
            "ok": True,
            "answer_mode": "grounded",
            "needs_review": any(card.get("status") not in {"approved", "published"} for card in cards),
            "cards": cards,
            "citations": [],
            "official_sources": [],
            "coverage_gaps": [],
            "next_actions": [],
        }


class ProcedureCompletionExplainArticleTool(BaseLexTool):
    tool_name = "procedure_completion_explain_article"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        if not _engine_enabled():
            return {"ok": False, "reason": "feature_flag_disabled"}
        try:
            esito = _service(kwargs).explain_article(
                str(kwargs.get("card_id") or ""),
                str(kwargs.get("article_ref") or kwargs.get("riferimento") or ""),
                _context(kwargs),
            )
        except Exception as exc:
            return {"ok": False, "reason": "spiegazione_non_disponibile", "detail": str(exc)[:200]}
        esito.setdefault("answer_mode", "grounded" if esito.get("ok") and esito.get("citations") else "needs_review")
        esito.setdefault("official_sources", [])
        esito.setdefault("coverage_gaps", [] if esito.get("ok") else ["Riferimento non coperto dalle citazioni della scheda."])
        return esito


class ProcedureCompletionSuggestTemplateTool(BaseLexTool):
    tool_name = "procedure_completion_suggest_template"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        if not _engine_enabled():
            return {"ok": False, "reason": "feature_flag_disabled"}
        try:
            esito = _service(kwargs).suggest_template(str(kwargs.get("card_id") or ""), _context(kwargs))
        except Exception as exc:
            return {"ok": False, "reason": "suggerimento_non_disponibile", "detail": str(exc)[:200]}
        esito.setdefault("answer_mode", "grounded")
        esito.setdefault("citations", [])
        esito.setdefault("official_sources", [])
        esito.setdefault(
            "coverage_gaps",
            [str(gap.get("descrizione") or "") for gap in esito.get("gaps") or []],
        )
        esito.setdefault("next_actions", ["Collegare o creare un template nel catalogo atti."] if esito.get("needs_review") else [])
        return esito


class ProcedureCompletionListGapsTool(BaseLexTool):
    tool_name = "procedure_completion_list_gaps"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        if not _engine_enabled():
            return {"ok": False, "reason": "feature_flag_disabled"}
        try:
            gaps = _service(kwargs).list_gaps(
                severita=str(kwargs.get("severita") or ""),
                card_id=str(kwargs.get("card_id") or ""),
                context=_context(kwargs),
            )
        except Exception as exc:
            return {"ok": False, "reason": "gap_non_disponibili", "detail": str(exc)[:200]}
        return {
            "ok": True,
            "answer_mode": "grounded",
            "needs_review": bool(gaps),
            "gaps": gaps,
            "citations": [],
            "official_sources": [],
            "coverage_gaps": [str(gap.get("descrizione") or "") for gap in gaps],
            "next_actions": sorted(
                {
                    str(gap.get("azione_suggerita"))
                    for gap in gaps
                    if str(gap.get("azione_suggerita") or "").strip()
                }
            )[:8],
        }


__all__ = [
    "ProcedureCompletionPreviewTool",
    "ProcedureCompletionSearchTool",
    "ProcedureCompletionExplainArticleTool",
    "ProcedureCompletionSuggestTemplateTool",
    "ProcedureCompletionListGapsTool",
]
