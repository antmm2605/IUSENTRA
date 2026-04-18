"""Compatibilita' pubblica per il Source Policy System di Lex.

Questo modulo mantiene un entrypoint semplice e stabile:

    from ai_lex_sources import infer_area, evaluate_source, SourceMode

La logica governabile vive nel package ``lex.research.source_policy``.
"""

from __future__ import annotations

from lex.research.source_policy import (
    AREA_KEYWORDS,
    MODE_MULTIPLIERS,
    RELIABILITY_THRESHOLDS,
    SOURCE_POLICIES,
    SOURCE_WEIGHTS,
    SourceEvaluation,
    SourceMode,
    SourcePolicySummary,
    Tier,
    allowed_domains,
    batch_evaluate_sources,
    calculate_source_score,
    evaluate_source,
    evaluate_source_row,
    get_area_suggestions,
    get_domain_from_url,
    get_reliability_label,
    get_source_policy,
    get_tier_for_domain,
    infer_area,
    infer_area_with_confidence,
    init_source_system,
    is_domain_allowed,
    match_domain_pattern,
    normalize_domain,
    normalize_source_mode,
    summarize_evaluated_sources,
    validate_policy_config,
)

__all__ = [
    "AREA_KEYWORDS",
    "MODE_MULTIPLIERS",
    "RELIABILITY_THRESHOLDS",
    "SOURCE_POLICIES",
    "SOURCE_WEIGHTS",
    "SourceEvaluation",
    "SourceMode",
    "SourcePolicySummary",
    "Tier",
    "allowed_domains",
    "batch_evaluate_sources",
    "calculate_source_score",
    "evaluate_source",
    "evaluate_source_row",
    "get_area_suggestions",
    "get_domain_from_url",
    "get_reliability_label",
    "get_source_policy",
    "get_tier_for_domain",
    "infer_area",
    "infer_area_with_confidence",
    "init_source_system",
    "is_domain_allowed",
    "match_domain_pattern",
    "normalize_domain",
    "normalize_source_mode",
    "summarize_evaluated_sources",
    "validate_policy_config",
]
