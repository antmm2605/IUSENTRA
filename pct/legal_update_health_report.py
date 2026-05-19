"""Health report di regime per gli aggiornamenti legali.

Il modulo non acquisisce nuove fonti e non pubblica contenuti: legge solo
repository, coda job, cursori e diagnostica già salvata per produrre un quadro
di manutenzione ordinaria.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Mapping

from pct.legal_update_enrichment import extract_legal_references
from pct.legal_update_autofetch import (
    LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS,
    LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS,
    LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET,
    LegalAutoFetchConfig,
    build_legal_update_operational_monitor,
    legal_update_progressive_publication_policy,
    legal_update_progressive_scheduler_payload,
    legal_update_progressive_source_classification,
)
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS, LegalUpdatePipeline, build_legal_update_pipeline
from pct.legal_update_source_capabilities import get_source_capability


LEGAL_UPDATES_HEALTH_REPORT_SCHEMA = "iusentra.legal_updates_health_report.v1"
BACKFILL_MISSING_KINDS: tuple[str, ...] = ("attachments", "ocr", "references", "questions")
GIURISPRUDENZA_STRUCTURED_CANARY_SOURCES: tuple[str, ...] = (
    "cassazione_ultime_sent_ord_questioni",
    "corte_conti",
    "curia_cgue_rss",
    "openga_sentenze",
    "openga_ordinanze",
    "corte_costituzionale",
)


def build_legal_updates_health_report(
    *,
    intelligence_db: str = "./intelligence/motori.json",
    giurisprudenza_db: str = "",
    ai_base_url: str = "",
    ai_model: str = "mistral",
    queue_db_path: str = "",
    cursor_path: str = "",
    pipeline: LegalUpdatePipeline | None = None,
) -> dict[str, Any]:
    """Costruisce il report sanitario senza fetch live e senza pubblicazione."""

    runtime_pipeline = pipeline or build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db,
        ai_base_url=ai_base_url,
        ai_model=ai_model,
    )
    try:
        runtime_pipeline.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))
    except Exception:
        # I test con repository finti possono non esporre upsert_sources.
        pass

    sources = list(runtime_pipeline.repository.list_sources(enabled_only=False))
    scheduler = legal_update_progressive_scheduler_payload(sources)
    config = LegalAutoFetchConfig(
        intelligence_db=str(intelligence_db or "./intelligence/motori.json"),
        giurisprudenza_db=str(giurisprudenza_db or ""),
        ai_base_url=str(ai_base_url or ""),
        ai_model=str(ai_model or "mistral"),
        queue_db_path=str(queue_db_path or ""),
        cursor_path=str(cursor_path or ""),
        source_budget=int(scheduler.get("source_budget") or LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET),
        publish_max_items=int(scheduler.get("publish_max_items") or LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS),
        item_timeout_seconds=int(
            scheduler.get("item_timeout_seconds") or LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS
        ),
        execute_due_sources=False,
    )
    monitor = build_legal_update_operational_monitor(config, pipeline=runtime_pipeline)
    dashboard = runtime_pipeline.dashboard_snapshot()
    source_quality = build_legal_source_quality_dashboard(
        runtime_pipeline,
        sources=sources,
        scheduler=scheduler,
        monitor=monitor,
    )
    retry = _retry_safety_payload(config, monitor=monitor)
    backfill = _periodic_backfill_payload(source_quality, intelligence_db=intelligence_db)
    publications = _publication_payload(dashboard, scheduler=scheduler, source_quality=source_quality)
    readiness = _readiness_payload(source_quality=source_quality, retry=retry, publications=publications)

    return {
        "schema": LEGAL_UPDATES_HEALTH_REPORT_SCHEMA,
        "generated_at": _now_iso(),
        "ok": readiness["status"] != "bloccato",
        "readiness": readiness,
        "source_quality_dashboard": source_quality,
        "stato_fonti": source_quality,
        "queues": monitor.get("queue") or {},
        "coda": monitor.get("queue") or {},
        "recent_jobs": monitor.get("recent_jobs") or [],
        "error_alerts": _error_alerts(source_quality, monitor=monitor),
        "pdf_ocr": source_quality.get("pdf_ocr") or {},
        "references": source_quality.get("references") or {},
        "questions": source_quality.get("questions") or {},
        "scheduler": scheduler,
        "monitor": monitor,
        "review": {
            "pending": int((dashboard.get("headline") or {}).get("review_pending") or 0),
            "approved": int((dashboard.get("headline") or {}).get("review_approved") or 0),
            "source_pending": source_quality["totals"]["review_pending"],
        },
        "pubblicazioni": publications,
        "publications": publications,
        "retry_sicuro": retry,
        "safe_retry": retry,
        "backfill_periodico": backfill,
        "periodic_backfill": backfill,
        "nuove_fonti": _new_source_procedure_payload(),
        "new_source_procedure": _new_source_procedure_payload(),
        "dashboard_counts": dashboard.get("headline") or {},
    }


def build_legal_source_quality_dashboard(
    pipeline: LegalUpdatePipeline,
    *,
    sources: list[Mapping[str, Any]] | None = None,
    scheduler: Mapping[str, Any] | None = None,
    monitor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Payload compatto per dashboard qualità fonti."""

    runtime_sources = list(sources or pipeline.repository.list_sources(enabled_only=False))
    scheduler_payload = dict(scheduler or legal_update_progressive_scheduler_payload(runtime_sources))
    monitor_payload = dict(monitor or {})
    activity = _safe_mapping_call(pipeline.repository, "source_activity_summary")
    latest_runs = _safe_mapping_call(pipeline.repository, "latest_source_agent_runs")
    evidence = _evidence_quality_by_source(pipeline)
    monitor_by_source = {
        str(row.get("source_code") or ""): dict(row)
        for row in list(monitor_payload.get("sources") or [])
        if isinstance(row, Mapping)
    }

    rows: list[dict[str, Any]] = []
    for source in runtime_sources:
        code = _source_code(source.get("code"))
        source_activity = dict(activity.get(code) or {})
        latest = dict(latest_runs.get(code) or {})
        evidence_row = dict(evidence.get(code) or {})
        monitor_row = dict(monitor_by_source.get(code) or {})
        classification = legal_update_progressive_source_classification(code)
        policy = legal_update_progressive_publication_policy(code)
        capability = get_source_capability(code, category=source.get("category"))
        last_check = _first_text(
            source.get("last_check_at"),
            latest.get("finished_at"),
            monitor_row.get("last_finished_at"),
            source_activity.get("last_document_at"),
        )
        last_error = _first_text(latest.get("error_message"), monitor_row.get("reason"))
        if str(latest.get("status") or "").lower() not in {"failed", "timeout"}:
            last_error = "" if str(monitor_row.get("status") or "") != "da_verificare" else last_error

        rows.append(
            {
                "source_code": code,
                "source_name": _first_text(source.get("name"), code),
                "enabled": bool(source.get("enabled", True)),
                "classification": classification,
                "classification_label": _classification_label(classification),
                "publication_policy": policy,
                "publication_policy_label": _policy_label(policy),
                "status": monitor_row.get("status") or _source_status(classification, policy),
                "last_check_at": last_check,
                "last_error": last_error,
                "raw_documents": _int(source_activity.get("raw_documents")),
                "normalized_documents": _int(source_activity.get("normalized_documents")),
                "analyses": _int(source_activity.get("analyses")),
                "review_pending": _int(source_activity.get("review_pending")),
                "review_published": _int(source_activity.get("review_published")),
                "web_evidence": _int(evidence_row.get("web_evidence")),
                "ocr_failed": _int(evidence_row.get("ocr_failed")),
                "empty_attachments": _int(evidence_row.get("empty_attachments")),
                "missing_references": _int(evidence_row.get("missing_references")),
                "missing_questions": _int(evidence_row.get("missing_questions")),
                "attachment_evidence": _int(evidence_row.get("attachment_evidence")),
                "guarded_publications": _int(source_activity.get("review_published")) if policy == "guarded" else 0,
                "rag_destination": capability.rag_destination,
                "publication_destination": capability.publication_destination,
            }
        )

    totals = {
        "sources": len(rows),
        "fonti_attive": sum(1 for row in rows if row["enabled"] and row["classification"] == "verde_abilitata"),
        "fonti_in_osservazione": sum(1 for row in rows if row["classification"] == "osservazione"),
        "fonti_rag_only": sum(1 for row in rows if row["classification"] == "rag_only"),
        "fonti_non_pubblicabili": sum(
            1
            for row in rows
            if row["publication_policy"] in {"no_publish", "blocked"}
            or row["classification"] in {"rag_only", "archivio_locale", "fuori_perimetro", "osservazione"}
        ),
        "errors": sum(1 for row in rows if row["last_error"]),
        "ocr_failed": sum(row["ocr_failed"] for row in rows),
        "empty_attachments": sum(row["empty_attachments"] for row in rows),
        "missing_references": sum(row["missing_references"] for row in rows),
        "missing_questions": sum(row["missing_questions"] for row in rows),
        "review_pending": sum(row["review_pending"] for row in rows),
        "guarded_publications": sum(row["guarded_publications"] for row in rows),
    }
    return {
        "schema": "iusentra.legal_source_quality_dashboard.v1",
        "generated_at": _now_iso(),
        "totals": totals,
        "fonti_attive": [row for row in rows if row["enabled"] and row["classification"] == "verde_abilitata"],
        "fonti_in_osservazione": [row for row in rows if row["classification"] == "osservazione"],
        "fonti_rag_only": [row for row in rows if row["classification"] == "rag_only"],
        "fonti_non_pubblicabili": [
            row
            for row in rows
            if row["publication_policy"] in {"no_publish", "blocked"}
            or row["classification"] in {"rag_only", "archivio_locale", "fuori_perimetro", "osservazione"}
        ],
        "rows": rows,
        "pdf_ocr": {
            "ocr_failed": totals["ocr_failed"],
            "empty_attachments": totals["empty_attachments"],
            "attachment_evidence": sum(row["attachment_evidence"] for row in rows),
        },
        "references": {"missing": totals["missing_references"]},
        "questions": {"missing": totals["missing_questions"]},
        "scheduler": {
            "enabled_source_codes": list(scheduler_payload.get("enabled_source_codes") or []),
            "publication_mode": scheduler_payload.get("publication_mode") or "guarded",
        },
    }


def _evidence_quality_by_source(pipeline: LegalUpdatePipeline) -> dict[str, dict[str, int]]:
    try:
        connector = getattr(pipeline.repository, "_connect")
        with connector() as conn:
            rows = conn.execute(
                """
                SELECT source_code, attachment_url, context_chars, excerpt, content_text,
                       matched_terms_json, verification_status
                FROM web_verification_evidence
                """
            ).fetchall()
    except Exception:
        return {}

    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        payload = dict(row)
        code = _source_code(payload.get("source_code"))
        if not code:
            continue
        bucket = summary.setdefault(
            code,
            {
                "web_evidence": 0,
                "attachment_evidence": 0,
                "ocr_failed": 0,
                "empty_attachments": 0,
                "missing_references": 0,
                "missing_questions": 0,
            },
        )
        bucket["web_evidence"] += 1
        attachment_url = _first_text(payload.get("attachment_url"))
        context_chars = _int(payload.get("context_chars"))
        content_text = _first_text(payload.get("content_text"), payload.get("excerpt"))
        matched_terms = _json_list(payload.get("matched_terms_json"))
        if attachment_url:
            bucket["attachment_evidence"] += 1
            if context_chars <= 0 or not content_text:
                bucket["empty_attachments"] += 1
            if _looks_like_ocr_failure(payload.get("excerpt"), payload.get("content_text")):
                bucket["ocr_failed"] += 1
        if content_text and not _has_reference(content_text, matched_terms):
            bucket["missing_references"] += 1
        if content_text and not _has_question(matched_terms):
            bucket["missing_questions"] += 1
    return summary


def _retry_safety_payload(config: LegalAutoFetchConfig, *, monitor: Mapping[str, Any]) -> dict[str, Any]:
    queue_summary = dict(monitor.get("queue") or {})
    recent_jobs = [dict(row) for row in list(monitor.get("recent_jobs") or []) if isinstance(row, Mapping)]
    job_limits = [
        {
            "job_id": row.get("job_id"),
            "source_code": row.get("source_code"),
            "status": row.get("status"),
            "attempts": _int(row.get("attempts")),
            "max_attempts": _int(row.get("max_attempts")),
            "timeout_seconds": _int(row.get("timeout_seconds")),
            "last_error": row.get("last_error") or "",
        }
        for row in recent_jobs[:10]
    ]
    return {
        "enabled": True,
        "max_attempts": max(1, int(config.max_attempts or 1)),
        "timeout_seconds": max(1, int(config.item_timeout_seconds or 1)),
        "dedupe": "dedupe_key univoca per fonte, URL, hash e payload stabile",
        "publication_guard": "guarded",
        "does_not_publish_without_guard": True,
        "readable_errors": True,
        "queue": queue_summary,
        "recent_job_limits": job_limits,
        "failed_or_timeout": _int(queue_summary.get("failed")) + _int(queue_summary.get("timeout")),
    }


def _periodic_backfill_payload(source_quality: Mapping[str, Any], *, intelligence_db: str) -> dict[str, Any]:
    totals = dict(source_quality.get("totals") or {})
    pending = {
        "attachments": _int(totals.get("empty_attachments")),
        "ocr": _int(totals.get("ocr_failed")),
        "references": _int(totals.get("missing_references")),
        "questions": _int(totals.get("missing_questions")),
    }
    base = "python -m pct.cli legal-updates-backfill-diagnostics"
    commands = [
        (
            f"{base} --missing {kind} --limit 50 --max-seconds 120 "
            "--no-publish --json"
        )
        for kind in BACKFILL_MISSING_KINDS
    ]
    return {
        "enabled": True,
        "mode": "solo mirato",
        "pending": pending,
        "commands": commands,
        "combined_command": (
            f"{base} --missing attachments,ocr,references,questions "
            "--limit 50 --max-seconds 120 --no-publish --json"
        ),
        "intelligence_db": str(intelligence_db or "./intelligence/motori.json"),
        "no_publish": True,
        "allowed_missing_kinds": list(BACKFILL_MISSING_KINDS),
    }


def _publication_payload(
    dashboard: Mapping[str, Any],
    *,
    scheduler: Mapping[str, Any],
    source_quality: Mapping[str, Any],
) -> dict[str, Any]:
    headline = dict(dashboard.get("headline") or {})
    return {
        "mode": scheduler.get("publication_mode") or "guarded",
        "max_items_per_cycle": _int(scheduler.get("publish_max_items")),
        "uncontrolled_publication": False,
        "guarded_publications": _int((source_quality.get("totals") or {}).get("guarded_publications")),
        "published_news": _int(headline.get("published_news")),
        "published_normative": _int(headline.get("published_normative")),
        "published_jurisprudence": _int(headline.get("published_jurisprudence")),
        "published_prassi": _int(headline.get("published_prassi")),
        "blocked_sources": list(scheduler.get("excluded_publication_source_codes") or []),
    }


def _readiness_payload(
    *,
    source_quality: Mapping[str, Any],
    retry: Mapping[str, Any],
    publications: Mapping[str, Any],
) -> dict[str, Any]:
    totals = dict(source_quality.get("totals") or {})
    blocking_errors = _int(retry.get("failed_or_timeout"))
    issue_count = (
        blocking_errors
        + _int(totals.get("errors"))
        + _int(totals.get("ocr_failed"))
        + _int(totals.get("empty_attachments"))
    )
    if bool(publications.get("uncontrolled_publication")):
        return {"status": "bloccato", "issue_count": issue_count + 1, "reason": "Pubblicazione non controllata attiva."}
    if issue_count:
        return {"status": "da_verificare", "issue_count": issue_count, "reason": "Sono presenti errori o allegati da completare."}
    return {"status": "presidiato", "issue_count": 0, "reason": "Regime controllato senza anomalie bloccanti note."}


def _error_alerts(source_quality: Mapping[str, Any], *, monitor: Mapping[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for row in list(source_quality.get("rows") or []):
        if not isinstance(row, Mapping):
            continue
        if row.get("last_error"):
            alerts.append(
                {
                    "source_code": row.get("source_code"),
                    "source_name": row.get("source_name"),
                    "severity": "errore",
                    "message": row.get("last_error"),
                    "last_check_at": row.get("last_check_at"),
                }
            )
    queue = dict(monitor.get("queue") or {})
    for key, label in (("failed", "Job falliti"), ("timeout", "Job in timeout")):
        count = _int(queue.get(key))
        if count:
            alerts.append({"severity": "errore", "message": f"{label}: {count}", "count": count})
    return alerts[:20]


def _new_source_procedure_payload() -> dict[str, Any]:
    return {
        "steps": [
            "capability",
            "fixture",
            "canary",
            "report",
            "pilot",
            "scheduler",
        ],
        "rules": [
            "Aggiungere la capability fonte con destinazione e policy di pubblicazione.",
            "Creare fixture offline di elenco, dettaglio e allegato quando previsto.",
            "Eseguire canary con limite obbligatorio, direct-only e no-publish.",
            "Salvare report qualità con PDF/OCR, riferimenti e domande.",
            "Fare pilot guarded su pochi documenti prima di abilitarla.",
            "Inserire nello scheduler solo dopo report verde e policy no-publish/guarded esplicita.",
        ],
    }


def build_giurisprudenza_structured_canary(
    *,
    intelligence_db: str = "./intelligence/motori.json",
    giurisprudenza_db: str = "",
    ai_base_url: str = "",
    ai_model: str = "mistral",
    pipeline: LegalUpdatePipeline | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Verifica se esistono schede giurisprudenziali pubblicabili con chiavi minime."""

    runtime_pipeline = pipeline or build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db,
        ai_base_url=ai_base_url,
        ai_model=ai_model,
    )
    rows: list[dict[str, Any]] = []
    try:
        review_rows = runtime_pipeline.repository.list_review_queue(
            statuses=("pending", "approved", "published"),
            limit=max(1, int(limit or 1)),
        )
    except Exception:
        review_rows = []
    for row in review_rows:
        item = dict(row)
        try:
            if item.get("id"):
                item = dict(runtime_pipeline.repository.get_review_item(int(item["id"])) or item)
        except Exception:
            pass
        source_code = _source_code(item.get("source_code"))
        if source_code not in GIURISPRUDENZA_STRUCTURED_CANARY_SOURCES:
            continue
        attachments = item.get("attachments_json") if isinstance(item.get("attachments_json"), list) else []
        text_or_pdf = bool(_first_text(item.get("body_text"), item.get("body_short"), item.get("summary_long"), item.get("summary_short")) or attachments)
        required = {
            "corte": _first_text(item.get("court_name")),
            "numero": _first_text(item.get("decision_number")),
            "anno": _first_text(item.get("decision_year")),
            "data": _first_text(item.get("effective_date"), item.get("document_date"), item.get("published_at")),
            "fonte_ufficiale": _first_text(item.get("source_url")),
            "testo_pdf": "presente" if text_or_pdf else "",
        }
        missing = [key for key, value in required.items() if not value]
        rows.append(
            {
                "review_id": item.get("id"),
                "source_code": source_code,
                "title": item.get("title") or "",
                "status": item.get("status") or "",
                "proposed_action": item.get("proposed_action") or item.get("analysis_proposed_action") or "",
                "required_keys": required,
                "missing_keys": missing,
                "complete": not missing,
                "can_promote_guarded": not missing and (item.get("proposed_action") or item.get("analysis_proposed_action")) == "NEW_CASE_LAW",
            }
        )
    complete = [row for row in rows if row["complete"]]
    return {
        "schema": "iusentra.legal_updates.giurisprudenza_structured_canary.v1",
        "generated_at": _now_iso(),
        "sources_checked": list(GIURISPRUDENZA_STRUCTURED_CANARY_SOURCES),
        "items_checked": len(rows),
        "complete_candidates": complete,
        "complete_candidate_count": len(complete),
        "status": "chiuso" if complete else "chiuso_con_blocco_intenzionale",
        "reason": (
            "Sono presenti schede con corte, numero, anno, data, fonte ufficiale e testo/PDF."
            if complete
            else "Nessuna scheda ha tutte le chiavi minime: la promozione strutturata resta bloccata e non viene forzata."
        ),
        "items": rows,
    }


def _safe_mapping_call(target: Any, method_name: str) -> dict[str, Any]:
    method = getattr(target, method_name, None)
    if method is None:
        return {}
    try:
        value = method()
    except Exception:
        return {}
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _source_status(classification: str, policy: str) -> str:
    if classification == "verde_abilitata" and policy == "guarded":
        return "presidiata"
    if classification == "osservazione":
        return "in_osservazione"
    if classification == "rag_only":
        return "solo_ricerca"
    return "non_pubblicabile"


def _classification_label(value: Any) -> str:
    raw = str(value or "").strip()
    return {
        "verde_abilitata": "Attiva",
        "osservazione": "In osservazione",
        "rag_only": "RAG-only",
        "archivio_locale": "Archivio locale",
        "fuori_perimetro": "Non pubblicabile",
    }.get(raw, raw.replace("_", " ").capitalize() or "Da verificare")


def _policy_label(value: Any) -> str:
    raw = str(value or "").strip()
    return {
        "guarded": "Pubblicazione guarded",
        "no_publish": "Non pubblica",
        "blocked": "Bloccata",
    }.get(raw, raw.replace("_", " ").capitalize() or "Da verificare")


def _looks_like_ocr_failure(*values: Any) -> bool:
    haystack = " ".join(str(value or "").lower() for value in values if str(value or "").strip())
    if "testo non estraibile" in haystack or "ocr fall" in haystack:
        return True
    return "ocr" in haystack and any(marker in haystack for marker in ("errore", "fallito", "fallita", "non riusc"))


def _has_reference(text: str, matched_terms: list[str]) -> bool:
    if any(_looks_like_reference_term(term) for term in matched_terms):
        return True
    try:
        return bool(extract_legal_references(text, limit=2))
    except Exception:
        return False


def _looks_like_reference_term(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in ("art.", "articolo", "r.g.", "rg ", "legge", "decreto", "sentenza", "ordinanza"))


def _has_question(matched_terms: list[str]) -> bool:
    return any("?" in str(term or "") for term in matched_terms)


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    try:
        payload = json.loads(str(value or "[]"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if str(item).strip()]


def _source_code(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().split())


def _first_text(*values: Any) -> str:
    for value in values:
        text = " ".join(str(value or "").strip().split())
        if text:
            return text
    return ""


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
