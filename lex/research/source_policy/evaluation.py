"""Valutazione, scoring e sintesi della policy fonti di Lex."""

from __future__ import annotations

import logging
from typing import Any

from .catalog import MODE_MULTIPLIERS, RELIABILITY_THRESHOLDS, SOURCE_POLICIES, SOURCE_WEIGHTS
from .inference import (
    allowed_domains,
    get_domain_from_url,
    get_tier_for_domain,
    normalize_domain,
    normalize_source_mode,
)
from .models import SourceEvaluation, SourceMode, SourcePolicySummary, Tier
from ..source_registry import get_source_registry


LOGGER = logging.getLogger("lex.source_policy")

_INTERNAL_HIGH_PRIORITY_TYPES = {
    "fonte_ufficiale",
    "web_ufficiale",
    "legal_source",
    "legal_updates",
    "normativa",
    "giurisprudenza",
    "prassi",
}
_INTERNAL_CONTEXT_TYPES = {"fascicolo", "documento", "agenda", "scadenza", "scadenziario", "preventivo", "fattura", "telematico"}


def calculate_source_score(domain: str, area: str, mode: SourceMode | str = SourceMode.BALANCED) -> float:
    tier = get_tier_for_domain(domain, area)
    mode_key = normalize_source_mode(mode).value
    base = SOURCE_WEIGHTS.get(tier.value, SOURCE_WEIGHTS[Tier.UNKNOWN.value])
    multiplier = MODE_MULTIPLIERS[mode_key].get(tier.value, 0.0)
    return round(base * multiplier, 6)


def get_reliability_label(score: float) -> str:
    if score >= RELIABILITY_THRESHOLDS["high"]:
        return "high"
    if score >= RELIABILITY_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def evaluate_source(url: str, area: str, mode: SourceMode | str = SourceMode.BALANCED) -> SourceEvaluation:
    normalized_url = str(url or "").strip()
    domain = get_domain_from_url(normalized_url)
    resolved_mode = normalize_source_mode(mode)
    tier = get_tier_for_domain(domain, area)
    score = calculate_source_score(domain, area, resolved_mode)
    warnings: list[str] = []
    registry_entry = get_source_registry().find_by_host(domain)
    if tier == Tier.TIER_3:
        warnings.append("Fonte residuale: usare solo come supporto orientativo.")
    elif tier == Tier.UNKNOWN:
        warnings.append("Dominio non classificato: verificare con fonte primaria prima dell'uso.")
    if registry_entry is not None:
        if registry_entry.requires_credentials:
            warnings.append(f"Fonte governata con accesso non libero: {registry_entry.access_label.lower()}.")
        elif registry_entry.requires_registration:
            warnings.append("Fonte ufficiale con registrazione preventiva: verificare abilitazione e credenziali.")
    authority_band = {
        Tier.TIER_1: "istituzionale_o_primaria",
        Tier.TIER_2: "professionale_affidabile",
        Tier.TIER_3: "web_residuale",
        Tier.UNKNOWN: "non_classificata",
    }[tier]
    return SourceEvaluation(
        url=normalized_url,
        domain=domain,
        area=str(area or "default").strip().lower() or "default",
        tier=tier,
        score=score,
        reliability=get_reliability_label(score),
        mode_used=resolved_mode.value,
        warnings=warnings,
        authority_band=authority_band,
        reason=f"Dominio {domain or 'n.d.'} classificato come {tier.value} per area {area or 'default'}.",
    )


def batch_evaluate_sources(
    urls: list[str],
    area: str,
    mode: SourceMode | str = SourceMode.BALANCED,
    min_score: float = 0.0,
) -> list[SourceEvaluation]:
    rows = [evaluate_source(url, area, mode) for url in list(urls or []) if str(url or "").strip()]
    filtered = [row for row in rows if row.score >= float(min_score or 0.0)]
    return sorted(filtered, key=lambda item: item.score, reverse=True)


def _internal_score(
    *,
    row: dict[str, Any],
    resolved_mode: SourceMode,
    verified_reference: bool,
) -> tuple[Tier, float, str, list[str], str]:
    source_type = str(row.get("type") or row.get("source_type") or "").strip().lower()
    source_id = str(row.get("id") or row.get("source_id") or "").strip().lower()
    warnings: list[str] = []
    if verified_reference or source_type in _INTERNAL_HIGH_PRIORITY_TYPES or source_id.startswith("live-web:"):
        tier = Tier.TIER_1
        base_score = 0.95
        authority_band = "verificata_o_istituzionale"
    elif source_type in _INTERNAL_CONTEXT_TYPES or source_id.startswith(("fascicolo:", "documento:", "agenda:", "scadenza:", "legal-intelligence:dashboard")):
        tier = Tier.TIER_2
        base_score = 0.82
        authority_band = "contesto_interno"
    else:
        tier = Tier.UNKNOWN
        base_score = 0.28
        authority_band = "contesto_non_classificato"
        warnings.append("Contesto interno poco strutturato: usare con verifica aggiuntiva.")
    score = round(base_score * MODE_MULTIPLIERS[resolved_mode.value].get(tier.value, 0.0), 6)
    return tier, score, authority_band, warnings, source_type or "internal"


def evaluate_source_row(
    row: dict[str, Any],
    *,
    area: str,
    mode: SourceMode | str = SourceMode.BALANCED,
) -> dict[str, Any]:
    payload = dict(row or {})
    resolved_mode = normalize_source_mode(mode)
    url = str(
        payload.get("url")
        or payload.get("final_url")
        or payload.get("official_url")
        or payload.get("monitor_url")
        or ""
    ).strip()
    verified_reference = bool(payload.get("verified_reference")) or str(payload.get("stato_verifica_fonte") or "").strip().lower() == "verificata"
    if url:
        evaluation = evaluate_source(url, area, resolved_mode)
    else:
        tier, score, authority_band, warnings, source_type = _internal_score(
            row=payload,
            resolved_mode=resolved_mode,
            verified_reference=verified_reference,
        )
        evaluation = SourceEvaluation(
            url="",
            domain=f"internal://{source_type}",
            area=str(area or "default").strip().lower() or "default",
            tier=tier,
            score=score,
            reliability=get_reliability_label(score),
            mode_used=resolved_mode.value,
            warnings=warnings,
            authority_band=authority_band,
            reason="Valutazione derivata da sorgente interna o strutturata del gestionale.",
        )

    payload["source_reliability"] = evaluation.to_dict()
    payload["source_policy_score"] = evaluation.score
    payload["source_policy_tier"] = evaluation.tier.value
    payload["source_reliability_label"] = evaluation.reliability
    payload["source_authority_band"] = evaluation.authority_band
    return payload


def summarize_evaluated_sources(
    rows: list[dict[str, Any]],
    *,
    area: str,
    area_confidence: float = 0.0,
    mode: SourceMode | str = SourceMode.BALANCED,
    require_primary: bool = False,
) -> SourcePolicySummary:
    evaluated_rows = list(rows or [])
    tier_1_count = sum(1 for row in evaluated_rows if str(row.get("source_policy_tier") or "").strip() == Tier.TIER_1.value)
    tier_2_count = sum(1 for row in evaluated_rows if str(row.get("source_policy_tier") or "").strip() == Tier.TIER_2.value)
    tier_3_count = sum(1 for row in evaluated_rows if str(row.get("source_policy_tier") or "").strip() == Tier.TIER_3.value)
    unknown_count = sum(1 for row in evaluated_rows if str(row.get("source_policy_tier") or "").strip() == Tier.UNKNOWN.value)
    high_count = sum(1 for row in evaluated_rows if str(row.get("source_reliability_label") or "").strip() == "high")
    medium_count = sum(1 for row in evaluated_rows if str(row.get("source_reliability_label") or "").strip() == "medium")
    low_count = sum(1 for row in evaluated_rows if str(row.get("source_reliability_label") or "").strip() == "low")
    has_primary_sources = tier_1_count > 0
    if high_count >= 2 or (tier_1_count >= 1 and medium_count >= 1):
        recommended_confidence = "alta"
    elif high_count >= 1 or medium_count >= 2:
        recommended_confidence = "media"
    else:
        recommended_confidence = "bassa"

    warnings: list[str] = []
    if require_primary and not has_primary_sources:
        warnings.append("Mancano fonti primarie o ufficiali sufficienti per una risposta forte.")
    if tier_3_count > 0:
        warnings.append("Sono presenti fonti residuali: usarle solo come supporto orientativo.")
    if low_count and high_count == 0:
        warnings.append("La base documentale e' debole e richiede verifica ulteriore.")

    reasoning_parts = [
        f"Area rilevata: {str(area or 'default').strip().lower() or 'default'}.",
        f"Fonti primarie {tier_1_count}, professionali {tier_2_count}, residuali {tier_3_count}, non classificate {unknown_count}.",
        f"Affidabilita alta {high_count}, media {medium_count}, bassa {low_count}.",
    ]
    if require_primary and not has_primary_sources:
        reasoning_parts.append("Per questa richiesta Lex deve dichiarare i limiti invece di forzare una risposta certa.")

    return SourcePolicySummary(
        area=str(area or "default").strip().lower() or "default",
        area_confidence=float(area_confidence or 0.0),
        mode_used=normalize_source_mode(mode).value,
        total_sources=len(evaluated_rows),
        tier_1_count=tier_1_count,
        tier_2_count=tier_2_count,
        tier_3_count=tier_3_count,
        unknown_count=unknown_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        has_primary_sources=has_primary_sources,
        recommended_confidence=recommended_confidence,
        reasoning=" ".join(reasoning_parts).strip(),
        warnings=warnings,
        block_unverified_answer=bool(require_primary and not has_primary_sources),
    )


def validate_policy_config() -> dict[str, Any]:
    result = {"valid": True, "warnings": [], "errors": []}
    seen_patterns: set[str] = set()
    for area, policy in SOURCE_POLICIES.items():
        for tier_name in ("tier_1", "tier_2", "tier_3"):
            values = policy.get(tier_name)
            if not isinstance(values, list):
                result["errors"].append(f"Area '{area}' senza lista valida per {tier_name}.")
                result["valid"] = False
                continue
            for pattern in values:
                if pattern in seen_patterns:
                    result["warnings"].append(f"Pattern duplicato: {pattern}")
                seen_patterns.add(pattern)
    return result


def init_source_system(log_level: int = logging.INFO) -> bool:
    logging.basicConfig(level=log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    validation = validate_policy_config()
    if not validation["valid"]:
        LOGGER.critical("Configurazione source policy non valida: %s", validation["errors"])
        return False
    return True


__all__ = [
    "batch_evaluate_sources",
    "calculate_source_score",
    "evaluate_source",
    "evaluate_source_row",
    "get_reliability_label",
    "init_source_system",
    "summarize_evaluated_sources",
    "validate_policy_config",
]
