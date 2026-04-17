"""Costanti e regole di business per la coverage pipeline legale."""

from __future__ import annotations

from typing import Any


COVERAGE_SCORING: dict[str, int] = {
    "profile": 5,
    "procedure": 20,
    "variant": 5,
    "phases": 10,
    "acts": 10,
    "documents": 10,
    "norms": 10,
    "checklists": 10,
    "requirements": 5,
    "outcomes": 5,
    "rules": 5,
    "templates": 5,
}

CRITICAL_BLOCKS: tuple[str, ...] = (
    "procedure",
    "phases",
    "acts",
    "documents",
    "checklists",
    "templates",
)

OPEN_GAP_STATUSES: tuple[str, ...] = ("OPEN", "IN_PROGRESS", "GENERATED")
REVIEWABLE_DRAFT_STATUSES: tuple[str, ...] = ("generated", "validated", "needs_review", "approved")
PUBLISHABLE_DRAFT_STATUSES: tuple[str, ...] = ("approved",)

SPECIALIST_KEYWORDS: tuple[str, ...] = (
    "PENALE",
    "SANITARIO",
    "CRISI",
    "IMMIGRAZ",
    "INTERNAZIONALE",
    "SOCIETARIO_PATOLOGICO",
)

TELEMATIC_CHANNEL_CODES: set[str] = {
    "PCT_CIVILE",
    "PDP_PENALE",
    "PAT_AMMINISTRATIVO",
    "PTT_TRIBUTARIO",
    "PORTALE_MINISTERIALE",
    "SPORTELLO_PA",
    "PEC_ONLY",
}


def coverage_status_from_score(score: int) -> str:
    if score <= 24:
        return "EMPTY"
    if score <= 69:
        return "PARTIAL"
    return "READY"


def gap_type_from_missing_blocks(procedure_count: int, missing_blocks: list[str]) -> str:
    missing = set(missing_blocks)
    if procedure_count <= 0:
        return "MISSING_PROCEDURE"
    if "templates" in missing:
        return "MISSING_TEMPLATE"
    if "rules" in missing:
        return "MISSING_RULES"
    if "requirements" in missing:
        return "MISSING_REQUIREMENTS"
    if "documents" in missing:
        return "MISSING_DOCUMENTS"
    return "LOW_SCORE"


def requires_human_review(subbranch_code: str, complexity_level: str) -> bool:
    branch = (subbranch_code or "").upper()
    level = (complexity_level or "").upper()
    if level in {"MEDIUM", "HIGH", "SPECIALIST"}:
        return True
    return any(keyword in branch for keyword in SPECIALIST_KEYWORDS)


def is_telematic_channel(channel_code: str) -> bool:
    return (channel_code or "").upper() in TELEMATIC_CHANNEL_CODES


def normalize_validation_status(errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "generated"
    if warnings:
        return "needs_review"
    return "validated"


def can_auto_publish(
    *,
    policy: dict[str, Any] | None,
    complexity_level: str,
    validation_errors: list[str],
    validation_score: int,
    subbranch_code: str,
) -> bool:
    effective_policy = policy or {}
    if effective_policy.get("require_human_review", True):
        return False
    if not effective_policy.get("auto_publish_allowed", False):
        return False
    if validation_errors:
        return False
    if validation_score < 90:
        return False
    if requires_human_review(subbranch_code, complexity_level):
        return False
    return (complexity_level or "").upper() == "LOW"


def priority_score_for_gap(
    *,
    coverage_score: int,
    operational_priority: int,
    telematic: bool,
    preset_available: bool,
    specialist_without_preset: bool,
    gap_type: str,
) -> int:
    score = max(0, 100 - int(coverage_score))
    score += int(operational_priority or 0)
    if telematic:
        score += 20
    if preset_available:
        score += 10
    if specialist_without_preset:
        score += 15
    if gap_type == "MISSING_PROCEDURE":
        score += 25
    elif gap_type in {"MISSING_TEMPLATE", "MISSING_DOCUMENTS"}:
        score += 10
    return score
