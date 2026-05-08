"""Costruzione del payload debug Lex per admin e superadmin.

Il payload debug espone il massimo dettaglio diagnostico del ciclo Lex
(provider, routing, evidenze, fonti, confidence, gap) senza esporre
informazioni sensibili (chiavi API, path assoluti, query private, token
rimossi).

Visibilita': solo ruoli 'superadmin', 'admin_studio', 'admin'.
La verifica del ruolo e' responsabilita' del chiamante.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


_DEBUG_VERSION = "1.0"

_AUTHORIZED_ROLES: frozenset[str] = frozenset({"superadmin", "admin_studio", "admin"})


def should_include_debug(user_role: str) -> bool:
    """Ritorna True se il ruolo e' autorizzato a ricevere il payload debug."""
    return str(user_role or "").strip().lower() in _AUTHORIZED_ROLES


def build_lex_debug_payload(
    request: Any,
    context: Any,
    workflow: str,
    evidence: dict[str, Any],
    draft: Any,
    verdict: Any,
    response: Any,
    *,
    public_research_query: str = "",
    private_context_query: str = "",  # NON esposto: sostituito con [REDATTO PER PRIVACY]
    removed_sensitive_tokens: list[str] | None = None,
    ldr_used: bool = False,
    ldr_blocked_reason: str = "",
    web_used: bool = False,
    web_blocked_reason: str = "",
    skipped_generation_reason: str = "",
) -> dict[str, Any]:
    """Costruisce il payload debug completo Lex per admin/superadmin.

    Parametri sensibili gestiti:
    - private_context_query → sempre '[REDATTO PER PRIVACY]' nell'output
    - removed_sensitive_tokens → solo il conteggio, mai i token reali
    - path assoluti → sanitizzati a basename
    - chiavi API → mai esposte
    """
    # ------------------------------------------------------------------ #
    # Normalizzazione input                                                #
    # ------------------------------------------------------------------ #
    ev = dict(evidence or {})
    evidence_pack = dict(ev.get("evidence_pack") or {})
    draft_meta = dict(getattr(draft, "metadata", {}) or {})
    resp_meta = dict(getattr(response, "metadata", {}) or {})

    official_sources: list[str] = list(
        ev.get("official_sources") or evidence_pack.get("official_sources") or []
    )
    trusted_sources: list[str] = list(
        ev.get("trusted_sources") or evidence_pack.get("trusted_sources") or []
    )
    considered_sources: list[str] = list(
        getattr(response, "considered_sources", None) or []
    )
    compared_sources: list[Any] = list(
        ev.get("source_comparison") or evidence_pack.get("compared_sources") or []
    )
    coverage_gaps: list[str] = list(
        ev.get("coverage_gaps") or evidence_pack.get("coverage_gaps") or []
    )
    missing_evidence: list[str] = list(
        getattr(response, "missing_evidence", None) or coverage_gaps or []
    )
    next_actions: list[str] = list(
        getattr(response, "next_actions", None) or []
    )

    restricted_sources: list[str] = list(
        evidence_pack.get("metadata", {}).get("source_registry_restricted") or []
    )
    partner_sources: list[str] = list(
        evidence_pack.get("metadata", {}).get("source_registry_partner") or []
    )

    evidence_count = len(list(ev.get("items") or []))
    official_count = len(official_sources)
    internal_count = len(trusted_sources)

    confidence: float = float(getattr(response, "confidence", 0.0) or 0.0)
    answer_mode: str = str(getattr(response, "answer_mode", "needs_review") or "needs_review")
    risk_level: str = str(getattr(verdict, "risk_level", "low") or "low")
    fallback_triggered: bool = bool(ev.get("fallback_triggered") or evidence_pack.get("fallback_triggered"))

    provider_name: str = str(
        resp_meta.get("provider")
        or draft_meta.get("provider")
        or getattr(draft, "provider", "")
        or ""
    )
    model_name: str = str(
        draft_meta.get("model")
        or resp_meta.get("model")
        or ""
    )

    # ------------------------------------------------------------------ #
    # Confidence reason                                                     #
    # ------------------------------------------------------------------ #
    confidence_reason = _build_confidence_reason(
        confidence=confidence,
        official_count=official_count,
        internal_count=internal_count,
        evidence_count=evidence_count,
        fallback_triggered=fallback_triggered,
    )

    # ------------------------------------------------------------------ #
    # Retrieval cache (senza dati sensibili)                               #
    # ------------------------------------------------------------------ #
    raw_cache = dict(ev.get("cache") or resp_meta.get("retrieval_cache") or {})
    retrieval_cache = _sanitize_cache(raw_cache)

    # ------------------------------------------------------------------ #
    # Payload finale                                                        #
    # ------------------------------------------------------------------ #
    return {
        # Routing e provider
        "workflow": str(workflow or ""),
        "provider": provider_name,
        "model": model_name,
        # Risposta
        "answer_mode": answer_mode,
        "confidence": round(confidence, 4),
        "confidence_reason": confidence_reason,
        "risk_level": risk_level,
        # Evidenze
        "evidence_count": evidence_count,
        "official_sources_count": official_count,
        "internal_sources_count": internal_count,
        # Retrieval esteso
        "ldr_used": bool(ldr_used),
        "ldr_blocked_reason": str(ldr_blocked_reason or ""),
        "web_used": bool(web_used),
        "web_blocked_reason": str(web_blocked_reason or ""),
        # Query (privacy)
        "public_research_query": str(public_research_query or ""),
        "private_context_query": "[REDATTO PER PRIVACY]",
        # Token rimossi (solo conteggio, mai i valori reali)
        "removed_sensitive_tokens": {
            "count": len(removed_sensitive_tokens) if removed_sensitive_tokens is not None else 0
        },
        # Fonti e gap
        "considered_sources": considered_sources,
        "compared_sources": compared_sources,
        "official_sources": official_sources,
        "restricted_sources": restricted_sources,
        "partner_sources": partner_sources,
        "coverage_gaps": coverage_gaps,
        "missing_evidence": missing_evidence,
        # Azioni
        "next_actions": next_actions,
        # Fallback e cache
        "fallback_triggered": fallback_triggered,
        "retrieval_cache": retrieval_cache,
        # Generazione saltata
        "skipped_generation_reason": str(skipped_generation_reason or ""),
        # Versione e timestamp debug
        "debug_version": _DEBUG_VERSION,
        "debug_timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ------------------------------------------------------------------ #
# Helpers privati                                                       #
# ------------------------------------------------------------------ #

def _build_confidence_reason(
    *,
    confidence: float,
    official_count: int,
    internal_count: int,
    evidence_count: int,
    fallback_triggered: bool,
) -> str:
    """Genera una breve motivazione testuale del livello di confidence."""
    if confidence >= 0.82:
        level = "alta"
    elif confidence >= 0.62:
        level = "media"
    else:
        level = "bassa"

    parts: list[str] = [f"{level} ({round(confidence * 100)}%)"]

    if official_count:
        parts.append(
            f"per {official_count} "
            f"{'fonte ufficiale' if official_count == 1 else 'fonti ufficiali'}"
        )
    elif internal_count:
        parts.append(
            f"per {internal_count} "
            f"{'fonte interna' if internal_count == 1 else 'fonti interne'}"
        )
    elif evidence_count:
        parts.append(
            f"per {evidence_count} "
            f"{'evidenza' if evidence_count == 1 else 'evidenze'} operative"
        )
    else:
        parts.append("per evidenze insufficienti")

    if fallback_triggered:
        parts.append("(fallback esterno attivato)")

    return "; ".join(parts)


def _sanitize_cache(cache: dict[str, Any]) -> dict[str, Any]:
    """Rimuove dati sensibili dalla cache di retrieval.

    Regole:
    - Rimuove chiavi che contengono 'key', 'token', 'secret', 'password',
      'credential', 'auth'.
    - Sanitizza eventuali valori stringa che sembrano path assoluti:
      espone solo il basename.
    """
    _SENSITIVE_KEYS = frozenset({
        "api_key", "token", "secret", "password",
        "credential", "credentials", "auth", "authorization",
        "bearer", "private_key", "access_token", "refresh_token",
    })

    result: dict[str, Any] = {}
    for key, value in cache.items():
        key_lower = str(key).lower()
        if any(s in key_lower for s in _SENSITIVE_KEYS):
            continue
        if isinstance(value, str):
            value = _sanitize_path(value)
        result[key] = value
    return result


def _sanitize_path(value: str) -> str:
    """Se il valore sembra un path assoluto (Unix o Windows), ritorna solo il basename."""
    stripped = value.strip()
    if stripped.startswith("/") or (len(stripped) > 2 and stripped[1] == ":"):
        return os.path.basename(stripped)
    return value
