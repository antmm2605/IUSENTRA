from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from lex.research.source_policy.inference import get_tier_for_domain, infer_area, normalize_domain
from lex.research.source_policy.models import Tier


STRUCTURED_ACTIONS = {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _truncate(value: Any, limit: int = 260) -> str:
    text = _clean_spaces(value)
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _domain(value: Any) -> str:
    return normalize_domain(urlparse(str(value or "").strip()).netloc or str(value or ""))


def _source_ids_for_review(review: dict[str, Any], source: dict[str, Any]) -> list[str]:
    text = " ".join(
        _clean_spaces(part).lower()
        for part in (
            review.get("classification_type"),
            review.get("proposed_action"),
            review.get("source_code"),
            review.get("source_name"),
            source.get("code"),
            source.get("category"),
            review.get("title"),
        )
    )
    rows: list[str] = []

    def _push(value: str) -> None:
        if value and value not in rows:
            rows.append(value)

    if "cassazione" in text or "giurisprudenza" in text or "case_law" in text:
        _push("cassazione")
    if "gazzetta" in text or "normativa" in text or "normative" in text or "decreto" in text or "legge" in text:
        _push("gazzetta_ufficiale")
        _push("normattiva")
    if "eur" in text or "ue" in text:
        _push("eur_lex")
    if "agenzia" in text or "entrate" in text:
        _push("agenzia_entrate")
    if "lavoro" in text:
        _push("ministero_lavoro")
    return rows[:4]


def _verification_query(review: dict[str, Any]) -> str:
    parts = [
        review.get("title"),
        review.get("source_name"),
        review.get("document_date") or review.get("published_at"),
        review.get("decision_number"),
        review.get("decision_year"),
        review.get("norm_type"),
        review.get("norm_number"),
        review.get("norm_year"),
        review.get("matter_name") or review.get("matter_slug"),
    ]
    return _truncate(" ".join(_clean_spaces(part) for part in parts if _clean_spaces(part)), 420)


def _reference_tokens(review: dict[str, Any]) -> dict[str, str]:
    return {
        "decision_number": _clean_spaces(review.get("decision_number")),
        "decision_year": _clean_spaces(review.get("decision_year")),
        "norm_number": _clean_spaces(review.get("norm_number")),
        "norm_year": _clean_spaces(review.get("norm_year")),
        "title": _clean_spaces(review.get("title")),
    }


def _title_token_overlap(expected: str, candidate: str) -> int:
    expected_tokens = {
        token
        for token in re.findall(r"[^\W_]{5,}", expected.lower(), flags=re.UNICODE)
        if token not in {"della", "degli", "delle", "ordinanza", "sentenza", "decreto", "legge"}
    }
    candidate_text = candidate.lower()
    return sum(1 for token in expected_tokens if token in candidate_text)


def _matches_review_reference(row: dict[str, Any], review: dict[str, Any]) -> bool:
    ref = _reference_tokens(review)
    haystack = " ".join(
        _clean_spaces(row.get(key))
        for key in (
            "title",
            "titolo",
            "excerpt",
            "testo",
            "content",
            "url",
            "url_origine",
            "official_url",
            "source_name",
            "fonte",
        )
    ).lower()
    if ref["decision_number"] and ref["decision_year"]:
        return ref["decision_number"].lower() in haystack and ref["decision_year"].lower() in haystack
    if ref["norm_number"] and ref["norm_year"]:
        return ref["norm_number"].lower() in haystack and ref["norm_year"].lower() in haystack
    if ref["title"]:
        return _title_token_overlap(ref["title"], haystack) >= 2
    return False


def _confirmation_from_row(
    row: dict[str, Any],
    *,
    origin: str,
    review: dict[str, Any],
) -> dict[str, Any] | None:
    if not _matches_review_reference(row, review):
        return None
    url = _clean_spaces(row.get("url") or row.get("official_url") or row.get("url_origine"))
    domain = _domain(url)
    area = infer_area(_verification_query(review))
    tier = get_tier_for_domain(domain, area).value if domain else Tier.UNKNOWN.value
    source_name = _clean_spaces(row.get("source_name") or row.get("fonte") or row.get("source_id") or origin)
    return {
        "origin": origin,
        "title": _truncate(row.get("title") or row.get("titolo") or row.get("source_name") or source_name, 180),
        "source_name": source_name,
        "url": url,
        "domain": domain,
        "tier": tier,
        "official": tier == Tier.TIER_1.value or bool(row.get("official") or row.get("verified_reference")),
        "excerpt": _truncate(row.get("excerpt") or row.get("testo") or row.get("content"), 220),
    }


def _self_confirmation(review: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    url = _clean_spaces(review.get("source_url"))
    domain = _domain(url)
    if not domain:
        return None
    area = infer_area(_verification_query(review))
    tier = get_tier_for_domain(domain, area).value
    official = tier == Tier.TIER_1.value or bool(source.get("is_official"))
    if not official:
        return None
    return {
        "origin": "fonte_acquisita",
        "title": _truncate(review.get("title"), 180),
        "source_name": _clean_spaces(source.get("name") or review.get("source_name")),
        "url": url,
        "domain": domain,
        "tier": tier,
        "official": True,
        "excerpt": _truncate(review.get("summary_short") or review.get("body_short"), 220),
    }


def _deduplicate_confirmations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = _clean_spaces(row.get("url")) or f"{row.get('source_name')}|{row.get('title')}"
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def verify_legal_update_against_public_sources(
    review: dict[str, Any],
    source: dict[str, Any],
    *,
    limit: int = 5,
) -> dict[str, Any]:
    from lex.retrieval.official_sources_retriever import search_gazzetta, search_normattiva, search_official_sources
    from lex.retrieval.official_web import search_recognized_official_web

    action = _clean_spaces(review.get("proposed_action")).upper()
    query = _verification_query(review)
    confirmations: list[dict[str, Any]] = []
    warnings: list[str] = []
    searched: dict[str, Any] = {"query": query, "source_ids": _source_ids_for_review(review, source)}

    self_match = _self_confirmation(review, source)
    if self_match:
        confirmations.append(self_match)

    try:
        for row in search_official_sources(query, limit=limit):
            match = _confirmation_from_row(row, origin="archivio_fonti_ufficiali", review=review)
            if match:
                confirmations.append(match)
    except Exception as exc:
        warnings.append(f"Archivio fonti ufficiali non consultabile: {_truncate(exc, 140)}")

    try:
        for row in search_normattiva(query, limit=limit):
            match = _confirmation_from_row(row, origin="archivio_normattiva", review=review)
            if match:
                confirmations.append(match)
    except Exception as exc:
        warnings.append(f"Archivio Normattiva non consultabile: {_truncate(exc, 140)}")

    if action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEWS_ONLY"}:
        try:
            for row in search_gazzetta(query, limit=limit):
                match = _confirmation_from_row(row, origin="archivio_gazzetta", review=review)
                if match:
                    confirmations.append(match)
        except Exception as exc:
            warnings.append(f"Archivio Gazzetta non consultabile: {_truncate(exc, 140)}")

    try:
        web_rows = search_recognized_official_web(
            query,
            source_ids=list(searched["source_ids"] or []),
            limit_results=limit,
        )
        searched["web_results"] = len(web_rows)
        for row in web_rows:
            match = _confirmation_from_row(row, origin="ricerca_web_governata", review=review)
            if match:
                confirmations.append(match)
    except Exception as exc:
        searched["web_results"] = 0
        warnings.append(f"Ricerca web governata non completata: {_truncate(exc, 140)}")

    confirmations = _deduplicate_confirmations(confirmations)
    official_count = sum(1 for row in confirmations if bool(row.get("official")))
    required_confirmations = 2 if action in STRUCTURED_ACTIONS else 1
    verified = official_count >= 1 and len(confirmations) >= required_confirmations
    if not verified and action in STRUCTURED_ACTIONS:
        reason = "Servono almeno una fonte primaria e una seconda conferma coerente prima della pubblicazione automatica."
    elif not verified:
        reason = "Nessuna fonte pubblica coerente trovata per la pubblicazione automatica."
    else:
        reason = "Verifica pubblica completata con fonti coerenti."

    return {
        "ok": verified,
        "status": "verified" if verified else "insufficient",
        "query": query,
        "required_confirmations": required_confirmations,
        "official_confirmations": official_count,
        "confirmation_count": len(confirmations),
        "confirmations": confirmations,
        "warnings": warnings,
        "searched": searched,
        "reason": reason,
    }


__all__ = ["verify_legal_update_against_public_sources"]
