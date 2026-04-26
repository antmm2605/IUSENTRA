"""Ranking applicativo della Ricerca Studio."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .normalizer import normalize_identifier, normalize_search_text

EXACT_FIELDS = (
    "rg",
    "numero_rg",
    "codice_fiscale",
    "partita_iva",
    "email",
    "telefono",
    "numero",
    "numero_fattura",
)


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def compute_score(row: dict[str, Any], query: str, base_score: float = 0.0) -> float:
    q_norm = normalize_search_text(query)
    q_id = normalize_identifier(query)
    title = normalize_search_text(row.get("title", ""))
    subtitle = normalize_search_text(row.get("subtitle", ""))
    keywords = normalize_search_text(row.get("keywords", ""))
    body = normalize_search_text(row.get("body", ""))
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    score = max(0.0, 100.0 - abs(float(base_score or 0.0)) * 10)

    if q_norm and q_norm == title:
        score += 120
    elif q_norm and q_norm in title:
        score += 80
    if q_norm and q_norm in subtitle:
        score += 45
    if q_norm and q_norm in keywords:
        score += 40
    if q_norm and q_norm in body:
        score += 20

    for field in EXACT_FIELDS:
        candidate = normalize_identifier(metadata.get(field) or row.get(field) or "")
        if q_id and candidate and q_id == candidate:
            score += 160
        elif q_id and candidate and q_id in candidate:
            score += 90

    stato = normalize_search_text(metadata.get("stato", ""))
    if "attiv" in stato or "apert" in stato or "in corso" in stato:
        score += 25
    if "archiv" in stato or "storico" in stato or "chius" in stato:
        score -= 25
    if metadata.get("non_letto") in (True, "true", "1", "si"):
        score += 35
    if metadata.get("firmato") in (True, "true", "1", "si"):
        score += 20
    if metadata.get("ufficiale") in (True, "true", "1", "si"):
        score += 20

    scadenza = _parse_date(metadata.get("data_scadenza") or metadata.get("date"))
    if scadenza:
        delta = (scadenza - date.today()).days
        if 0 <= delta <= 14:
            score += 45
        elif delta < 0:
            score -= 15

    updated = _parse_date(row.get("updated_at") or metadata.get("updated_at"))
    if updated:
        age = (date.today() - updated).days
        if age <= 30:
            score += 15
        elif age > 365:
            score -= 8

    return round(score, 4)
