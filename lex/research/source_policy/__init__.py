"""Sistema modulare di policy fonti per Lex."""

from .catalog import AREA_KEYWORDS, MODE_MULTIPLIERS, RELIABILITY_THRESHOLDS, SOURCE_POLICIES, SOURCE_WEIGHTS
from .evaluation import (
    batch_evaluate_sources,
    calculate_source_score,
    evaluate_source,
    evaluate_source_row,
    get_reliability_label,
    init_source_system,
    summarize_evaluated_sources,
    validate_policy_config,
)
from .inference import (
    allowed_domains,
    get_area_suggestions,
    get_domain_from_url,
    get_source_policy,
    get_tier_for_domain,
    infer_area,
    infer_area_with_confidence,
    is_domain_allowed,
    match_domain_pattern,
    normalize_domain,
    normalize_source_mode,
)
from .models import SourceEvaluation, SourceMode, SourcePolicySummary, Tier

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
