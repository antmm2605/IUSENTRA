"""Costruzione del payload debug Lex per admin e superadmin.

Il payload debug espone il massimo dettaglio diagnostico del ciclo Lex
(provider, routing, evidenze, fonti, confidence, gap, guard verdicts,
latenza, intent matrix, request profile, contract) senza esporre
informazioni sensibili (chiavi API, path assoluti, query private, token
rimossi).

Visibilita': solo ruoli 'superadmin', 'admin_studio', 'admin'.
La verifica del ruolo e' responsabilita' del chiamante.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


_DEBUG_VERSION = "2.0"

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
    # Phase 18 — extended fields
    intent: str = "",
    intent_confidence: float = 0.0,
    request_profile: str = "",
    routing_priority: int = 0,
    answer_contract: dict[str, Any] | None = None,
    guard_verdicts: list[dict[str, Any]] | None = None,
    latency_ms: float = 0.0,
    latency_breakdown: dict[str, float] | None = None,
    template_used: str = "",
    workflow_registry_hit: bool = False,
    memory_hit: bool = False,
    session_id: str = "",
    request_id: str = "",
    total_tokens: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    # Phase 12 — source scope fields
    source_scope: str = "",
    source_scope_confidence: float = 0.0,
    exact_legal_reference: bool = False,
    exact_reference_number: str = "",
    exact_reference_date: str = "",
    exact_reference_year: str = "",
    exact_reference_court: str = "",
    exact_reference_kind: str = "",
    exact_reference_verdict: str = "",
    studio_data_lookup_used: bool = False,
    studio_entity_hint: str = "",
    web_forced_by_exact_ref: bool = False,
    local_case_law_fragment_found: bool | None = None,
    local_case_law_complete: bool | None = None,
    local_case_law_missing_parts: list[str] | None = None,
    public_web_forced: bool | None = None,
    official_search_run: bool | None = None,
    exact_match_found: bool | None = None,
    completed_from_web: bool | None = None,
    official_url: str = "",
    has_full_text: bool | None = None,
    has_dispositivo: bool | None = None,
    has_motivazione: bool | None = None,
    confidence_cap_reason: str = "",
    discarded_unrelated_case_law_count: int | None = None,
    studio_data_lookup_type: str = "",
    studio_data_lookup_query: str = "",
    studio_data_lookup_cleaned_query: str = "",
    studio_data_lookup_matches: int | None = None,
    studio_data_lookup_status: str = "",
    web_forbidden_reason: str = "",
) -> dict[str, Any]:
    """Costruisce il payload debug completo Lex per admin/superadmin (v2.0 — 46+ campi).

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
    pack_meta = dict(evidence_pack.get("metadata") or {})

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
    # Guard verdicts normalizzati                                          #
    # ------------------------------------------------------------------ #
    normalized_guard_verdicts = _normalize_guard_verdicts(guard_verdicts or [])

    # ------------------------------------------------------------------ #
    # Answer contract (solo campi non sensibili)                           #
    # ------------------------------------------------------------------ #
    safe_contract = _safe_contract(answer_contract or {})

    # ------------------------------------------------------------------ #
    # Latency breakdown                                                    #
    # ------------------------------------------------------------------ #
    safe_latency = dict(latency_breakdown or {})

    # ------------------------------------------------------------------ #
    # Payload finale — 20+ campi                                           #
    # ------------------------------------------------------------------ #
    return {
        # ── Routing e classificazione ──────────────────────────────────
        "workflow": str(workflow or ""),
        "intent": str(intent or ""),
        "intent_confidence": round(float(intent_confidence or 0.0), 4),
        "request_profile": str(request_profile or ""),
        "routing_priority": int(routing_priority or 0),
        "workflow_registry_hit": bool(workflow_registry_hit),
        # ── Provider e modello ─────────────────────────────────────────
        "provider": provider_name,
        "model": model_name,
        "template_used": str(template_used or ""),
        # ── Risposta e qualità ─────────────────────────────────────────
        "answer_mode": answer_mode,
        "confidence": round(confidence, 4),
        "confidence_reason": confidence_reason,
        "risk_level": risk_level,
        # ── Guard verdicts ─────────────────────────────────────────────
        "guard_verdicts": normalized_guard_verdicts,
        # ── Answer contract applicato ──────────────────────────────────
        "answer_contract": safe_contract,
        # ── Evidenze ───────────────────────────────────────────────────
        "evidence_count": evidence_count,
        "official_sources_count": official_count,
        "internal_sources_count": internal_count,
        # ── Retrieval esteso ───────────────────────────────────────────
        "ldr_used": bool(ldr_used),
        "ldr_blocked_reason": str(ldr_blocked_reason or ""),
        "web_used": bool(web_used),
        "web_blocked_reason": str(web_blocked_reason or ""),
        "memory_hit": bool(memory_hit),
        # ── Query (privacy) ────────────────────────────────────────────
        "public_research_query": str(public_research_query or ""),
        "private_context_query": "[REDATTO PER PRIVACY]",
        # ── Token rimossi (solo conteggio) ─────────────────────────────
        "removed_sensitive_tokens": {
            "count": len(removed_sensitive_tokens) if removed_sensitive_tokens is not None else 0
        },
        # ── Fonti e gap ────────────────────────────────────────────────
        "considered_sources": considered_sources,
        "compared_sources": compared_sources,
        "official_sources": official_sources,
        "restricted_sources": restricted_sources,
        "partner_sources": partner_sources,
        "coverage_gaps": coverage_gaps,
        "missing_evidence": missing_evidence,
        # ── Azioni ─────────────────────────────────────────────────────
        "next_actions": next_actions,
        # ── Fallback e cache ───────────────────────────────────────────
        "fallback_triggered": fallback_triggered,
        "retrieval_cache": retrieval_cache,
        # ── Generazione saltata ────────────────────────────────────────
        "skipped_generation_reason": str(skipped_generation_reason or ""),
        # ── Latenza ────────────────────────────────────────────────────
        "latency_ms": round(float(latency_ms or 0.0), 1),
        "latency_breakdown": safe_latency,
        # ── Token usage ────────────────────────────────────────────────
        "total_tokens": int(total_tokens or 0),
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        # ── Sessione e tracciabilità ───────────────────────────────────
        "session_id": str(session_id or ""),
        "request_id": str(request_id or ""),
        # ── Source scope e classificazione fonti ───────────────────────
        "source_scope": str(source_scope or resp_meta.get("source_scope") or pack_meta.get("source_scope") or ""),
        "source_scope_confidence": round(float(source_scope_confidence or resp_meta.get("source_scope_confidence") or pack_meta.get("source_scope_confidence") or 0.0), 4),
        # ── Riferimento legale esatto ──────────────────────────────────
        "exact_legal_reference": bool(exact_legal_reference or resp_meta.get("exact_reference") or pack_meta.get("exact_reference")),
        "exact_reference_number": str(exact_reference_number or resp_meta.get("exact_reference_number") or pack_meta.get("exact_reference_number") or ""),
        "exact_reference_date": str(exact_reference_date or resp_meta.get("exact_reference_date") or pack_meta.get("exact_reference_date") or ""),
        "exact_reference_year": str(exact_reference_year or resp_meta.get("exact_reference_year") or pack_meta.get("exact_reference_year") or ""),
        "exact_reference_court": str(exact_reference_court or resp_meta.get("official_court") or pack_meta.get("official_court") or ""),
        "exact_reference_kind": str(exact_reference_kind or resp_meta.get("exact_reference_kind") or pack_meta.get("exact_reference_kind") or ""),
        "exact_reference_verdict": str(exact_reference_verdict or ("exact_match" if (resp_meta.get("exact_match_found") or pack_meta.get("exact_match_found")) else "")),
        "web_forced_by_exact_ref": bool(web_forced_by_exact_ref or resp_meta.get("public_web_forced") or pack_meta.get("public_web_forced")),
        "local_case_law_fragment_found": bool(resp_meta.get("local_case_law_fragment_found") if local_case_law_fragment_found is None else local_case_law_fragment_found),
        "local_case_law_complete": bool(resp_meta.get("local_case_law_complete") if local_case_law_complete is None else local_case_law_complete),
        "local_case_law_missing_parts": list(local_case_law_missing_parts or resp_meta.get("local_case_law_missing_parts") or pack_meta.get("local_case_law_missing_parts") or []),
        "public_web_forced": bool(resp_meta.get("public_web_forced") if public_web_forced is None else public_web_forced),
        "official_search_run": bool(resp_meta.get("official_search_run") if official_search_run is None else official_search_run),
        "exact_match_found": bool(resp_meta.get("exact_match_found") if exact_match_found is None else exact_match_found),
        "completed_from_web": bool(resp_meta.get("completed_from_web") if completed_from_web is None else completed_from_web),
        "official_url": str(official_url or resp_meta.get("official_url") or pack_meta.get("official_url") or ""),
        "has_full_text": bool(resp_meta.get("has_full_text") if has_full_text is None else has_full_text),
        "has_dispositivo": bool(resp_meta.get("has_dispositivo") if has_dispositivo is None else has_dispositivo),
        "has_motivazione": bool(resp_meta.get("has_motivazione") if has_motivazione is None else has_motivazione),
        "confidence_cap_reason": str(confidence_cap_reason or resp_meta.get("confidence_cap_reason") or pack_meta.get("confidence_cap_reason") or ""),
        "discarded_unrelated_case_law_count": int(discarded_unrelated_case_law_count if discarded_unrelated_case_law_count is not None else (resp_meta.get("discarded_unrelated_case_law_count") or pack_meta.get("discarded_unrelated_case_law_count") or 0)),
        # ── Studio data lookup ─────────────────────────────────────────
        "studio_data_lookup_used": bool(studio_data_lookup_used or resp_meta.get("studio_data_lookup_used")),
        "studio_data_lookup_type": str(studio_data_lookup_type or resp_meta.get("studio_data_lookup_type") or ""),
        "studio_data_lookup_query": str(studio_data_lookup_query or resp_meta.get("studio_data_lookup_query") or ""),
        "studio_data_lookup_cleaned_query": str(studio_data_lookup_cleaned_query or resp_meta.get("studio_data_lookup_cleaned_query") or ""),
        "studio_data_lookup_matches": int(studio_data_lookup_matches if studio_data_lookup_matches is not None else (resp_meta.get("studio_data_lookup_matches") or 0)),
        "studio_data_lookup_status": str(studio_data_lookup_status or resp_meta.get("studio_data_lookup_status") or ""),
        "web_forbidden_reason": str(web_forbidden_reason or resp_meta.get("web_forbidden_reason") or ""),
        "studio_entity_hint": str(studio_entity_hint or ""),
        # ── Versione e timestamp debug ─────────────────────────────────
        "debug_version": _DEBUG_VERSION,
        "debug_timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ------------------------------------------------------------------ #
# Helpers privati                                                       #
# ------------------------------------------------------------------ #

def _normalize_guard_verdicts(verdicts: list[Any]) -> list[dict[str, Any]]:
    """Normalizza una lista di GuardVerdict (o dict) in formato uniforme."""
    result: list[dict[str, Any]] = []
    for v in verdicts:
        if isinstance(v, dict):
            result.append({
                "guard": str(v.get("guard") or "unknown"),
                "allowed": bool(v.get("allowed", True)),
                "risk_level": str(v.get("risk_level") or "low"),
                "warnings": list(v.get("warnings") or []),
                "reasons": list(v.get("reasons") or []),
            })
        else:
            result.append({
                "guard": str(getattr(v, "guard", "unknown") or "unknown"),
                "allowed": bool(getattr(v, "allowed", True)),
                "risk_level": str(getattr(v, "risk_level", "low") or "low"),
                "warnings": list(getattr(v, "warnings", None) or []),
                "reasons": list(getattr(v, "reasons", None) or []),
            })
    return result


def _safe_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Ritorna solo i campi non sensibili dell'answer contract."""
    _ALLOWED_KEYS = {
        "workflow", "sections", "provider_hint", "allow_abstention",
        "italian_only", "disclaimer_suppressed", "no_json_output",
        "no_english_output", "strict_legal", "no_invented_references",
    }
    if not contract:
        return {}
    # Flatten metadata into top-level if present
    flat = dict(contract)
    meta = dict(flat.pop("metadata", {}) or {})
    flat.update(meta)
    return {k: v for k, v in flat.items() if k in _ALLOWED_KEYS}


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
