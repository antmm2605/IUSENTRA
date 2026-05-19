from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import requests

from pct.legal_context_questions import generate_context_questions
from pct.legal_reference_extractor import extract_references, reference_labels
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS, RequestGet, build_legal_update_pipeline
from pct.legal_update_source_capabilities import (
    get_source_capability,
    publication_destination_label,
    source_exclusion_reason,
)
from pct.legal_update_web_verification import verify_legal_update_against_public_sources

CANARY_SCHEMA = "iusentra.legal_updates.canary.v1"
BACKFILL_SCHEMA = "iusentra.legal_updates.backfill_diagnostics.v1"
MISSING_KINDS = ("attachments", "ocr", "references", "questions")
MISSING_KIND_SET = set(MISSING_KINDS)
MAX_CANARY_LIMIT = 50
MAX_BACKFILL_LIMIT = 250
MAX_ATTACHMENTS_PER_DOCUMENT = 4
PUBLISH_MODES = {"off", "guarded", "auto"}


def run_legal_updates_canary(
    *,
    intelligence_db: str,
    giurisprudenza_db: str = "",
    source_code: str,
    limit: int,
    max_seconds: int = 60,
    no_publish: bool = True,
    publish_mode: str = "off",
    direct_only: bool = True,
    save_diagnostics: bool = False,
    request_get: RequestGet = requests.get,
) -> dict[str, Any]:
    """Esegue una prova controllata su una sola fonte, con limite obbligatorio."""

    code = _clean_code(source_code)
    safe_limit = _required_limit(limit, max_limit=MAX_CANARY_LIMIT)
    resolved_publish_mode = _resolve_publish_mode(publish_mode, no_publish=no_publish)
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
                existing_context = _existing_review_context(pipeline.repository, existing)
                item.update(existing_context)
                review_id = int(existing_context.get("review_id") or 0)
                if review_id and _should_refresh_unchanged_evidence(source, document, existing_context):
                    review = pipeline.repository.get_review_item(review_id) or {}
                    evidence = pipeline._record_ingestion_verification_evidence(review, source, direct_only=direct_only)
                    verification_attempts += int(evidence.get("attempted") or 0)
                    verification_saved += int(evidence.get("saved") or 0)
                    verification_attachments += int(evidence.get("attachments") or 0)
                    item["verification"] = evidence
                    item["quality"] = _quality_summary(
                        pipeline.repository.web_evidence_quality_for_review(review_id, review=review)
                    )
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

    if resolved_publish_mode == "guarded" and not stopped_for_time_limit:
        autopublished = _publish_guarded_canary_items(
            pipeline,
            source=source,
            items=items,
            limit=safe_limit,
            started=started,
            max_seconds=max_seconds,
            direct_only=direct_only,
        )
    elif resolved_publish_mode == "auto" and not stopped_for_time_limit:
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
        "no_publish": resolved_publish_mode == "off",
        "publish_mode": resolved_publish_mode,
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

    missing_kinds = _parse_missing_kinds(missing)
    safe_limit = _required_limit(limit, max_limit=MAX_BACKFILL_LIMIT)
    code = _clean_code(source_code)
    started = time.monotonic()
    pipeline = build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db,
    )
    pipeline.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))

    if len(missing_kinds) > 1:
        reports: list[dict[str, Any]] = []
        for missing_kind in missing_kinds:
            remaining_seconds = _remaining_seconds(started, max_seconds)
            if max_seconds and remaining_seconds <= 0:
                reports.append(
                    _with_backfill_summary(
                        {
                            "ok": False,
                            "schema": BACKFILL_SCHEMA,
                            "mode": "backfill_diagnostics",
                            "missing": missing_kind,
                            "no_publish": bool(no_publish),
                            "selected": 0,
                            "checked": 0,
                            "updated": 0,
                            "items": [],
                            "errors": ["Budget tempo esaurito prima di questa fase."],
                            "stopped_for_time_limit": True,
                            "autopublished": {"count": 0, "items": []},
                        },
                        missing_kind,
                    )
                )
                continue
            reports.append(
                _run_single_backfill_diagnostics(
                    pipeline,
                    missing_kind=missing_kind,
                    code=code,
                    review_id=int(review_id or 0),
                    query=query,
                    limit=safe_limit,
                    max_seconds=remaining_seconds,
                    include_closed=include_closed,
                    include_open_data=include_open_data,
                    no_publish=no_publish,
                )
            )
        result = {
            "schema": BACKFILL_SCHEMA,
            "mode": "backfill_diagnostics",
            "missing": ",".join(missing_kinds),
            "missing_kinds": missing_kinds,
            "no_publish": bool(no_publish),
            "ok": all(bool(report.get("ok")) for report in reports),
            "source_code": code,
            "review_id": int(review_id or 0) or None,
            "query": _clean(query),
            "limit": safe_limit,
            "max_seconds": max(0, int(max_seconds or 0)),
            "duration_seconds": round(time.monotonic() - started, 2),
            "reports": reports,
            "autopublished": {"count": sum(int((report.get("autopublished") or {}).get("count") or 0) for report in reports), "items": []},
        }
        return _with_combined_backfill_summary(result)

    return _run_single_backfill_diagnostics(
        pipeline,
        missing_kind=missing_kinds[0],
        code=code,
        review_id=int(review_id or 0),
        query=query,
        limit=safe_limit,
        max_seconds=max(0, int(max_seconds or 0)),
        include_closed=include_closed,
        include_open_data=include_open_data,
        no_publish=no_publish,
    )


def _run_single_backfill_diagnostics(
    pipeline: Any,
    *,
    missing_kind: str,
    code: str,
    review_id: int,
    query: str,
    limit: int,
    max_seconds: int,
    include_closed: bool,
    include_open_data: bool,
    no_publish: bool,
) -> dict[str, Any]:
    if missing_kind in {"attachments", "ocr"}:
        report = pipeline.backfill_web_verification_evidence(
            limit=limit,
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
            report["autopublished"] = pipeline.publish_auto_news(limit=min(limit, 20))
        else:
            report.setdefault("autopublished", {"count": 0, "items": []})
        return _with_backfill_summary(report, missing_kind)

    report = _backfill_evidence_enrichment(
        pipeline.repository,
        missing=missing_kind,
        source_code=code,
        review_id=int(review_id or 0),
        query=query,
        limit=limit,
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
    return _with_backfill_summary(report, missing_kind)


def _parse_missing_kinds(value: Any) -> list[str]:
    raw = _clean(value)
    if not raw:
        raise ValueError("Valore --missing non valido: usare attachments, ocr, references o questions.")
    if _clean_code(raw) == "all":
        return list(MISSING_KINDS)
    chunks = [chunk.strip() for part in raw.replace(";", ",").split(",") for chunk in [part] if chunk.strip()]
    kinds: list[str] = []
    invalid: list[str] = []
    for chunk in chunks:
        kind = _clean_code(chunk)
        if kind not in MISSING_KIND_SET:
            invalid.append(chunk)
            continue
        if kind not in kinds:
            kinds.append(kind)
    if invalid or not kinds:
        raise ValueError("Valore --missing non valido: usare attachments, ocr, references o questions.")
    return kinds


def _remaining_seconds(started: float, max_seconds: int) -> int:
    budget = max(0, int(max_seconds or 0))
    if budget <= 0:
        return 0
    elapsed = int(time.monotonic() - started)
    return max(0, budget - elapsed)


def _with_backfill_summary(report: dict[str, Any], missing_kind: str) -> dict[str, Any]:
    summary = _single_backfill_summary(report, missing_kind)
    report["summary"] = summary
    report["selected"] = summary["selected"]
    report["checked"] = summary["processed"]
    report["updated"] = summary["updated"]
    report["failed"] = summary["failed"]
    report["unchanged"] = summary["unchanged"]
    return _compact_backfill_report(report)


def _compact_backfill_report(report: dict[str, Any]) -> dict[str, Any]:
    """Mantiene il report JSON leggibile evitando snapshot con payload/PDF grezzi."""

    dashboard = report.pop("dashboard", None)
    if not isinstance(dashboard, dict):
        return report
    compact: dict[str, Any] = {}
    for key in ("headline", "quality"):
        value = dashboard.get(key)
        if isinstance(value, dict):
            compact[key] = value
    for key in ("sources", "review_queue", "news", "normative", "jurisprudence", "prassi", "audit"):
        value = dashboard.get(key)
        if isinstance(value, list):
            compact[f"{key}_count"] = len(value)
    if compact:
        report["dashboard_summary"] = compact
    return report


def _with_combined_backfill_summary(report: dict[str, Any]) -> dict[str, Any]:
    summaries = [
        dict(item.get("summary") or _single_backfill_summary(item, str(item.get("missing") or "")))
        for item in list(report.get("reports") or [])
        if isinstance(item, dict)
    ]
    failure_reasons: list[str] = []
    for summary in summaries:
        failure_reasons.extend(str(reason) for reason in summary.get("failure_reasons") or [] if str(reason).strip())
    report["summary"] = {
        "selected": sum(int(item.get("selected") or 0) for item in summaries),
        "processed": sum(int(item.get("processed") or 0) for item in summaries),
        "updated": sum(int(item.get("updated") or 0) for item in summaries),
        "unchanged": sum(int(item.get("unchanged") or 0) for item in summaries),
        "failed": sum(int(item.get("failed") or 0) for item in summaries),
        "failure_reasons": _unique_terms(failure_reasons)[:12],
        "pdf_completed": sum(int(item.get("pdf_completed") or 0) for item in summaries),
        "ocr_completed": sum(int(item.get("ocr_completed") or 0) for item in summaries),
        "attachments_completed": sum(int(item.get("attachments_completed") or 0) for item in summaries),
        "references_added": sum(int(item.get("references_added") or 0) for item in summaries),
        "questions_added": sum(int(item.get("questions_added") or 0) for item in summaries),
        "lex_updated": any(bool(item.get("lex_updated")) for item in summaries),
        "ricerca_legale_updated": any(bool(item.get("ricerca_legale_updated")) for item in summaries),
    }
    report["selected"] = report["summary"]["selected"]
    report["checked"] = report["summary"]["processed"]
    report["updated"] = report["summary"]["updated"]
    report["unchanged"] = report["summary"]["unchanged"]
    report["failed"] = report["summary"]["failed"]
    return report


def _single_backfill_summary(report: dict[str, Any], missing_kind: str) -> dict[str, Any]:
    items = [item for item in list(report.get("items") or []) if isinstance(item, dict)]
    processed = int(report.get("checked") or report.get("processed") or 0)
    selected = int(report.get("selected") or len(items))
    verification_updated = int(report.get("verification_evidence_saved") or 0)
    enrichment_updated = int(report.get("updated") or 0)
    updated = max(verification_updated, enrichment_updated)
    failed_items = [item for item in items if item.get("ok") is False or item.get("error")]
    skipped = int(report.get("skipped") or 0)
    failure_reasons = [
        _truncate(item.get("reason") or item.get("error") or "elemento non completato", 180)
        for item in failed_items
    ]
    failure_reasons.extend(_truncate(error, 180) for error in list(report.get("errors") or []) if _clean(error))
    if skipped:
        failure_reasons.append("record non azionabili o fonte non attendibile")
    failed = len(failed_items) + skipped + len(list(report.get("errors") or []))
    quality_summary = dict((report.get("quality") or {}).get("summary") or {})
    references_added = int(report.get("references_added") or 0)
    questions_added = int(report.get("questions_added") or 0)
    if missing_kind == "references" and not references_added:
        references_added = sum(int(item.get("terms_added") or 0) for item in items if item.get("updated"))
    if missing_kind == "questions" and not questions_added:
        questions_added = sum(int(item.get("terms_added") or 0) for item in items if item.get("updated"))
    pdf_completed = int(quality_summary.get("pdf_text_ready") or 0)
    ocr_completed = sum(
        1
        for item in list((report.get("quality") or {}).get("items") or [])
        if isinstance(item, dict)
        and item.get("pdf_found")
        and item.get("pdf_text_ready")
        and str(item.get("ocr_status") or "") in {"pulito", "leggibile_con_note"}
    )
    attachments_completed = int(report.get("verification_attachments_saved") or 0)
    unchanged = max(0, processed - updated - failed)
    lex_updated = bool(updated or references_added or questions_added or pdf_completed or attachments_completed)
    return {
        "selected": selected,
        "processed": processed,
        "updated": updated,
        "unchanged": unchanged,
        "failed": failed,
        "failure_reasons": _unique_terms(failure_reasons)[:12],
        "pdf_completed": pdf_completed,
        "ocr_completed": ocr_completed,
        "attachments_completed": attachments_completed,
        "references_added": references_added,
        "questions_added": questions_added,
        "lex_updated": lex_updated,
        "ricerca_legale_updated": lex_updated,
    }


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


def _resolve_publish_mode(value: Any, *, no_publish: bool) -> str:
    mode = _clean_code(value or "")
    if not mode or mode == "default":
        return "off" if no_publish else "auto"
    if mode not in PUBLISH_MODES:
        raise ValueError("Valore --publish-mode non valido: usare off, guarded o auto.")
    if mode == "off":
        return "off" if no_publish else "auto"
    return mode


def _publish_guarded_canary_items(
    pipeline: Any,
    *,
    source: dict[str, Any],
    items: list[dict[str, Any]],
    limit: int,
    started: float,
    max_seconds: int,
    direct_only: bool,
) -> dict[str, Any]:
    """Pubblica solo gli elementi letti dal canary che superano tutte le guardie."""

    published: list[int] = []
    published_items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    verification_attempts = 0
    verification_evidence_saved = 0
    verification_attachments_saved = 0
    stopped_for_time_limit = False
    for item in items:
        if len(published) >= max(1, int(limit or 1)):
            break
        if _time_exhausted(started, max_seconds):
            stopped_for_time_limit = True
            break
        review_id = int(item.get("review_id") or 0)
        if review_id <= 0:
            _guarded_skip(item, skipped, review_id, "review assente per il documento letto")
            continue
        review = pipeline.repository.get_review_item(review_id) or {}
        guard = _guarded_publication_precheck(pipeline, source, review, item)
        if not guard["ok"]:
            _mark_guarded_skip(pipeline, review_id, guard["reason"])
            _guarded_skip(item, skipped, review_id, guard["reason"])
            continue
        try:
            verification = verify_legal_update_against_public_sources(review, source, direct_only=direct_only)
        except Exception as exc:
            verification = {
                "ok": False,
                "reason": f"Verifica fonte non completata nel pilot guarded: {_truncate(exc, 180)}",
                "confirmation_count": 0,
                "official_confirmations": 0,
                "confirmations": [],
                "searched": {},
            }
        verification_attempts += 1
        evidence = pipeline._record_verification_evidence(
            review,
            source,
            verification,
            status="verified" if verification.get("ok") else "insufficient",
        )
        verification_evidence_saved += int(evidence.get("saved") or 0)
        verification_attachments_saved += int(evidence.get("attachments") or 0)
        if not verification.get("ok"):
            reason = _truncate(verification.get("reason") or "verifica fonte insufficiente", 220)
            _mark_guarded_skip(pipeline, review_id, reason)
            _guarded_skip(
                item,
                skipped,
                review_id,
                reason,
                confirmations=int(verification.get("confirmation_count") or 0),
                evidence_saved=int(evidence.get("saved") or 0),
                attachments_saved=int(evidence.get("attachments") or 0),
            )
            continue
        refreshed_review = pipeline.repository.get_review_item(review_id) or review
        quality = pipeline.repository.web_evidence_quality_for_review(review_id, review=refreshed_review)
        post_guard = _guarded_publication_quality_check(source, refreshed_review, item, quality)
        if not post_guard["ok"]:
            _mark_guarded_skip(pipeline, review_id, post_guard["reason"])
            _guarded_skip(item, skipped, review_id, post_guard["reason"])
            continue
        if str(refreshed_review.get("status") or "").lower() != "approved":
            pipeline.repository.set_review_status(
                review_id,
                "approved",
                reviewer="pilot-guarded",
                notes="Pilot guarded: guardie fonte, testo, allegati, duplicati e destinazione superate.",
            )
        try:
            result = pipeline.publish_review(review_id, reviewer="pilot-guarded", verification=verification)
        except Exception as exc:
            reason = f"errore pubblicazione guarded: {_truncate(exc, 180)}"
            _mark_guarded_skip(pipeline, review_id, reason)
            _guarded_skip(item, skipped, review_id, reason)
            continue
        published.append(review_id)
        published_items.append(
            {
                "id": review_id,
                "title": _truncate(refreshed_review.get("title"), 180),
                "source_code": source.get("code") or "",
                "destination": _published_destination(result),
                "quality": _quality_summary(quality),
            }
        )
        item["guarded_publish"] = {
            "published": True,
            "review_id": review_id,
            "destination": published_items[-1]["destination"],
        }
    if published:
        pipeline.repository.deduplicate_archive(performed_by="pilot-guarded")
    return {
        "count": len(published),
        "items": published,
        "published_items": published_items,
        "skipped": skipped,
        "mode": "guarded",
        "web_verification_attempts": verification_attempts,
        "verification_evidence_saved": verification_evidence_saved,
        "verification_attachments_saved": verification_attachments_saved,
        "stopped_for_time_limit": stopped_for_time_limit,
    }


def _guarded_publication_precheck(
    pipeline: Any,
    source: dict[str, Any],
    review: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    if not review:
        return {"ok": False, "reason": "review non trovata"}
    source_code = _clean_code(source.get("code"))
    capability = get_source_capability(source_code, category=source.get("category"))
    if not pipeline._is_trusted_update_source(source):
        return {"ok": False, "reason": "fonte non ufficiale o trust insufficiente"}
    if capability.publication_destination in {"rag_only", "out_of_scope"}:
        return {"ok": False, "reason": "destinazione non pubblicabile: solo RAG o fuori perimetro"}
    title = _clean(review.get("title"))
    body_text = _clean(review.get("body_text") or review.get("body_short") or review.get("summary_long"))
    quality = item.get("quality") if isinstance(item.get("quality"), dict) else {}
    has_evidence_text = bool(quality.get("text_read") and int(quality.get("context_chars") or 0) >= 400)
    if len(body_text) < 400 and not has_evidence_text:
        return {"ok": False, "reason": "testo pagina non abbastanza leggibile per la pubblicazione"}
    exclusion = source_exclusion_reason(
        source,
        title=title,
        body_text=body_text,
        url=review.get("source_url") or source.get("base_url"),
        has_structured_reference=pipeline._has_structured_reference(review),
    )
    if exclusion:
        return {"ok": False, "reason": exclusion}
    if pipeline._is_non_actionable_source_metadata(source, review, review):
        return {"ok": False, "reason": "filtro interesse studio legale non positivo"}
    proposed_action, resolved_review = pipeline._resolve_publish_action(review)
    canonical_destination = capability.to_dict().get("destination")
    if canonical_destination == "prassi" and proposed_action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE"}:
        downgraded = pipeline.repository.set_review_proposed_action(
            int(review["id"]),
            "NEWS_ONLY",
            target_entity_type="",
            target_entity_id=None,
            reviewer="pilot-guarded",
            notes=(
                "Pilot guarded: fonte di prassi con chiave normativa non coerente; "
                "pubblicazione limitata a notizia verificata."
            ),
        )
        if downgraded:
            proposed_action, resolved_review = pipeline._resolve_publish_action(downgraded)
    if proposed_action in {"DUPLICATE", "OUT_OF_SCOPE"}:
        return {"ok": False, "reason": f"azione non pubblicabile: {proposed_action.lower()}"}
    if proposed_action not in {"NEWS_ONLY", "NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}:
        return {"ok": False, "reason": "destinazione di pubblicazione non risolta"}
    duplicate = pipeline.repository.find_published_duplicate(
        source=source,
        normalized={
            "title": resolved_review.get("title"),
            "source_url": resolved_review.get("source_url"),
            "published_at": resolved_review.get("published_at"),
            "document_date": resolved_review.get("document_date"),
            "issuer": resolved_review.get("issuer"),
        },
        analysis={
            "classification_type": resolved_review.get("classification_type"),
            "issuer": resolved_review.get("analysis_issuer") or resolved_review.get("issuer"),
            "norm_type": resolved_review.get("norm_type"),
            "norm_number": resolved_review.get("norm_number"),
            "norm_year": resolved_review.get("norm_year"),
            "decision_number": resolved_review.get("decision_number"),
            "decision_year": resolved_review.get("decision_year"),
            "court_name": resolved_review.get("court_name"),
            "effective_date": resolved_review.get("effective_date"),
        },
    )
    if duplicate:
        return {"ok": False, "reason": "duplicato già pubblicato"}
    visible_fields = (
        ("title", "summary_short", "what_changes")
        if proposed_action == "NEWS_ONLY"
        else ("title", "summary_short", "summary_long", "what_changes")
    )
    visible_text = _clean(" ".join(_clean(resolved_review.get(field)) for field in visible_fields))
    if _looks_like_raw_technical_text(title) or _looks_like_raw_technical_text(visible_text):
        return {"ok": False, "reason": "testo tecnico grezzo non pubblicabile in UI"}
    if proposed_action != "NEWS_ONLY" and _looks_like_raw_technical_text(body_text):
        return {"ok": False, "reason": "testo tecnico grezzo non pubblicabile in UI"}
    if int(item.get("question_count") or 0) <= 0:
        return {"ok": False, "reason": "domande contestuali non salvate"}
    if int(item.get("reference_count") or 0) <= 0:
        return {"ok": False, "reason": "riferimenti normativi o identificativi non salvati"}
    return {"ok": True, "reason": ""}


def _guarded_publication_quality_check(
    source: dict[str, Any],
    review: dict[str, Any],
    item: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    capability = get_source_capability(source.get("code"), category=source.get("category"))
    if not quality.get("ready"):
        return {"ok": False, "reason": "diagnosi fonte/PDF/OCR non pronta"}
    if not quality.get("text_read"):
        return {"ok": False, "reason": "testo leggibile non disponibile"}
    if capability.pdf_required and not quality.get("pdf_found"):
        return {"ok": False, "reason": "PDF ufficiale richiesto ma non disponibile"}
    if quality.get("pdf_found") and not quality.get("pdf_text_ready"):
        return {"ok": False, "reason": "PDF presente ma testo/OCR non disponibile"}
    if quality.get("attachment_found") and not quality.get("hash_ready"):
        return {"ok": False, "reason": "hash allegato non salvato"}
    if not quality.get("pdf_clickable"):
        return {"ok": False, "reason": "allegato PDF non cliccabile"}
    if not list(quality.get("question_matrix") or []):
        return {"ok": False, "reason": "domande contestuali mancanti nella qualità fonte"}
    if int(item.get("reference_count") or 0) > 0 and not (
        list(quality.get("norm_references") or []) or list(quality.get("rg_references") or [])
    ):
        return {"ok": False, "reason": "riferimenti non ritrovati nella diagnosi fonte"}
    return {"ok": True, "reason": ""}


def _looks_like_raw_technical_text(value: Any) -> bool:
    text = _clean(value).lower()
    if not text:
        return False
    technical_markers = (
        "```",
        "{",
        "}",
        "<script",
        "<html",
        "payload",
        "json_api",
        "backend",
        "frontend",
        "provider",
        "webhook",
        "runtime",
    )
    if any(marker in text for marker in technical_markers):
        braces = text.count("{") + text.count("}")
        return braces >= 2 or any(marker not in {"{", "}"} for marker in technical_markers if marker in text)
    padded = f" {text} "
    if " undefined " in padded or " null " in padded:
        return True
    return False


def _mark_guarded_skip(pipeline: Any, review_id: int, reason: str) -> None:
    try:
        pipeline.repository.set_review_status(
            int(review_id),
            "pending",
            reviewer="pilot-guarded",
            notes=f"Pilot guarded non pubblicato: {_truncate(reason, 220)}",
            priority=10,
        )
    except Exception:
        return


def _guarded_skip(
    item: dict[str, Any],
    skipped: list[dict[str, Any]],
    review_id: int,
    reason: str,
    **extra: Any,
) -> None:
    payload = {
        "id": int(review_id or 0) or None,
        "title": _truncate(item.get("title"), 180),
        "reason": _truncate(reason, 220),
    }
    payload.update(extra)
    skipped.append(payload)
    item["guarded_publish"] = {"published": False, "reason": payload["reason"], "review_id": payload["id"]}


def _published_destination(result: dict[str, Any]) -> str:
    for key in ("jurisprudence", "prassi", "normative", "news"):
        if key in result:
            return key
    return "pubblicato"


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
    failed = 0
    references_added = 0
    questions_added = 0
    failure_reasons: list[str] = []
    stopped_for_time_limit = False
    items: list[dict[str, Any]] = []
    with repository._connect() as conn:
        for row in rows:
            if _time_exhausted(started, max_seconds):
                stopped_for_time_limit = True
                break
            checked += 1
            payload = dict(row)
            try:
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
                existing_keys = {_clean(term).casefold() for term in existing_terms if _clean(term)}
                added_terms = [
                    _clean(term)
                    for term in incoming_terms
                    if _clean(term) and _clean(term).casefold() not in existing_keys
                ]
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
                    if missing == "references":
                        references_added += len(added_terms)
                    else:
                        questions_added += len(added_terms)
                items.append(
                    {
                        "evidence_id": int(payload["id"]),
                        "review_id": int(payload.get("review_id") or 0) or None,
                        "source_code": payload.get("source_code") or "",
                        "title": _truncate(payload.get("title"), 160),
                        "references": len(references),
                        "questions": len(questions),
                        "terms_added": len(added_terms) if changed else 0,
                        "updated": changed,
                        "ok": True,
                    }
                )
            except Exception as exc:
                failed += 1
                reason = f"Evidenza non completata: {_truncate(exc)}"
                failure_reasons.append(reason)
                items.append(
                    {
                        "evidence_id": int(payload.get("id") or 0),
                        "review_id": int(payload.get("review_id") or 0) or None,
                        "source_code": payload.get("source_code") or "",
                        "title": _truncate(payload.get("title"), 160),
                        "updated": False,
                        "ok": False,
                        "error": reason,
                    }
                )
        conn.commit()
    return {
        "ok": True,
        "checked": checked,
        "updated": updated,
        "failed": failed,
        "references_added": references_added,
        "questions_added": questions_added,
        "failure_reasons": _unique_terms(failure_reasons)[:12],
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


def _existing_review_context(repository: Any, raw_document: dict[str, Any]) -> dict[str, Any]:
    raw_id = int((raw_document or {}).get("id") or 0)
    if raw_id <= 0:
        return {}
    normalized = repository.get_normalized_by_raw(raw_id) or {}
    normalized_id = int(normalized.get("id") or 0)
    if normalized_id <= 0:
        return {}
    review_id = 0
    with repository._connect() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM review_queue
            WHERE normalized_document_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (normalized_id,),
        ).fetchone()
        review_id = int(row["id"] or 0) if row else 0
    payload: dict[str, Any] = {"normalized_document_id": normalized_id}
    if review_id:
        review = repository.get_review_item(review_id) or {}
        payload["review_id"] = review_id
        payload["quality"] = _quality_summary(repository.web_evidence_quality_for_review(review_id, review=review))
    return payload


def _should_refresh_unchanged_evidence(
    source: dict[str, Any],
    document: dict[str, Any],
    existing_context: dict[str, Any],
) -> bool:
    capability = get_source_capability(source.get("code"), category=source.get("category"))
    if capability.publication_destination in {"rag_only", "out_of_scope"}:
        return False
    quality = existing_context.get("quality") if isinstance(existing_context, dict) else {}
    if isinstance(quality, dict) and quality.get("pdf_found") and quality.get("text_read"):
        return False
    attachments = _attachments(document.get("attachments_json"))
    return any(_looks_like_pdf_attachment(item) for item in attachments)


def _looks_like_pdf_attachment(item: dict[str, Any]) -> bool:
    url = _clean(item.get("url") or item.get("attachment_url")).lower()
    attachment_type = _clean(item.get("attachment_type")).lower()
    return bool(
        url.startswith(("http://", "https://"))
        and (
            attachment_type == "pdf"
            or ".pdf" in url
            or "downloadpdf" in url
            or "format=pdf" in url
            or "estensione=pdf" in url
        )
    )


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
    repaired = _repair_mojibake(str(value or ""))
    return " ".join(repaired.split()).strip()


def _clean_code(value: Any) -> str:
    return _clean(value).lower()


def _truncate(value: Any, limit: int = 220) -> str:
    text = _clean(value)
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _repair_mojibake(text: str) -> str:
    if not text:
        return ""
    if not any(
        marker in text
        for marker in (
            "\u00c3",
            "\u00c2",
            "\u00e2\u20ac",
            "\u00e2\u20ac\u2122",
            "\u00e2\u20ac\u0153",
            "\u00ef\u00bf\u00bd",
            "\ufffd",
        )
    ):
        return text
    candidates = [text]
    for encoding in ("latin-1", "windows-1252"):
        try:
            candidates.append(text.encode(encoding, errors="strict").decode("utf-8", errors="replace"))
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            continue
    return min(candidates, key=_decode_penalty)


def _decode_penalty(text: str) -> tuple[int, int]:
    lowered = text.lower()
    mojibake = sum(
        lowered.count(marker)
        for marker in (
            "\u00e3",
            "\u00e2",
            "\u00c3",
            "\u00c2",
            "\u00e2\u20ac",
            "\u00e2\u20ac\u2122",
            "\u00ef\u00bf\u00bd",
            "\ufffd",
        )
    )
    return (mojibake, text.count("\ufffd"))


def _time_exhausted(started: float, max_seconds: int) -> bool:
    return bool(max_seconds and time.monotonic() - started >= max(1, int(max_seconds)))


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
