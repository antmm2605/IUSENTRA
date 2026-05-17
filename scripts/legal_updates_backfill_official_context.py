from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


ContextHelper = Callable[[str, str], Mapping[str, Any]]

PERFORMED_BY = "legal_updates_backfill_official_context"
DEFAULT_CONTEXT_LIMIT = 3600

DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2}|(?:19|20)\d{2}-\d{2}-\d{2}|"
    r"\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
LEGAL_REFERENCE_RE = re.compile(
    r"\b(?P<kind>D\.?\s*Lgs\.?|Decreto\s+legislativo|D\.?\s*L\.?|Decreto[-\s]+legge|"
    r"Legge|D\.?\s*M\.?|Decreto\s+ministeriale|D\.?\s*P\.?\s*R\.?)"
    r"(?:\s+(?P<day>\d{1,2})\s+(?P<month>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(?P<date_year>(?:19|20)\d{2}),?)?"
    r"\s*(?:n\.?|numero)?\s*(?P<number>\d{1,5})(?:\s*/\s*|\s+del\s+)?(?P<slash_year>(?:19|20)\d{2})?",
    re.IGNORECASE,
)
CODICE_REDAZIONALE_RE = re.compile(r"\b(?P<year>\d{2})G(?P<number>\d{5})\b", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")

GENERIC_TEXT_PATTERNS = (
    re.compile(r"\bleggi\s+la\s+notizia\b", re.IGNORECASE),
    re.compile(r"\baggiornamento\s+giuridico\s+pubblicato\s+in\s+fonte\s+ufficiale\b", re.IGNORECASE),
    re.compile(r"\bcontenuto\s+generico\b", re.IGNORECASE),
    re.compile(r"\bnotizia\s+pubblicata\s+in\s+fonte\s+ufficiale\b", re.IGNORECASE),
    re.compile(r"\bapri\s+scheda\b", re.IGNORECASE),
)

NEWS_OLD_FIELDS = (
    "title",
    "slug",
    "short_summary",
    "content",
    "news_type",
    "matter_slug",
    "submatter_slug",
    "related_normative_id",
    "related_jurisprudence_id",
    "related_prassi_id",
    "source_url",
    "source_document_id",
    "is_auto_generated",
    "publication_status",
    "published_at",
)

NORMATIVE_OLD_FIELDS = (
    "title",
    "slug",
    "norm_type",
    "norm_number",
    "norm_year",
    "issuer",
    "publication_date",
    "effective_date",
    "status",
    "matter_slug",
    "submatter_slug",
    "source_url",
    "source_document_id",
    "text_official",
    "text_current",
    "summary",
    "notes",
)


def _clean(value: Any) -> str:
    return SPACE_RE.sub(" ", str(value or "").strip())


def _plain_text(value: Any) -> str:
    return _clean(TAG_RE.sub(" ", str(value or "")))


def _short(value: Any, limit: int = 700) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    if not isinstance(value, str):
        value = _stable_json(value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: Any) -> str:
    text = _clean(value).casefold()
    replacements = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "record"


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _query_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _generic_title(value: Any) -> bool:
    text = _clean(value).casefold()
    return not text or text in {"leggi la notizia", "notizia", "aggiornamento", "aggiornamenti"}


def _contains_generic_text(value: Any) -> bool:
    text = _clean(value)
    return any(pattern.search(text) for pattern in GENERIC_TEXT_PATTERNS)


def _count_marker(value: Any, marker: str) -> int:
    return len(re.findall(re.escape(marker), str(value or ""), flags=re.IGNORECASE))


def _date_count(value: Any) -> int:
    return len({match.group(0).casefold() for match in DATE_RE.finditer(str(value or ""))})


def _legal_reference_present(value: Any) -> bool:
    text = str(value or "")
    return LEGAL_REFERENCE_RE.search(text) is not None or CODICE_REDAZIONALE_RE.search(text) is not None


def suspicious_reasons(title: Any, *texts: Any) -> list[str]:
    title_text = _clean(title)
    combined = "\n".join(_plain_text(text) for text in (title, *texts) if text is not None)
    reasons: list[str] = []
    if _clean(title_text).casefold() == "leggi la notizia":
        reasons.append("title_leggi_la_notizia")
    if _count_marker(combined, "Leggi la notizia") >= 2:
        reasons.append("repeated_leggi_la_notizia")
    if _date_count(combined) >= 2 and (_contains_generic_text(combined) or _generic_title(title_text)):
        reasons.append("multiple_dates_in_cumulative_block")
    if _contains_generic_text(combined) and _legal_reference_present(combined):
        reasons.append("generic_content_with_legal_reference")
    if _generic_title(title_text) and _legal_reference_present(combined):
        reasons.append("generic_title_with_official_reference")
    return list(dict.fromkeys(reasons))


def _extract_normative_reference(*values: Any) -> dict[str, str]:
    text = " ".join(_clean(value) for value in values if value)
    match = LEGAL_REFERENCE_RE.search(text)
    if match:
        kind = _normalize_norm_type(match.group("kind"))
        year = match.group("slash_year") or match.group("date_year") or ""
        return {
            "norm_type": kind,
            "norm_number": _clean(match.group("number")),
            "norm_year": _clean(year),
        }
    redazionale = CODICE_REDAZIONALE_RE.search(text)
    if redazionale:
        return {
            "norm_type": "",
            "norm_number": str(int(redazionale.group("number"))),
            "norm_year": f"20{redazionale.group('year')}",
        }
    return {"norm_type": "", "norm_number": "", "norm_year": ""}


def _normalize_norm_type(value: Any) -> str:
    text = _clean(value).casefold().replace(" ", "")
    if "lgs" in text or "legislativo" in text:
        return "decreto legislativo"
    if text in {"d.l.", "dl"} or "decreto-legge" in text or "decretolegge" in text:
        return "decreto-legge"
    if text in {"d.m.", "dm"} or "ministeriale" in text:
        return "decreto ministeriale"
    if text in {"d.p.r.", "dpr"}:
        return "decreto del presidente della repubblica"
    if "legge" in text:
        return "legge"
    return _clean(value).casefold()


def _build_query(candidate: Mapping[str, Any]) -> str:
    old = candidate.get("old") if isinstance(candidate.get("old"), Mapping) else {}
    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), Mapping) else {}
    pieces = [
        old.get("title"),
        old.get("norm_type"),
        old.get("norm_number"),
        old.get("norm_year"),
        old.get("issuer"),
        evidence.get("normalized_title"),
        evidence.get("raw_title"),
        evidence.get("external_id"),
        candidate.get("source_url"),
    ]
    reference = _extract_normative_reference(*pieces, old.get("content"), old.get("text_official"))
    if reference.get("norm_number") and reference.get("norm_year"):
        kind = reference.get("norm_type") or "atto"
        return _clean(f"{kind} {reference['norm_number']}/{reference['norm_year']} {old.get('issuer') or evidence.get('source_name') or ''}")
    return _clean(" ".join(str(piece or "") for piece in pieces if piece))


def _default_context_helper(url: str, query: str) -> Mapping[str, Any]:
    try:
        from web.services.legal_official_context import build_official_context
    except Exception as exc:  # pragma: no cover - usato solo quando il servizio non e' disponibile.
        return {
            "officialContext": "",
            "contextSummary": "",
            "warnings": [f"Helper contesto ufficiale non disponibile: {_short(exc, 180)}."],
            "contextCompleted": False,
        }
    return build_official_context(url, query, context_limit=DEFAULT_CONTEXT_LIMIT)


def _normalize_context(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    context = _clean(
        data.get("officialContext")
        or data.get("official_context")
        or data.get("context")
        or data.get("text")
        or ""
    )
    summary = _clean(data.get("contextSummary") or data.get("summary") or "")
    title = _clean(data.get("officialTitle") or data.get("title") or "")
    key_points = data.get("keyPoints") or data.get("key_points") or []
    checks = data.get("operationalChecks") or data.get("operational_checks") or []
    warnings = data.get("warnings") or []
    return {
        "title": title,
        "officialContext": context,
        "contextSummary": summary,
        "keyPoints": [_clean(item) for item in key_points if _clean(item)],
        "operationalChecks": [_clean(item) for item in checks if _clean(item)],
        "warnings": [_clean(item) for item in warnings if _clean(item)],
        "contextCompleted": bool(data.get("contextCompleted") or data.get("context_completed") or context),
    }


def _fetch_context(helper: ContextHelper, url: str, query: str) -> dict[str, Any]:
    if not _clean(url):
        return {
            "title": "",
            "officialContext": "",
            "contextSummary": "",
            "keyPoints": [],
            "operationalChecks": [],
            "warnings": ["Fonte ufficiale assente nel record."],
            "contextCompleted": False,
        }
    try:
        return _normalize_context(helper(url, query))
    except Exception as exc:
        return {
            "title": "",
            "officialContext": "",
            "contextSummary": "",
            "keyPoints": [],
            "operationalChecks": [],
            "warnings": [f"Recupero contesto ufficiale non completato: {_short(exc, 180)}."],
            "contextCompleted": False,
        }


def _derive_title(context: Mapping[str, Any], old_title: Any, query: str) -> str:
    explicit = _clean(context.get("title"))
    if explicit and not _generic_title(explicit):
        return _short(explicit, 180)
    text = _clean(context.get("officialContext"))
    for chunk in re.split(r"(?<=[.!?])\s+|\n+", text):
        candidate = _clean(chunk)
        if not candidate:
            continue
        if _legal_reference_present(candidate) or candidate.casefold().startswith(("decreto", "legge", "d.lgs", "d.l.")):
            return _short(candidate, 180)
    if query and not _generic_title(query):
        return _short(query, 180)
    if old_title and not _generic_title(old_title):
        return _short(old_title, 180)
    return _short(text, 180) or "Aggiornamento da fonte ufficiale"


def _first_sentence(value: Any, limit: int = 420) -> str:
    text = _clean(value)
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    for part in parts:
        cleaned = _clean(part)
        if cleaned:
            return _short(cleaned, limit)
    return _short(text, limit)


def _compose_content(context: Mapping[str, Any]) -> str:
    official = _clean(context.get("officialContext"))
    pieces = [official]
    key_points = list(context.get("keyPoints") or [])
    checks = list(context.get("operationalChecks") or [])
    if key_points:
        pieces.append("Punti rilevanti:\n" + "\n".join(f"- {_clean(item)}" for item in key_points[:6]))
    if checks:
        pieces.append("Verifiche operative:\n" + "\n".join(f"- {_clean(item)}" for item in checks[:6]))
    return "\n\n".join(piece for piece in pieces if _clean(piece))


def _source_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": row.get("source_id"),
        "source_code": _clean(row.get("source_code")),
        "source_name": _clean(row.get("source_name")),
        "source_url": _clean(row.get("source_url") or row.get("raw_source_url")),
        "external_id": _clean(row.get("external_id")),
    }


def _news_old(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in NEWS_OLD_FIELDS}


def _normative_old(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in NORMATIVE_OLD_FIELDS}


def _candidate(
    entity_type: str,
    row: Mapping[str, Any],
    old: Mapping[str, Any],
    reasons: list[str],
    *,
    applyable: bool,
) -> dict[str, Any]:
    evidence = {
        "raw_document_id": row.get("raw_document_id"),
        "normalized_document_id": row.get("normalized_document_id") or old.get("source_document_id"),
        "review_id": row.get("review_id"),
        "review_status": row.get("review_status"),
        "raw_title": _clean(row.get("raw_title")),
        "normalized_title": _clean(row.get("normalized_title")),
        "external_id": _clean(row.get("external_id")),
        "source_name": _clean(row.get("source_name")),
    }
    source_url = _clean(old.get("source_url") or row.get("raw_source_url") or row.get("source_url"))
    return {
        "entity_type": entity_type,
        "entity_id": int(row.get("entity_id") or row.get("id") or 0),
        "applyable": applyable,
        "reasons": reasons,
        "source_url": source_url,
        "source": _source_payload({**row, "source_url": source_url}),
        "old": dict(old),
        "evidence": evidence,
    }


def discover_dirty_records(db_path: str | Path, *, limit: int = 0) -> list[dict[str, Any]]:
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Database legal_updates non trovato: {db}")
    candidates: list[dict[str, Any]] = []
    with _connect(db) as conn:
        if _table_exists(conn, "news"):
            rows = _query_rows(
                conn,
                """
                SELECT n.id AS entity_id, n.title, n.slug, n.short_summary, n.content,
                       n.news_type, n.related_normative_id, n.related_jurisprudence_id,
                       n.related_prassi_id, n.source_url, n.source_document_id,
                       n.is_auto_generated, n.publication_status, n.published_at,
                       m.slug AS matter_slug, sm.slug AS submatter_slug,
                       nd.id AS normalized_document_id, nd.title AS normalized_title,
                       nd.body_text AS normalized_body_text, nd.body_short AS normalized_body_short,
                       raw.id AS raw_document_id, raw.title AS raw_title, raw.raw_text, raw.raw_html,
                       raw.source_url AS raw_source_url, raw.external_id, raw.source_id,
                       s.code AS source_code, s.name AS source_name,
                       q.id AS review_id, q.status AS review_status, q.proposal_payload_json
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                LEFT JOIN source_documents_normalized nd ON nd.id = n.source_document_id
                LEFT JOIN source_documents_raw raw ON raw.id = nd.raw_document_id
                LEFT JOIN sources s ON s.id = raw.source_id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = nd.id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                ORDER BY n.id
                """,
            )
            for row in rows:
                old = _news_old(row)
                reasons = suspicious_reasons(
                    old.get("title"),
                    old.get("short_summary"),
                    old.get("content"),
                    row.get("normalized_title"),
                    row.get("normalized_body_text"),
                    row.get("raw_title"),
                    row.get("raw_text"),
                    row.get("raw_html"),
                    row.get("proposal_payload_json"),
                    row.get("external_id"),
                )
                if reasons:
                    candidates.append(_candidate("news", row, old, reasons, applyable=True))

        if _table_exists(conn, "normative"):
            rows = _query_rows(
                conn,
                """
                SELECT n.id AS entity_id, n.title, n.slug, n.norm_type, n.norm_number,
                       n.norm_year, n.issuer, n.publication_date, n.effective_date, n.status,
                       n.source_url, n.source_document_id, n.text_official, n.text_current,
                       n.summary, n.notes,
                       m.slug AS matter_slug, sm.slug AS submatter_slug,
                       nd.id AS normalized_document_id, nd.title AS normalized_title,
                       nd.body_text AS normalized_body_text, nd.body_short AS normalized_body_short,
                       raw.id AS raw_document_id, raw.title AS raw_title, raw.raw_text, raw.raw_html,
                       raw.source_url AS raw_source_url, raw.external_id, raw.source_id,
                       s.code AS source_code, s.name AS source_name,
                       q.id AS review_id, q.status AS review_status, q.proposal_payload_json
                FROM normative n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                LEFT JOIN source_documents_normalized nd ON nd.id = n.source_document_id
                LEFT JOIN source_documents_raw raw ON raw.id = nd.raw_document_id
                LEFT JOIN sources s ON s.id = raw.source_id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = nd.id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                ORDER BY n.id
                """,
            )
            for row in rows:
                old = _normative_old(row)
                reasons = suspicious_reasons(
                    old.get("title"),
                    old.get("summary"),
                    old.get("text_official"),
                    old.get("text_current"),
                    old.get("notes"),
                    row.get("normalized_title"),
                    row.get("normalized_body_text"),
                    row.get("raw_title"),
                    row.get("raw_text"),
                    row.get("raw_html"),
                    row.get("proposal_payload_json"),
                    row.get("external_id"),
                )
                if reasons:
                    candidates.append(_candidate("normative", row, old, reasons, applyable=True))

        if _table_exists(conn, "review_queue"):
            rows = _query_rows(
                conn,
                """
                SELECT q.id AS entity_id, q.status, q.proposed_action, q.proposal_payload_json,
                       q.review_notes, q.normalized_document_id, q.analysis_id,
                       nd.title AS normalized_title, nd.body_text AS normalized_body_text,
                       nd.body_short AS normalized_body_short, nd.document_date,
                       raw.id AS raw_document_id, raw.title AS raw_title, raw.raw_text, raw.raw_html,
                       raw.source_url AS raw_source_url, raw.external_id, raw.source_id,
                       s.code AS source_code, s.name AS source_name,
                       news.id AS linked_news_id, normative.id AS linked_normative_id
                FROM review_queue q
                LEFT JOIN source_documents_normalized nd ON nd.id = q.normalized_document_id
                LEFT JOIN source_documents_raw raw ON raw.id = nd.raw_document_id
                LEFT JOIN sources s ON s.id = raw.source_id
                LEFT JOIN news ON news.source_document_id = nd.id
                LEFT JOIN normative ON normative.source_document_id = nd.id
                ORDER BY q.id
                """,
            )
            for row in rows:
                old = {
                    "status": row.get("status"),
                    "proposed_action": row.get("proposed_action"),
                    "proposal_payload_json": row.get("proposal_payload_json"),
                    "review_notes": row.get("review_notes"),
                    "normalized_document_id": row.get("normalized_document_id"),
                    "analysis_id": row.get("analysis_id"),
                    "linked_news_id": row.get("linked_news_id"),
                    "linked_normative_id": row.get("linked_normative_id"),
                }
                reasons = suspicious_reasons(
                    row.get("normalized_title"),
                    row.get("proposal_payload_json"),
                    row.get("review_notes"),
                    row.get("normalized_body_text"),
                    row.get("normalized_body_short"),
                    row.get("raw_title"),
                    row.get("raw_text"),
                    row.get("raw_html"),
                    row.get("external_id"),
                )
                if reasons:
                    candidates.append(_candidate("review", row, old, reasons, applyable=False))

        if _table_exists(conn, "source_documents_raw"):
            rows = _query_rows(
                conn,
                """
                SELECT raw.id AS entity_id, raw.title, raw.published_at, raw.raw_text, raw.raw_html,
                       raw.source_url AS raw_source_url, raw.external_id, raw.content_hash,
                       raw.source_id, s.code AS source_code, s.name AS source_name,
                       nd.id AS normalized_document_id, nd.title AS normalized_title,
                       news.id AS linked_news_id, normative.id AS linked_normative_id,
                       q.id AS review_id, q.status AS review_status
                FROM source_documents_raw raw
                LEFT JOIN sources s ON s.id = raw.source_id
                LEFT JOIN source_documents_normalized nd ON nd.raw_document_id = raw.id
                LEFT JOIN news ON news.source_document_id = nd.id
                LEFT JOIN normative ON normative.source_document_id = nd.id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = nd.id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                ORDER BY raw.id
                """,
            )
            for row in rows:
                old = {
                    "title": row.get("title"),
                    "published_at": row.get("published_at"),
                    "raw_text": _short(row.get("raw_text"), 1400),
                    "raw_html": _short(_plain_text(row.get("raw_html")), 1400),
                    "content_hash": row.get("content_hash"),
                    "linked_news_id": row.get("linked_news_id"),
                    "linked_normative_id": row.get("linked_normative_id"),
                }
                reasons = suspicious_reasons(
                    row.get("title"),
                    row.get("raw_text"),
                    row.get("raw_html"),
                    row.get("normalized_title"),
                    row.get("external_id"),
                )
                if reasons:
                    candidates.append(_candidate("raw", row, old, reasons, applyable=False))

    if limit > 0:
        return candidates[:limit]
    return candidates


def _new_news_fields(candidate: Mapping[str, Any], context: Mapping[str, Any], query: str) -> dict[str, Any]:
    old = dict(candidate.get("old") or {})
    content = _compose_content(context)
    summary = _clean(context.get("contextSummary")) or _first_sentence(content)
    title = _derive_title(context, old.get("title"), query)
    return {
        **old,
        "title": title,
        "slug": _slugify(title),
        "short_summary": summary,
        "content": content,
        "source_url": _clean(old.get("source_url") or candidate.get("source_url")),
        "source_document_id": old.get("source_document_id"),
        "publication_status": old.get("publication_status") or "published",
        "published_at": old.get("published_at") or "",
    }


def _new_normative_fields(candidate: Mapping[str, Any], context: Mapping[str, Any], query: str) -> dict[str, Any]:
    old = dict(candidate.get("old") or {})
    content = _compose_content(context)
    summary = _clean(context.get("contextSummary")) or _first_sentence(content)
    title = _derive_title(context, old.get("title"), query)
    ref = _extract_normative_reference(
        title,
        query,
        old.get("text_official"),
        old.get("summary"),
        candidate.get("source_url"),
    )
    notes = _clean(old.get("notes"))
    backfill_note = "Backfill non distruttivo da fonte ufficiale; raw originale conservato."
    if backfill_note not in notes:
        notes = _clean("; ".join(part for part in (notes, backfill_note) if part))
    return {
        **old,
        "title": title,
        "slug": _slugify(title),
        "norm_type": old.get("norm_type") or ref.get("norm_type"),
        "norm_number": old.get("norm_number") or ref.get("norm_number"),
        "norm_year": old.get("norm_year") or ref.get("norm_year"),
        "issuer": old.get("issuer") or candidate.get("source", {}).get("source_name") or "Fonte ufficiale",
        "publication_date": old.get("publication_date") or "",
        "effective_date": old.get("effective_date") or old.get("publication_date") or "",
        "status": old.get("status") or "vigente",
        "source_url": _clean(old.get("source_url") or candidate.get("source_url")),
        "source_document_id": old.get("source_document_id"),
        "text_official": content,
        "text_current": content,
        "summary": summary,
        "notes": notes,
    }


def build_backfill_plan(
    db_path: str | Path,
    *,
    context_helper: ContextHelper | None = None,
    limit: int = 0,
    apply_changes: bool = False,
) -> dict[str, Any]:
    helper = context_helper or _default_context_helper
    candidates = discover_dirty_records(db_path, limit=limit)
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        query = _build_query(candidate)
        context = _fetch_context(helper, str(candidate.get("source_url") or ""), query)
        entity_type = str(candidate.get("entity_type"))
        if entity_type == "news" and context.get("officialContext"):
            new_fields = _new_news_fields(candidate, context, query)
            status = "ready"
        elif entity_type == "normative" and context.get("officialContext"):
            new_fields = _new_normative_fields(candidate, context, query)
            status = "ready"
        else:
            new_fields = dict(candidate.get("old") or {})
            status = "context_only" if context.get("officialContext") else "missing_context"
        old_fields = dict(candidate.get("old") or {})
        items.append(
            {
                **candidate,
                "query": query,
                "status": status,
                "new": new_fields,
                "hashes": {
                    "old_sha256": _sha256(old_fields),
                    "new_sha256": _sha256(new_fields),
                    "official_context_sha256": _sha256(context.get("officialContext") or ""),
                },
                "official_context": {
                    "completed": bool(context.get("contextCompleted")),
                    "warnings": list(context.get("warnings") or []),
                    "summary": _short(context.get("contextSummary"), 700),
                },
            }
        )
    return {
        "tool": "legal_updates_backfill_official_context",
        "mode": "apply" if apply_changes else "dry-run",
        "dry_run": not apply_changes,
        "db_path": str(Path(db_path)),
        "generated_at": _now(),
        "stats": {
            "candidates": len(candidates),
            "items": len(items),
            "applyable_ready": sum(1 for item in items if item.get("applyable") and item.get("status") == "ready"),
            "diagnostic_only": sum(1 for item in items if not item.get("applyable")),
        },
        "items": items,
    }


def _load_current_news(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT n.title, n.slug, n.short_summary, n.content, n.news_type,
               m.slug AS matter_slug, sm.slug AS submatter_slug,
               n.related_normative_id, n.related_jurisprudence_id, n.related_prassi_id,
               n.source_url, n.source_document_id, n.is_auto_generated,
               n.publication_status, n.published_at
        FROM news n
        LEFT JOIN matters m ON m.id = n.matter_id
        LEFT JOIN matters sm ON sm.id = n.submatter_id
        WHERE n.id = ?
        """,
        (int(entity_id),),
    ).fetchone()
    return {field: _row_dict(row).get(field) for field in NEWS_OLD_FIELDS}


def _load_current_normative(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT n.title, n.slug, n.norm_type, n.norm_number, n.norm_year, n.issuer,
               n.publication_date, n.effective_date, n.status,
               m.slug AS matter_slug, sm.slug AS submatter_slug,
               n.source_url, n.source_document_id, n.text_official, n.text_current,
               n.summary, n.notes
        FROM normative n
        LEFT JOIN matters m ON m.id = n.matter_id
        LEFT JOIN matters sm ON sm.id = n.submatter_id
        WHERE n.id = ?
        """,
        (int(entity_id),),
    ).fetchone()
    return {field: _row_dict(row).get(field) for field in NORMATIVE_OLD_FIELDS}


def _matter_id(conn: sqlite3.Connection, slug: Any) -> int | None:
    slug_text = _clean(slug).casefold()
    if not slug_text or not _table_exists(conn, "matters"):
        return None
    row = conn.execute("SELECT id FROM matters WHERE slug = ? LIMIT 1", (slug_text,)).fetchone()
    return int(row["id"]) if row else None


def _unique_slug(conn: sqlite3.Connection, table: str, slug: str, entity_id: int) -> str:
    base = _slugify(slug)
    candidate = base
    suffix = 2
    while True:
        row = conn.execute(
            f"SELECT id FROM {table} WHERE slug = ? AND id <> ? LIMIT 1",
            (candidate, int(entity_id)),
        ).fetchone()
        if not row:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def _insert_audit(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    action: str,
    old_data: Mapping[str, Any],
    new_data: Mapping[str, Any],
    performed_by: str,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (entity_type, entity_id, action, old_data_json, new_data_json, performed_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            entity_type,
            int(entity_id),
            action,
            _stable_json(dict(old_data)),
            _stable_json(dict(new_data)),
            performed_by,
        ),
    )


def _apply_news_sqlite(conn: sqlite3.Connection, item: Mapping[str, Any], performed_by: str) -> dict[str, Any]:
    entity_id = int(item["entity_id"])
    old = _load_current_news(conn, entity_id)
    new = dict(item.get("new") or {})
    new["slug"] = _unique_slug(conn, "news", str(new.get("slug") or new.get("title")), entity_id)
    conn.execute(
        """
        UPDATE news
        SET title = ?, slug = ?, short_summary = ?, content = ?, news_type = ?,
            matter_id = ?, submatter_id = ?, related_normative_id = ?,
            related_jurisprudence_id = ?, related_prassi_id = ?, source_url = ?,
            source_document_id = ?, is_auto_generated = ?, publication_status = ?,
            published_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _clean(new.get("title")),
            _clean(new.get("slug")),
            str(new.get("short_summary") or ""),
            str(new.get("content") or ""),
            _clean(new.get("news_type") or "focus").casefold(),
            _matter_id(conn, new.get("matter_slug")),
            _matter_id(conn, new.get("submatter_slug")),
            new.get("related_normative_id"),
            new.get("related_jurisprudence_id"),
            new.get("related_prassi_id"),
            _clean(new.get("source_url")),
            new.get("source_document_id"),
            1 if new.get("is_auto_generated", True) else 0,
            _clean(new.get("publication_status") or "published").casefold(),
            _clean(new.get("published_at")),
            entity_id,
        ),
    )
    updated = _load_current_news(conn, entity_id)
    _insert_audit(conn, "news", entity_id, "update", old, updated, performed_by)
    return updated


def _apply_normative_sqlite(conn: sqlite3.Connection, item: Mapping[str, Any], performed_by: str) -> dict[str, Any]:
    entity_id = int(item["entity_id"])
    old = _load_current_normative(conn, entity_id)
    new = dict(item.get("new") or {})
    new["slug"] = _unique_slug(conn, "normative", str(new.get("slug") or new.get("title")), entity_id)
    conn.execute(
        """
        UPDATE normative
        SET title = ?, slug = ?, norm_type = ?, norm_number = ?, norm_year = ?,
            issuer = ?, publication_date = ?, effective_date = ?, status = ?,
            matter_id = ?, submatter_id = ?, source_url = ?, source_document_id = ?,
            text_official = ?, text_current = ?, summary = ?, notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _clean(new.get("title")),
            _clean(new.get("slug")),
            _clean(new.get("norm_type")).casefold(),
            _clean(new.get("norm_number")),
            _clean(new.get("norm_year")),
            _clean(new.get("issuer")),
            _clean(new.get("publication_date")),
            _clean(new.get("effective_date")),
            _clean(new.get("status") or "vigente").casefold(),
            _matter_id(conn, new.get("matter_slug")),
            _matter_id(conn, new.get("submatter_slug")),
            _clean(new.get("source_url")),
            new.get("source_document_id"),
            str(new.get("text_official") or ""),
            str(new.get("text_current") or new.get("text_official") or ""),
            str(new.get("summary") or ""),
            str(new.get("notes") or ""),
            entity_id,
        ),
    )
    conn.execute(
        """
        INSERT INTO normative_versions (
            normative_id, version_label, valid_from, valid_to, text_version,
            source_url, source_document_id, created_at
        )
        VALUES (?, ?, ?, '', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            entity_id,
            "Backfill contesto ufficiale",
            _clean(new.get("effective_date") or new.get("publication_date")),
            str(new.get("text_current") or new.get("text_official") or ""),
            _clean(new.get("source_url")),
            new.get("source_document_id"),
        ),
    )
    updated = _load_current_normative(conn, entity_id)
    _insert_audit(conn, "normative", entity_id, "update", old, updated, performed_by)
    return updated


def _repository_or_none(db_path: str | Path) -> Any:
    try:
        from pct.legal_update_repository import LegalUpdateRepository
    except Exception:
        return None
    try:
        return LegalUpdateRepository(str(db_path), json_path="")
    except Exception:
        return None


def _apply_with_repository(repo: Any, item: Mapping[str, Any], db_path: str | Path, performed_by: str) -> dict[str, Any] | None:
    entity_type = str(item.get("entity_type") or "")
    new = dict(item.get("new") or {})
    entity_id = int(item.get("entity_id") or 0)
    with _connect(db_path) as conn:
        if entity_type == "news":
            new["slug"] = _unique_slug(conn, "news", str(new.get("slug") or new.get("title")), entity_id)
        elif entity_type == "normative":
            new["slug"] = _unique_slug(conn, "normative", str(new.get("slug") or new.get("title")), entity_id)

    if entity_type == "news" and hasattr(repo, "create_or_update_news"):
        if not (new.get("source_document_id") or new.get("source_url")):
            return None
        return repo.create_or_update_news(
            {
                "title": new.get("title"),
                "slug": new.get("slug"),
                "short_summary": new.get("short_summary"),
                "content": new.get("content"),
                "news_type": new.get("news_type"),
                "matter_slug": new.get("matter_slug"),
                "submatter_slug": new.get("submatter_slug"),
                "related_normative_id": new.get("related_normative_id"),
                "related_jurisprudence_id": new.get("related_jurisprudence_id"),
                "related_prassi_id": new.get("related_prassi_id"),
                "source_url": new.get("source_url"),
                "source_document_id": new.get("source_document_id"),
                "is_auto_generated": bool(new.get("is_auto_generated", True)),
                "publication_status": new.get("publication_status") or "published",
                "published_at": new.get("published_at") or "",
            },
            performed_by=performed_by,
        )
    if entity_type == "normative" and hasattr(repo, "create_or_update_normative"):
        if not (new.get("source_document_id") or new.get("source_url") or (new.get("norm_type") and new.get("norm_number") and new.get("norm_year"))):
            return None
        return repo.create_or_update_normative(
            {
                "title": new.get("title"),
                "slug": new.get("slug"),
                "norm_type": new.get("norm_type"),
                "norm_number": new.get("norm_number"),
                "norm_year": new.get("norm_year"),
                "issuer": new.get("issuer"),
                "publication_date": new.get("publication_date"),
                "effective_date": new.get("effective_date") or new.get("publication_date"),
                "status": new.get("status") or "vigente",
                "matter_slug": new.get("matter_slug"),
                "submatter_slug": new.get("submatter_slug"),
                "source_url": new.get("source_url"),
                "source_document_id": new.get("source_document_id"),
                "text_official": new.get("text_official"),
                "text_current": new.get("text_current") or new.get("text_official"),
                "summary": new.get("summary"),
                "notes": new.get("notes"),
                "version_label": "Backfill contesto ufficiale",
            },
            performed_by=performed_by,
        )
    return None


def apply_backfill_plan(
    db_path: str | Path,
    plan: Mapping[str, Any],
    *,
    performed_by: str = PERFORMED_BY,
    prefer_repository_api: bool = True,
) -> dict[str, Any]:
    repo = _repository_or_none(db_path) if prefer_repository_api else None
    report = {"applied": 0, "skipped": 0, "errors": 0, "items": []}
    for item in list(plan.get("items") or []):
        entity_type = str(item.get("entity_type") or "")
        entity_id = int(item.get("entity_id") or 0)
        if not item.get("applyable") or item.get("status") != "ready" or entity_type not in {"news", "normative"}:
            report["skipped"] += 1
            report["items"].append({"entity_type": entity_type, "entity_id": entity_id, "status": "skipped", "reason": "diagnostic_only"})
            continue

        with _connect(db_path) as conn:
            current = _load_current_news(conn, entity_id) if entity_type == "news" else _load_current_normative(conn, entity_id)
        if _sha256(current) != item.get("hashes", {}).get("old_sha256"):
            report["skipped"] += 1
            report["items"].append({"entity_type": entity_type, "entity_id": entity_id, "status": "skipped", "reason": "stale_record"})
            continue

        try:
            updated = _apply_with_repository(repo, item, db_path, performed_by) if repo is not None else None
            used = "repository_api" if updated is not None else "sqlite_transaction"
            if updated is None:
                with _connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    if entity_type == "news":
                        updated = _apply_news_sqlite(conn, item, performed_by)
                    else:
                        updated = _apply_normative_sqlite(conn, item, performed_by)
                    conn.commit()
            report["applied"] += 1
            report["items"].append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "status": "applied",
                    "writer": used,
                    "new_sha256": _sha256(updated),
                }
            )
        except Exception as exc:
            report["errors"] += 1
            report["items"].append(
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "status": "error",
                    "reason": _short(exc, 220),
                }
            )
    return report


def run_backfill(
    db_path: str | Path,
    *,
    apply_changes: bool = False,
    context_helper: ContextHelper | None = None,
    limit: int = 0,
    performed_by: str = PERFORMED_BY,
    prefer_repository_api: bool = True,
) -> dict[str, Any]:
    plan = build_backfill_plan(
        db_path,
        context_helper=context_helper,
        limit=limit,
        apply_changes=apply_changes,
    )
    if apply_changes:
        plan["apply"] = apply_backfill_plan(
            db_path,
            plan,
            performed_by=performed_by,
            prefer_repository_api=prefer_repository_api,
        )
    return plan


def _resolve_db_path(args: argparse.Namespace) -> str:
    if args.db:
        return str(Path(args.db))
    if os.getenv("LEGAL_UPDATES_DB"):
        return os.getenv("LEGAL_UPDATES_DB", "")
    intelligence = args.intelligence_db or os.getenv("PCT_LEGAL_INTELLIGENCE_DB") or os.getenv("LEGAL_INTELLIGENCE_DB")
    if intelligence:
        return str(Path(intelligence).resolve().with_name("legal_updates.db"))
    return str(Path("./intelligence/legal_updates.db"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill non distruttivo del contesto ufficiale in legal_updates.db. Default: dry-run.",
    )
    parser.add_argument("--db", help="Percorso esplicito di legal_updates.db.")
    parser.add_argument("--intelligence-db", help="Anchor motori.json da cui derivare legal_updates.db.")
    parser.add_argument("--apply", action="store_true", help="Applica le modifiche pianificate. Senza questo flag non scrive nulla.")
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di candidati da pianificare.")
    parser.add_argument("--output", help="File JSON del piano. Se omesso stampa su stdout.")
    parser.add_argument("--no-repository-api", action="store_true", help="Forza il fallback SQLite transazionale.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    db_path = _resolve_db_path(args)
    plan = run_backfill(
        db_path,
        apply_changes=bool(args.apply),
        limit=max(0, int(args.limit or 0)),
        prefer_repository_api=not bool(args.no_repository_api),
    )
    payload = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        sys.stdout.write(payload + "\n")
    return 1 if plan.get("apply", {}).get("errors") else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
