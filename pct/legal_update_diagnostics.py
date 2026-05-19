from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Callable

import requests

from pct.legal_context_questions import generate_context_questions
from pct.legal_reference_extractor import extract_references, reference_labels
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS, RequestGet, build_legal_update_pipeline
from pct.legal_update_source_capabilities import (
    get_source_capability,
    publication_destination_label,
    source_exclusion_reason,
)


CANARY_SCHEMA = "iusentra.legal_updates.canary.v1"
BACKFILL_SCHEMA = "iusentra.legal_updates.backfill_diagnostics.v1"
MISSING_KINDS = {"attachments", "ocr", "references", "questions"}
MAX_CANARY_LIMIT = 50
MAX_BACKFILL_LIMIT = 250
MAX_ATTACHMENTS_PER_DOCUMENT = 4


def run_legal_updates_canary(
    *,
    intelligence_db: str,
    giurisprudenza_db: str = "",
    source_code: str,
    limit: int,
    max_seconds: int = 60,
    no_publish: bool = True,
    direct_only: bool = True,
    save_diagnostics: bool = False,
    request_get: RequestGet = requests.get,
) -> dict[str, Any]:
    """Esegue una prova controllata su una sola fonte, con limite obbligatorio."""

    code = _clean_code(source_code)
    safe_limit = _required_limit(limit, max_limit=MAX_CANARY_LIMIT)
    started_at = _utc_now_iso()
    started = time.monotonic()
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    skipped_unchanged = 0
    verification_attempts = 0
    verification_saved = 0
    verification_attachments = 0
    autopublished = {"count": 0, "items": []}
    stopped_for_time_limit = False

    pipeline = build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db,
    )
    pipeline.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))
    source = pipeline.repository.get_source_by_code(code)
    if not source:
        raise ValueError(f"Fonte non configurata: {source_code}")

    documents: list[dict[str, Any]] = []
    with _limited_source_environment(safe_limit):
        try:
            documents = pipeline._fetch_source(source, request_get=request_get)
        except Exception as exc:
            errors.append(f"Lettura fonte non completata: {_truncate(exc)}")

    for document in documents[:safe_limit]:
        if _time_exhausted(started, max_seconds):
            stopped_for_time_limit = True
            break
        item = _document_diagnostic(source, document)
        try:
            existing = pipeline.repository.get_raw_document_by_external(
                int(source["id"]),
                str(document.get("external_id") or ""),
            )
            if existing and _clean(existing.get("content_hash")) == _clean(document.get("content_hash")):
                skipped_unchanged += 1
                item["status"] = "invariato"
                items.append(item)
                continue
            processed = pipeline.process_document(source, document, direct_only=direct_only)
            evidence = processed.get("verification_evidence") if isinstance(processed, dict) else {}
            verification_attempts += int(evidence.get("attempted") or 0)
            verification_saved += int(evidence.get("saved") or 0)
            verification_attachments += int(evidence.get("attachments") or 0)
            review = processed.get("review") if isinstance(processed, dict) else {}
            review_id = int((review or {}).get("id") or 0)
            item.update(
                {
                    "status": "analizzato",
                    "review_id": review_id or None,
                    "normalized_document_id": int((review or {}).get("normalized_document_id") or 0) or None,
                    "verification": evidence,
                }
            )
            if review_id:
                quality = pipeline.repository.web_evidence_quality_for_review(review_id, review=review)
                item["quality"] = _quality_summary(quality)
        except Exception as exc:
            message = f"Elemento non completato: {_truncate(exc)}"
            item.update({"status": "errore", "error": message})
            errors.append(message)
        items.append(item)

    if not no_publish and not stopped_for_time_limit:
        autopublished = pipeline.publish_auto_news(limit=min(safe_limit, 20))

    duration_ms = int((time.monotonic() - started) * 1000)
    status = "timeout" if stopped_for_time_limit else ("failed" if errors else "completed")
    result: dict[str, Any] = {
        "schema": CANARY_SCHEMA,
        "ok": not errors and not stopped_for_time_limit,
        "mode": "canary",
        "source_code": code,
        "source_name": source.get("name") or "",
        "limit": safe_limit,
        "max_seconds": max(0, int(max_seconds or 0)),
        "no_publish": bool(no_publish),
        "direct_only": bool(direct_only),
        "documents_found": len(documents),
        "processed": sum(1 for item in items if item.get("status") == "analizzato"),
        "skipped_unchanged": skipped_unchanged,
        "web_verification_attempts": verification_attempts,
        "verification_evidence_saved": verification_saved,
        "verification_attachments_saved": verification_attachments,
        "autopublished": autopublished,
        "stopped_for_time_limit": stopped_for_time_limit,
        "duration_seconds": round(duration_ms / 1000, 2),
        "items": items,
        "errors": errors,
    }
    if errors:
        result["inner_errors"] = errors[:8]

    if save_diagnostics:
        pipeline.repository.record_source_agent_run(
            source_code=code,
            source_name=str(source.get("name") or ""),
            trigger_label="canary",
            status=status,
            timeout_seconds=max(0, int(max_seconds or 0)),
            started_at=started_at,
            finished_at=_utc_now_iso(),
            duration_ms=duration_ms,
            documents_found=len(documents),
            processed=int(result["processed"]),
            skipped_unchanged=skipped_unchanged,
            autopublished_count=int((autopublished or {}).get("count") or 0),
            error_message="; ".join(errors[:3]),
            payload=result,
        )
        result["diagnostics_saved"] = True
    else:
        result["diagnostics_saved"] = False
    return result


def run_legal_updates_backfill_diagnostics(
    *,
    intelligence_db: str,
    giurisprudenza_db: str = "",
    source_code: str = "",
    review_id: int = 0,
    query: str = "",
    missing: str,
    limit: int,
    max_seconds: int = 60,
    include_closed: bool = False,
    include_open_data: bool = False,
    no_publish: bool = True,
) -> dict[str, Any]:
    """Esegue un backfill mirato senza scansioni infinite e senza pubblicazione automatica."""

    missing_kind = _clean_code(missing)
    if missing_kind not in MISSING_KINDS:
        raise ValueError("Valore --missing non valido: usare attachments, ocr, references o questions.")
    safe_limit = _required_limit(limit, max_limit=MAX_BACKFILL_LIMIT)
    code = _clean_code(source_code)
    pipeline = build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db,
    )
    pipeline.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))

    if missing_kind in {"attachments", "ocr"}:
        report = pipeline.backfill_web_verification_evidence(
            limit=safe_limit,
            source_codes=[code] if code else None,
            include_closed=include_closed,
            include_open_data=include_open_data,
            direct_only=True,
            max_seconds=max(0, int(max_seconds or 0)),
            query=query,
            review_ids=(int(review_id),) if int(review_id or 0) > 0 else (),
        )
        report.update(
            {
                "schema": BACKFILL_SCHEMA,
                "mode": "backfill_diagnostics",
                "missing": missing_kind,
                "no_publish": bool(no_publish),
            }
        )
        if not no_publish:
            report["autopublished"] = pipeline.publish_auto_news(limit=min(safe_limit, 20))
        else:
            report.setdefault("autopublished", {"count": 0, "items": []})
        return report

    report = _backfill_evidence_enrichment(
        pipeline.repository,
        missing=missing_kind,
        source_code=code,
        review_id=int(review_id or 0),
        query=query,
        limit=safe_limit,
        max_seconds=max(0, int(max_seconds or 0)),
        include_closed=include_closed,
        include_open_data=include_open_data,
    )
    report.update(
        {
            "schema": BACKFILL_SCHEMA,
            "mode": "backfill_diagnostics",
            "missing": missing_kind,
            "no_publish": bool(no_publish),
            "autopublished": {"count": 0, "items": []},
        }
    )
    return report


def _document_diagnostic(source: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    body = _clean(
        " ".join(
            str(document.get(key) or "")
            for key in ("title", "raw_text", "body_short", "source_url", "published_at")
        )
    )
    attachments = _attachments(document.get("attachments_json"))
    capability = get_source_capability(source.get("code"), category=source.get("category"))
    references = extract_references(
        body,
        source_url=document.get("source_url"),
        limit=24,
    )
    questions = generate_context_questions(
        source_code=source.get("code"),
        title=document.get("title") or "aggiornamento legale",
        body=body,
        pdf_text="",
        references=references,
        classification=source.get("category") or capability.publication_destination,
        source_url=document.get("source_url"),
        attachment_url=(attachments[0].get("url") if attachments else ""),
        limit=8,
    )
    exclusion = source_exclusion_reason(
        source,
        title=document.get("title"),
        body_text=body,
        url=document.get("source_url"),
        has_structured_reference=bool(references),
    )
    return {
        "external_id": document.get("external_id"),
        "title": _truncate(document.get("title"), 180),
        "source_url": document.get("source_url"),
        "published_at": document.get("published_at") or "",
        "attachment_count": len(attachments),
        "attachments": attachments[:MAX_ATTACHMENTS_PER_DOCUMENT],
        "reference_count": len(references),
        "reference_labels": reference_labels(references, limit=8),
        "question_count": len(questions),
        "questions": questions[:5],
        "destination": capability.to_dict().get("destination"),
        "destination_label": publication_destination_label(capability.publication_destination),
        "rag_destination": capability.rag_destination,
        "exclusion_reason": exclusion,
        "status": "letto",
    }


def _backfill_evidence_enrichment(
    repository: Any,
    *,
    missing: str,
    source_code: str,
    review_id: int,
    query: str,
    limit: int,
    max_seconds: int,
    include_closed: bool,
    include_open_data: bool,
) -> dict[str, Any]:
    started = time.monotonic()
    rows = _select_evidence_rows(
        repository,
        missing=missing,
        source_code=source_code,
        review_id=review_id,
        query=query,
        limit=limit,
        include_closed=include_closed,
        include_open_data=include_open_data,
    )
    checked = 0
    updated = 0
    stopped_for_time_limit = False
    items: list[dict[str, Any]] = []
    with repository._connect() as conn:
        for row in rows:
            if _time_exhausted(started, max_seconds):
                stopped_for_time_limit = True
                break
            checked += 1
            payload = dict(row)
            text = _clean(
                " ".join(
                    str(payload.get(key) or "")
                    for key in ("title", "query", "excerpt", "content_text", "source_url", "attachment_url")
                )
            )
            references = extract_references(
                text,
                source_url=payload.get("source_url"),
                attachment_url=payload.get("attachment_url"),
                limit=24,
            )
            questions = generate_context_questions(
                source_code=payload.get("source_code"),
                title=payload.get("title") or "evidenza fonte ufficiale",
                body=text,
                pdf_text=payload.get("content_text") if payload.get("attachment_url") else "",
                references=references,
                classification=payload.get("attachment_type") or payload.get("origin"),
                source_url=payload.get("source_url"),
                attachment_url=payload.get("attachment_url"),
                limit=8,
            )
            existing_terms = _terms_from_json(payload.get("matched_terms_json"))
            incoming_terms = (
                reference_labels(references, limit=16)
                if missing == "references"
                else [_clean(item.get("question")) for item in questions if _clean(item.get("question"))]
            )
            merged_terms = _unique_terms([*existing_terms, *incoming_terms])
            changed = merged_terms != existing_terms
            if changed:
                conn.execute(
                    """
                    UPDATE web_verification_evidence
                    SET matched_terms_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(merged_terms, ensure_ascii=False), int(payload["id"])),
                )
                updated += 1
            items.append(
                {
                    "evidence_id": int(payload["id"]),
                    "review_id": int(payload.get("review_id") or 0) or None,
                    "source_code": payload.get("source_code") or "",
                    "title": _truncate(payload.get("title"), 160),
                    "references": len(references),
                    "questions": len(questions),
                    "updated": changed,
                }
            )
        conn.commit()
    return {
        "ok": True,
        "checked": checked,
        "updated": updated,
        "selected": len(rows),
        "stopped_for_time_limit": stopped_for_time_limit,
        "duration_seconds": round(time.monotonic() - started, 2),
        "include_closed": bool(include_closed),
        "include_open_data": bool(include_open_data),
        "source_code": source_code,
        "review_id": review_id or None,
        "query": _clean(query),
        "items": items,
    }


def _select_evidence_rows(
    repository: Any,
    *,
    missing: str,
    source_code: str,
    review_id: int,
    query: str,
    limit: int,
    include_closed: bool,
    include_open_data: bool,
) -> list[dict[str, Any]]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if source_code:
        clauses.append("e.source_code = ?")
        params.append(source_code)
    if review_id:
        clauses.append("COALESCE(e.review_id, 0) = ?")
        params.append(review_id)
    lookup = _clean(query).casefold()
    if lookup:
        like_value = f"%{lookup}%"
        clauses.append(
            """
            (
                LOWER(COALESCE(e.title, '')) LIKE ?
                OR LOWER(COALESCE(e.query, '')) LIKE ?
                OR LOWER(COALESCE(e.source_url, '')) LIKE ?
                OR LOWER(COALESCE(e.attachment_url, '')) LIKE ?
                OR LOWER(COALESCE(e.excerpt, '')) LIKE ?
                OR LOWER(COALESCE(e.content_text, '')) LIKE ?
            )
            """
        )
        params.extend([like_value] * 6)
    if missing == "references":
        clauses.append(
            """
            (
                COALESCE(e.matched_terms_json, '') = ''
                OR COALESCE(e.matched_terms_json, '') = '[]'
                OR (
                    LOWER(COALESCE(e.matched_terms_json, '')) NOT LIKE '%art.%'
                    AND LOWER(COALESCE(e.matched_terms_json, '')) NOT LIKE '%r.g.%'
                    AND LOWER(COALESCE(e.matched_terms_json, '')) NOT LIKE '%d.lgs%'
                    AND LOWER(COALESCE(e.matched_terms_json, '')) NOT LIKE '%regolamento ue%'
                )
            )
            """
        )
    else:
        clauses.append(
            """
            (
                COALESCE(e.matched_terms_json, '') = ''
                OR COALESCE(e.matched_terms_json, '') = '[]'
                OR COALESCE(e.matched_terms_json, '') NOT LIKE '%?%'
            )
            """
        )
    if not include_closed:
        clauses.append("(q.status IS NULL OR q.status NOT IN ('closed', 'rejected'))")
    if not include_open_data:
        clauses.append("COALESCE(s.source_type, '') <> 'open_data'")
        clauses.append("COALESCE(s.parser_type, '') <> 'ckan_json'")
        clauses.append("e.source_code NOT LIKE 'openga_%'")
    params.append(max(1, int(limit or 1)))
    with repository._connect() as conn:
        rows = conn.execute(
            f"""
            SELECT e.*
            FROM web_verification_evidence e
            LEFT JOIN review_queue q ON q.id = e.review_id
            LEFT JOIN sources s ON s.code = e.source_code
            WHERE {' AND '.join(clauses)}
            ORDER BY e.updated_at DESC, e.id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [dict(row) for row in rows]


def _attachments(value: Any) -> list[dict[str, Any]]:
    rows = value
    if isinstance(value, str):
        try:
            rows = json.loads(value or "[]")
        except json.JSONDecodeError:
            rows = []
    if not isinstance(rows, list):
        return []
    return [dict(item) for item in rows if isinstance(item, dict)]


def _terms_from_json(value: Any) -> list[str]:
    try:
        payload = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        payload = []
    if isinstance(payload, list):
        return [_clean(item) for item in payload if _clean(item)]
    if isinstance(payload, dict):
        terms: list[str] = []
        for item in payload.values():
            if isinstance(item, list):
                terms.extend(_clean(value) for value in item if _clean(value))
            elif _clean(item):
                terms.append(_clean(item))
        return terms
    return []


def _unique_terms(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = _clean(value)
        key = term.casefold()
        if not term or key in seen:
            continue
        seen.add(key)
        output.append(term)
    return output


def _quality_summary(quality: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(quality, dict):
        return {}
    return {
        "status": quality.get("status") or "",
        "ready": bool(quality.get("ready")),
        "attachment_found": bool(quality.get("attachment_found")),
        "pdf_found": bool(quality.get("pdf_found")),
        "text_read": bool(quality.get("text_read")),
        "context_chars": int(quality.get("context_chars") or 0),
        "ocr_status": quality.get("ocr_status") or "",
        "references": len(quality.get("norm_references") or []),
        "questions": len(quality.get("question_matrix") or []),
        "warnings": list(quality.get("warnings") or [])[:5],
    }


def _required_limit(value: int, *, max_limit: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    if parsed <= 0:
        raise ValueError("Il limite documenti è obbligatorio e deve essere maggiore di zero.")
    return min(parsed, max(1, int(max_limit or 1)))


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_code(value: Any) -> str:
    return _clean(value).lower()


def _truncate(value: Any, limit: int = 220) -> str:
    text = _clean(value)
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _time_exhausted(started: float, max_seconds: int) -> bool:
    return bool(max_seconds and time.monotonic() - started >= max(1, int(max_seconds)))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@contextmanager
def _limited_source_environment(limit: int):
    updates = {
        "IUSENTRA_LEGAL_DETAIL_MAX_ITEMS": str(max(1, min(int(limit), MAX_CANARY_LIMIT))),
        "IUSENTRA_CASSAZIONE_LATEST_MAX_ITEMS": str(max(1, min(int(limit), MAX_CANARY_LIMIT))),
        "IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_LINKS": str(MAX_ATTACHMENTS_PER_DOCUMENT),
    }
    old = {key: os.environ.get(key) for key in updates}
    try:
        os.environ.update(updates)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
