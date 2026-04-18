"""Inferenza area giuridica e utilita' di lookup per Lex."""

from __future__ import annotations

import fnmatch
import re
from typing import Any
from urllib.parse import urlparse

from .catalog import AREA_KEYWORDS, SOURCE_POLICIES
from .models import SourceMode, Tier


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_domain(domain: str) -> str:
    text = _clean_spaces(domain).lower()
    if not text:
        return ""
    if "://" in text:
        text = urlparse(text).netloc or text
    text = re.sub(r"^www\.", "", text)
    text = re.sub(r":\d+$", "", text)
    return text.strip(".")


def get_domain_from_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    return normalize_domain(parsed.netloc or str(url or ""))


def match_domain_pattern(domain: str, pattern: str) -> bool:
    normalized_domain = normalize_domain(domain)
    normalized_pattern = _clean_spaces(pattern).lower()
    if not normalized_domain or not normalized_pattern:
        return False
    if "*" not in normalized_pattern:
        return normalized_domain == normalized_pattern
    return fnmatch.fnmatch(normalized_domain, normalized_pattern)


def get_source_policy(area: str) -> dict[str, list[str]]:
    normalized = _clean_spaces(area).lower() or "default"
    return SOURCE_POLICIES.get(normalized, SOURCE_POLICIES["default"])


def get_tier_for_domain(domain: str, area: str) -> Tier:
    policy = get_source_policy(area)
    for tier_name in ("tier_1", "tier_2", "tier_3"):
        for pattern in policy.get(tier_name, []):
            if match_domain_pattern(domain, pattern):
                return Tier(tier_name)
    return Tier.UNKNOWN


def normalize_source_mode(mode: SourceMode | str | None) -> SourceMode:
    normalized = _clean_spaces(getattr(mode, "value", mode)).lower()
    if normalized in {"strict", "legal_strict", "strict_verified_sources", "strict_normative_freshness"}:
        return SourceMode.STRICT
    if normalized in {"broad", "draft", "drafting", "bozza"}:
        return SourceMode.BROAD
    return SourceMode.BALANCED


def allowed_domains(area: str, mode: SourceMode | str = SourceMode.BALANCED) -> list[str]:
    mode_key = normalize_source_mode(mode).value
    policy = get_source_policy(area)
    tiers_by_mode = {
        "strict": ("tier_1",),
        "balanced": ("tier_1", "tier_2"),
        "broad": ("tier_1", "tier_2", "tier_3"),
    }
    rows: list[str] = []
    for tier_name in tiers_by_mode[mode_key]:
        rows.extend(policy.get(tier_name, []))
    return rows


def is_domain_allowed(domain: str, area: str, mode: SourceMode | str = SourceMode.BALANCED) -> bool:
    normalized = normalize_domain(domain)
    return any(match_domain_pattern(normalized, pattern) for pattern in allowed_domains(area, mode))


def infer_area(query: str, threshold: float = 2.0, fallback_to_default: bool = True) -> str:
    text = _clean_spaces(query).lower()
    if not text:
        return "default"
    best_area = ""
    best_score = 0.0
    for area, keywords in AREA_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            normalized = keyword.lower()
            if normalized and normalized in text:
                score += 1.0 + (len(normalized) / 12.0)
        if score > best_score:
            best_area = area
            best_score = score
    if best_area and best_score >= threshold:
        return best_area
    if best_area and best_score > 0:
        return best_area
    return "default" if fallback_to_default else ""


def infer_area_with_confidence(query: str) -> dict[str, Any] | None:
    text = _clean_spaces(query).lower()
    if not text:
        return None
    scores: dict[str, float] = {}
    for area, keywords in AREA_KEYWORDS.items():
        value = 0.0
        for keyword in keywords:
            normalized = keyword.lower()
            if normalized and normalized in text:
                value += 1.0 + (len(normalized) / 12.0)
        if value > 0:
            scores[area] = value
    if not scores:
        return None
    best_score = max(scores.values())
    normalized_scores = {key: round(value / best_score, 3) for key, value in scores.items()}
    best_area = max(normalized_scores, key=normalized_scores.get)
    top_matches = sorted(normalized_scores.items(), key=lambda item: item[1], reverse=True)[:3]
    return {
        "area": best_area,
        "confidence": normalized_scores[best_area],
        "top_matches": top_matches,
    }


def get_area_suggestions(query: str, top_n: int = 3) -> list[dict[str, Any]]:
    inferred = infer_area_with_confidence(query)
    if not inferred:
        return []
    return [{"area": area, "score": score} for area, score in inferred.get("top_matches", [])[:top_n]]


__all__ = [
    "allowed_domains",
    "get_area_suggestions",
    "get_domain_from_url",
    "get_source_policy",
    "get_tier_for_domain",
    "infer_area",
    "infer_area_with_confidence",
    "is_domain_allowed",
    "match_domain_pattern",
    "normalize_domain",
    "normalize_source_mode",
]
