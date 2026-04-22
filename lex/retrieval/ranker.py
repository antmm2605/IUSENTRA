from __future__ import annotations

import math
import re
from typing import Any

_OFFICIAL_BONUS = {"A": 1.0, "B": 0.75, "C": 0.35, "D": 0.1}
_WORKFLOW_WEIGHTS = {
    "fascicolo": {"base": 0.35, "trust": 0.10, "freshness": 0.10, "context": 0.30, "consensus": 0.15},
    "udienza": {"base": 0.25, "trust": 0.15, "freshness": 0.15, "context": 0.30, "consensus": 0.15},
    "telematico_status": {"base": 0.25, "trust": 0.20, "freshness": 0.20, "context": 0.20, "consensus": 0.15},
    "normativa": {"base": 0.15, "trust": 0.30, "freshness": 0.20, "context": 0.15, "consensus": 0.20},
    "giurisprudenza": {"base": 0.15, "trust": 0.30, "freshness": 0.15, "context": 0.15, "consensus": 0.25},
    "prassi": {"base": 0.15, "trust": 0.25, "freshness": 0.20, "context": 0.15, "consensus": 0.25},
    "research": {"base": 0.20, "trust": 0.25, "freshness": 0.15, "context": 0.15, "consensus": 0.25},
    "economico": {"base": 0.35, "trust": 0.10, "freshness": 0.10, "context": 0.30, "consensus": 0.15},
    "cabina": {"base": 0.30, "trust": 0.10, "freshness": 0.15, "context": 0.25, "consensus": 0.20},
}


def _get(item: Any, name: str, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _text_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Zà-ù0-9_]+", str(value or "").lower()) if len(token) > 2}


def _context_fit(item: Any, request, workflow: str) -> float:
    metadata = dict(_get(item, "metadata", {}) or {})
    item_tokens = _text_tokens(" ".join([str(_get(item, "title", "") or ""), str(_get(item, "content", "") or "")]))
    query_tokens = _text_tokens(str(getattr(request, "query", "") or ""))
    overlap = len(item_tokens & query_tokens)
    score = min(1.0, overlap / max(len(query_tokens), 1))

    fascicolo_id = str(getattr(request, "fascicolo_id", "") or "")
    if fascicolo_id and str(metadata.get("fascicolo_id") or metadata.get("scope_id") or "") == fascicolo_id:
        score = max(score, 1.0)
    if workflow in {"fascicolo", "udienza", "telematico_status"} and str(_get(item, "source_type", "")) in {"fascicolo", "documento", "agenda", "scadenziario", "telematico"}:
        score = min(1.0, score + 0.25)
    return round(score, 4)

def _normalized_base_score(item: Any) -> float:
    value = float(_get(item, "score", 0.0) or 0.0)
    if value <= 1.0:
        return max(0.0, value)
    return min(1.0, math.log10(value + 1.0))

def _trust_score(item: Any) -> float:
    metadata = dict(_get(item, "metadata", {}) or {})
    trust_class = str(_get(item, "trust_class", "") or metadata.get("trust_class") or "").upper()
    source_level = int(_get(item, "source_level", 0) or metadata.get("source_level") or 0)
    source_type = str(_get(item, "source_type", "") or "").strip().lower()
    authority = str(_get(item, "authority", "") or metadata.get("authority") or "").strip().lower()
    official_url = str(_get(item, "official_url", "") or metadata.get("official_url") or metadata.get("url") or "").strip().lower()
    verified_reference = bool(_get(item, "verified_reference", False) or metadata.get("verified_reference"))
    explicit = float(_get(item, "trust_score", 0.0) or 0.0)
    if explicit > 0:
        return min(1.0, explicit)
    if not trust_class and not source_level:
        if source_type == "web_ufficiale":
            trust_class, source_level = "A", 1
        elif source_type == "normativa" and official_url:
            trust_class, source_level = "A", 1
        elif source_type in {"giurisprudenza", "prassi"} and (verified_reference or official_url):
            trust_class, source_level = "B", 2
        elif source_type in {"legal_intelligence", "telematico", "compliance"} and (
            official_url or "official" in authority or "istituz" in authority
        ):
            trust_class, source_level = "B", 2
    bonus = _OFFICIAL_BONUS.get(trust_class, 0.0)
    if source_level == 1:
        bonus = max(bonus, 1.0)
    elif source_level == 2:
        bonus = max(bonus, 0.75)
    elif source_level == 3:
        bonus = max(bonus, 0.45)
    return round(min(1.0, bonus), 4)

def _freshness_score(item: Any) -> float:
    explicit = float(_get(item, "freshness_score", 0.0) or 0.0)
    if explicit > 0:
        return min(1.0, explicit)
    metadata = dict(_get(item, "metadata", {}) or {})
    published_at = str(_get(item, "published_at", "") or metadata.get("published_at") or "")
    if published_at:
        return 0.6
    return 0.35

def _consensus_score(item: Any, items: list[Any]) -> float:
    explicit = float(_get(item, "consensus_score", 0.0) or 0.0)
    if explicit > 0:
        return min(1.0, explicit)
    metadata = dict(_get(item, "metadata", {}) or {})
    authority = str(_get(item, "authority", "") or metadata.get("authority") or "")
    if not authority:
        return 0.3
    matches = 0
    for other in items:
        if other is item:
            continue
        other_metadata = dict(_get(other, "metadata", {}) or {})
        if str(_get(other, "authority", "") or other_metadata.get("authority") or "") == authority:
            matches += 1
    return min(1.0, 0.3 + (matches * 0.2))

def rank_evidence(items, request, workflow: str):
    rows = list(items or [])
    weights = _WORKFLOW_WEIGHTS.get(workflow, {"base": 0.25, "trust": 0.20, "freshness": 0.15, "context": 0.20, "consensus": 0.20})

    for item in rows:
        base = _normalized_base_score(item)
        trust = _trust_score(item)
        freshness = _freshness_score(item)
        context_fit = _context_fit(item, request, workflow)
        consensus = _consensus_score(item, rows)
        final_score = (
            (base * weights["base"])
            + (trust * weights["trust"])
            + (freshness * weights["freshness"])
            + (context_fit * weights["context"])
            + (consensus * weights["consensus"])
        )
        if not isinstance(item, dict):
            try:
                item.score = round(final_score, 6)
                item.trust_score = round(trust, 6)
                item.freshness_score = round(freshness, 6)
                item.context_fit_score = round(context_fit, 6)
                item.consensus_score = round(consensus, 6)
            except Exception:
                pass
        else:
            item["score"] = round(final_score, 6)
            item["trust_score"] = round(trust, 6)
            item["freshness_score"] = round(freshness, 6)
            item["context_fit_score"] = round(context_fit, 6)
            item["consensus_score"] = round(consensus, 6)

    return sorted(rows, key=lambda item: float(_get(item, "score", 0.0) or 0.0), reverse=True)
