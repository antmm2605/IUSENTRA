"""Bridge React del Procedure Completion Engine.

Payload tenant-safe per dashboard, anteprima, dettaglio scheda, review e gap
queue. Il tenant e l'utente arrivano sempre dal contesto server (g), mai dal
client; gli errori sono sanificati prima della risposta.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import current_app, g

from pct.procedure_completion.models import card_summary
from pct.procedure_completion.repository import ProcedureCompletionRepository
from pct.procedure_completion.schema import forbidden_keys_in_payload
from pct.procedure_completion.service import (
    PERMESSO_APPROVA,
    PERMESSO_ESEGUI,
    PERMESSO_LEGGI,
    PERMESSO_PUBBLICA,
    ProcedureCompletionError,
    ProcedureCompletionService,
    default_template_search,
)
from pct.procedure_completion.source_plan import SourcePlanSettings
from web.services.feature_flags import is_feature_enabled

_PERMESSI_UI = (
    PERMESSO_LEGGI,
    PERMESSO_ESEGUI,
    PERMESSO_APPROVA,
    PERMESSO_PUBBLICA,
    "procedure_completion.esporta",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "sensitive_payloads_redacted": True,
    }


def engine_enabled() -> bool:
    return is_feature_enabled("lex.procedureCompletion.enabled", current_app.config)


def request_tenant_id() -> str:
    return str(getattr(g, "tenant_id", "") or getattr(g, "studio_id", "") or getattr(g, "tenant_slug", "") or "")


def request_context() -> dict[str, Any]:
    utente = g.get("utente_corrente")
    permessi = {
        permesso
        for permesso in _PERMESSI_UI
        if utente is not None and getattr(utente, "ha_permesso", lambda _p: False)(permesso)
    }
    return {
        "tenant_id": request_tenant_id(),
        "user_id": str(getattr(utente, "username", "") or getattr(utente, "id", "") or ""),
        "permissions": permessi,
    }


def build_service() -> ProcedureCompletionService:
    db_path = str(current_app.config.get("PROCEDURE_COMPLETION_DB") or "./intelligence/procedure_completion.sqlite")
    return ProcedureCompletionService(
        ProcedureCompletionRepository(db_path),
        settings=SourcePlanSettings(),
        template_search=default_template_search,
    )


def validate_client_payload(payload: Any) -> str:
    """Messaggio d'errore se il client tenta di imporre chiavi riservate."""
    chiavi = forbidden_keys_in_payload(payload)
    if chiavi:
        return "Parametri non ammessi dal client: " + ", ".join(chiavi) + "."
    return ""


def card_detail_payload(card: Any, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    dati = card.to_dict() if hasattr(card, "to_dict") else dict(card or {})
    return {
        "ok": True,
        "generatedAt": _iso_now(),
        "contracts": _contracts(),
        "card": dati,
        "summary": card_summary(card) if hasattr(card, "to_dict") else {},
        "validation": validation or {},
        "draftBanner": "Bozza per revisione avvocato"
        if str(dati.get("status")) != "published"
        else "",
    }


def build_dashboard_payload(service: ProcedureCompletionService, context: dict[str, Any]) -> dict[str, Any]:
    try:
        cards = service.search_cards(context=context, limit=30)
    except ProcedureCompletionError:
        cards = []
    try:
        gaps = service.list_gaps(context=context)
    except ProcedureCompletionError:
        gaps = []
    flags = {
        "engine": engine_enabled(),
        "voiceRead": is_feature_enabled("lex.procedureCompletion.voiceRead.enabled", current_app.config),
        "voiceReadLocalOnly": is_feature_enabled("lex.procedureCompletion.voiceRead.localOnly", current_app.config),
    }
    return {
        "ok": True,
        "generatedAt": _iso_now(),
        "contracts": _contracts(),
        "enabled": flags["engine"],
        "flags": flags,
        "permissions": sorted(context.get("permissions") or []),
        "cards": cards,
        "gaps": gaps[:50],
        "counters": {
            "cards": len(cards),
            "needsReview": sum(1 for card in cards if card.get("status") == "needs_review"),
            "approved": sum(1 for card in cards if card.get("status") == "approved"),
            "published": sum(1 for card in cards if card.get("status") == "published"),
            "gapsBlocking": sum(1 for gap in gaps if str(gap.get("severita")) == "blocking"),
        },
        "disclaimer": "Ogni scheda resta una bozza per revisione avvocato finche' non pubblicata.",
    }


def error_payload(message: str, *, status: int = 200) -> tuple[dict[str, Any], int]:
    return (
        {
            "ok": False,
            "errore": str(message or "Operazione non completata."),
            "contracts": _contracts(),
            "generatedAt": _iso_now(),
        },
        status,
    )


__all__ = [
    "build_dashboard_payload",
    "build_service",
    "card_detail_payload",
    "engine_enabled",
    "error_payload",
    "request_context",
    "request_tenant_id",
    "validate_client_payload",
]
