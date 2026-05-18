"""Auto-fetch governato per fonti legali pubbliche.

Il modulo coordina fonti, cursori e coda job senza fare scraping diretto:
la pipeline esistente resta proprietaria del fetch, mentre questo layer decide
quali fonti sono dovute, le accoda con deduplica e produce un monitor operativo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pct.legal_update_batch_runner import (
    LegalUpdateJobConfig,
    run_legal_update_batch_with_timeouts,
)
from pct.legal_update_job_queue import (
    LEGAL_UPDATE_JOB_QUEUE_SCHEMA,
    LegalUpdateJobQueue,
)
from pct.legal_update_pipeline import LegalUpdatePipeline, build_legal_update_pipeline


LEGAL_UPDATE_AUTOFETCH_SCHEMA = "iusentra.legal_update_autofetch.v1"

LEGAL_SOURCE_QUALITY_QUESTIONS: tuple[str, ...] = (
    "La fonte risulta censita nel database?",
    "La pagina ufficiale o pubblica e' raggiungibile?",
    "Sono presenti allegati, PDF o documenti collegati?",
    "Gli allegati sono stati scaricati e hashati?",
    "Il testo e' stato estratto oppure passato da OCR?",
    "Il testo OCR e' pulito o marcato come sporco?",
    "Sono state estratte norme, R.G., date e riferimenti utili?",
    "Ci sono discrepanze tra scheda, PDF, R.G., date o titolo?",
    "Il documento e' pronto per Memory Tree e RAG?",
    "Lex puo' rispondere con sintesi vera, link cliccabile e limiti chiari?",
)


@dataclass(frozen=True)
class LegalAutoFetchConfig:
    intelligence_db: str
    giurisprudenza_db: str = ""
    ai_base_url: str = ""
    ai_model: str = "mistral"
    queue_db_path: str = ""
    cursor_path: str = ""
    source_budget: int = 8
    publish_max_items: int = 40
    item_timeout_seconds: int = 180
    max_attempts: int = 3
    execute_due_sources: bool = True
    export_json_enabled: bool = False
    mirror_giurisprudenza_json_enabled: bool = False

    @classmethod
    def from_job_config(
        cls,
        config: LegalUpdateJobConfig,
        *,
        queue_db_path: str = "",
        cursor_path: str = "",
        source_budget: int = 8,
        publish_max_items: int = 40,
        item_timeout_seconds: int = 180,
        max_attempts: int = 3,
        execute_due_sources: bool = True,
    ) -> "LegalAutoFetchConfig":
        return cls(
            intelligence_db=config.intelligence_db,
            giurisprudenza_db=config.giurisprudenza_db,
            ai_base_url=config.ai_base_url,
            ai_model=config.ai_model,
            queue_db_path=queue_db_path,
            cursor_path=cursor_path,
            source_budget=source_budget,
            publish_max_items=publish_max_items,
            item_timeout_seconds=item_timeout_seconds,
            max_attempts=max_attempts,
            execute_due_sources=execute_due_sources,
            export_json_enabled=config.export_json_enabled,
            mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
        )

    def to_job_config(self) -> LegalUpdateJobConfig:
        return LegalUpdateJobConfig(
            intelligence_db=self.intelligence_db,
            giurisprudenza_db=self.giurisprudenza_db,
            ai_base_url=self.ai_base_url,
            ai_model=self.ai_model,
            export_json_enabled=self.export_json_enabled,
            mirror_giurisprudenza_json_enabled=self.mirror_giurisprudenza_json_enabled,
        )


class LegalAutoFetchCursorStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA, "sources": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA, "sources": {}}
        if not isinstance(payload, dict):
            return {"schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA, "sources": {}}
        payload.setdefault("schema", LEGAL_UPDATE_AUTOFETCH_SCHEMA)
        payload.setdefault("sources", {})
        return payload

    def save(self, payload: Mapping[str, Any]) -> None:
        data = dict(payload or {})
        data["schema"] = LEGAL_UPDATE_AUTOFETCH_SCHEMA
        data.setdefault("sources", {})
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def mark_enqueued(self, source_code: str, *, enqueued_at: str, job_id: str, due_reason: str) -> None:
        payload = self.load()
        sources = dict(payload.get("sources") or {})
        row = dict(sources.get(_source_code(source_code)) or {})
        row.update(
            {
                "source_code": _source_code(source_code),
                "last_enqueued_at": enqueued_at,
                "last_job_id": job_id,
                "last_due_reason": due_reason,
            }
        )
        sources[_source_code(source_code)] = row
        payload["sources"] = sources
        payload["updated_at"] = enqueued_at
        self.save(payload)

    def mark_result(self, source_code: str, *, status: str, finished_at: str, error: str = "") -> None:
        payload = self.load()
        sources = dict(payload.get("sources") or {})
        row = dict(sources.get(_source_code(source_code)) or {})
        failures = int(row.get("consecutive_failures") or 0)
        if status == "completed":
            failures = 0
        elif status in {"failed", "timeout"}:
            failures += 1
        row.update(
            {
                "source_code": _source_code(source_code),
                "last_status": status,
                "last_finished_at": finished_at,
                "last_error": error,
                "consecutive_failures": failures,
            }
        )
        sources[_source_code(source_code)] = row
        payload["sources"] = sources
        payload["updated_at"] = finished_at
        self.save(payload)


def build_legal_autofetch_plan(
    sources: Sequence[Mapping[str, Any]],
    *,
    cursor_payload: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    source_budget: int = 8,
    only_source_codes: Iterable[str] = (),
) -> dict[str, Any]:
    now_dt = now or datetime.now(tz=UTC)
    cursors = dict((cursor_payload or {}).get("sources") or {})
    allowed = {_source_code(code) for code in only_source_codes if _source_code(code)}
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for raw_source in sources:
        source = dict(raw_source or {})
        code = _source_code(source.get("code"))
        if not code:
            continue
        if allowed and code not in allowed:
            skipped.append({"source_code": code, "reason": "fuori_selezione"})
            continue
        if not bool(source.get("enabled", True)):
            skipped.append({"source_code": code, "reason": "fonte_disattivata"})
            continue
        cursor = dict(cursors.get(code) or {})
        interval_minutes = _positive_int(source.get("polling_minutes"), 1440)
        last_enqueued = _parse_dt(cursor.get("last_enqueued_at"))
        due_at = (last_enqueued + timedelta(minutes=interval_minutes)) if last_enqueued else now_dt
        due = last_enqueued is None or now_dt >= due_at
        if not due:
            skipped.append(
                {
                    "source_code": code,
                    "reason": "non_ancora_dovuta",
                    "due_at": _iso(due_at),
                }
            )
            continue
        failures = int(cursor.get("consecutive_failures") or 0)
        priority = _source_priority(source) + min(failures, 5)
        candidates.append(
            {
                "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
                "source_code": code,
                "source_name": str(source.get("name") or code),
                "source_id": int(source.get("id") or 0),
                "base_url": str(source.get("base_url") or ""),
                "category": str(source.get("category") or ""),
                "is_official": bool(source.get("is_official")),
                "polling_minutes": interval_minutes,
                "last_enqueued_at": str(cursor.get("last_enqueued_at") or ""),
                "due_at": _iso(due_at),
                "due_reason": "mai_eseguita" if last_enqueued is None else "intervallo_scaduto",
                "priority": priority,
                "quality_questions": list(LEGAL_SOURCE_QUALITY_QUESTIONS),
            }
        )

    budget = max(1, int(source_budget or 1))
    selected = sorted(candidates, key=lambda row: (-int(row["priority"]), row["due_at"], row["source_code"]))[:budget]
    overflow = [row | {"reason": "oltre_budget"} for row in candidates if row not in selected]
    return {
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "generated_at": _iso(now_dt),
        "source_budget": budget,
        "selected": selected,
        "skipped": skipped + overflow,
        "selected_count": len(selected),
        "skipped_count": len(skipped) + len(overflow),
        "quality_questions": list(LEGAL_SOURCE_QUALITY_QUESTIONS),
    }


def run_legal_update_autofetch_tick(
    config: LegalAutoFetchConfig,
    *,
    pipeline: LegalUpdatePipeline | None = None,
    source_codes: Sequence[str] = (),
    runner: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    runtime_pipeline = pipeline or build_legal_update_pipeline(
        config.intelligence_db,
        giurisprudenza_db_path=config.giurisprudenza_db,
        ai_base_url=config.ai_base_url,
        ai_model=config.ai_model,
        export_json_enabled=config.export_json_enabled,
        mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
    )
    queue = LegalUpdateJobQueue(_queue_path(config))
    cursor_store = LegalAutoFetchCursorStore(_cursor_path(config))
    cursor_payload = cursor_store.load()
    sources = runtime_pipeline.repository.list_sources(enabled_only=False)
    plan = build_legal_autofetch_plan(
        sources,
        cursor_payload=cursor_payload,
        now=now,
        source_budget=config.source_budget,
        only_source_codes=source_codes,
    )
    enqueued_jobs = []
    generated_at = str(plan.get("generated_at") or _iso(now or datetime.now(tz=UTC)))
    for item in plan["selected"]:
        job = queue.enqueue(
            source_code=item["source_code"],
            source_name=item["source_name"],
            item_url=item["base_url"],
            item_title=item["source_name"],
            item_kind="fonte",
            payload={
                "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
                "mode": "autofetch_governato",
                "source_code": item["source_code"],
                "source_id": item["source_id"],
                "source_name": item["source_name"],
                "base_url": item["base_url"],
                "due_reason": item["due_reason"],
                "quality_questions": item["quality_questions"],
            },
            timeout_seconds=config.item_timeout_seconds,
            max_attempts=config.max_attempts,
        )
        enqueued_jobs.append(job.to_dict())
        cursor_store.mark_enqueued(
            item["source_code"],
            enqueued_at=generated_at,
            job_id=job.job_id,
            due_reason=str(item.get("due_reason") or ""),
        )

    execution_report: dict[str, Any] = {"ok": True, "mode": "enqueue_only", "reports": []}
    selected_codes = [str(item.get("source_code") or "") for item in plan["selected"]]
    if config.execute_due_sources and selected_codes:
        execution_report = run_legal_update_batch_with_timeouts(
            config.to_job_config(),
            source_codes=selected_codes,
            auto_publish=True,
            item_timeout_seconds=config.item_timeout_seconds,
            publish_max_items=config.publish_max_items,
            runner=runner,
        )
        for row in list(execution_report.get("reports") or []):
            code = _source_code(row.get("label"))
            if not code:
                continue
            status = "completed" if row.get("ok") else ("timeout" if row.get("timeout") else "failed")
            cursor_store.mark_result(
                code,
                status=status,
                finished_at=str(row.get("finished_at") or generated_at),
                error=str(row.get("stderr") or row.get("inner_errors") or ""),
            )

    monitor = build_legal_update_operational_monitor(
        config,
        pipeline=runtime_pipeline,
        queue=queue,
        cursor_payload=cursor_store.load(),
    )
    return {
        "ok": bool(execution_report.get("ok", True)),
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "queue_schema": LEGAL_UPDATE_JOB_QUEUE_SCHEMA,
        "plan": plan,
        "enqueued_jobs": enqueued_jobs,
        "execution_report": execution_report,
        "monitor": monitor,
    }


def build_legal_update_operational_monitor(
    config: LegalAutoFetchConfig,
    *,
    pipeline: LegalUpdatePipeline | None = None,
    queue: LegalUpdateJobQueue | None = None,
    cursor_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_pipeline = pipeline or build_legal_update_pipeline(
        config.intelligence_db,
        giurisprudenza_db_path=config.giurisprudenza_db,
        ai_base_url=config.ai_base_url,
        ai_model=config.ai_model,
        export_json_enabled=config.export_json_enabled,
        mirror_giurisprudenza_json_enabled=config.mirror_giurisprudenza_json_enabled,
    )
    runtime_queue = queue or LegalUpdateJobQueue(_queue_path(config))
    snapshot = runtime_pipeline.dashboard_snapshot()
    sources = runtime_pipeline.repository.list_sources(enabled_only=False)
    activity = runtime_pipeline.repository.source_activity_summary()
    agent_runs = runtime_pipeline.repository.latest_source_agent_runs()
    cursors = dict((cursor_payload or {}).get("sources") or {})
    source_rows = [
        _source_monitor_row(source, activity.get(_source_code(source.get("code")), {}), agent_runs.get(_source_code(source.get("code"))), cursors)
        for source in sources
    ]
    jobs = [job.to_dict() for job in runtime_queue.list_jobs(limit=20)]
    queue_summary = runtime_queue.summary()
    blocked = [
        row for row in source_rows
        if row["status"] in {"da_verificare", "non_pronta"}
    ]
    return {
        "schema": LEGAL_UPDATE_AUTOFETCH_SCHEMA,
        "generated_at": _iso(datetime.now(tz=UTC)),
        "queue": queue_summary,
        "recent_jobs": jobs,
        "sources": source_rows,
        "sources_total": len(source_rows),
        "sources_ready": sum(1 for row in source_rows if row["status"] == "pronta"),
        "sources_not_ready": len(blocked),
        "quality_questions": list(LEGAL_SOURCE_QUALITY_QUESTIONS),
        "dashboard_counts": snapshot.get("headline") or snapshot,
        "readiness": {
            "status": "pronto" if not blocked and int(queue_summary.get("failed") or 0) == 0 and int(queue_summary.get("timeout") or 0) == 0 else "da_verificare",
            "blocked_sources": len(blocked),
            "queued_jobs": int(queue_summary.get("queued") or 0),
            "running_jobs": int(queue_summary.get("running") or 0),
            "failed_jobs": int(queue_summary.get("failed") or 0),
            "timeout_jobs": int(queue_summary.get("timeout") or 0),
        },
    }


def _source_monitor_row(
    source: Mapping[str, Any],
    activity: Mapping[str, Any],
    agent_run: Mapping[str, Any] | None,
    cursors: Mapping[str, Any],
) -> dict[str, Any]:
    code = _source_code(source.get("code"))
    raw_documents = _positive_int(activity.get("raw_documents"), 0)
    normalized_documents = _positive_int(activity.get("normalized_documents"), 0)
    review_pending = _positive_int(activity.get("review_pending"), 0)
    review_published = _positive_int(activity.get("review_published"), 0)
    cursor = dict(cursors.get(code) or {})
    latest_status = str((agent_run or {}).get("status") or cursor.get("last_status") or "").lower()
    if not bool(source.get("enabled", True)):
        status = "non_monitorata"
        reason = "Fonte disattivata."
    elif latest_status in {"failed", "timeout"}:
        status = "da_verificare"
        reason = str((agent_run or {}).get("error_message") or cursor.get("last_error") or "Ultimo controllo non riuscito.")
    elif raw_documents or normalized_documents or review_published:
        status = "pronta"
        reason = "Fonte con dati acquisiti o pubblicati."
    else:
        status = "non_pronta"
        reason = "Fonte censita ma ancora senza documenti acquisiti."
    return {
        "source_code": code,
        "source_name": str(source.get("name") or code),
        "enabled": bool(source.get("enabled", True)),
        "is_official": bool(source.get("is_official")),
        "status": status,
        "reason": reason,
        "raw_documents": raw_documents,
        "normalized_documents": normalized_documents,
        "review_pending": review_pending,
        "review_published": review_published,
        "last_enqueued_at": str(cursor.get("last_enqueued_at") or ""),
        "last_finished_at": str(cursor.get("last_finished_at") or (agent_run or {}).get("finished_at") or ""),
        "last_job_id": str(cursor.get("last_job_id") or ""),
        "consecutive_failures": _positive_int(cursor.get("consecutive_failures"), 0),
    }


def _queue_path(config: LegalAutoFetchConfig) -> Path:
    if str(config.queue_db_path or "").strip():
        return Path(config.queue_db_path)
    return Path(str(config.intelligence_db or "./intelligence/motori.json")).parent / "legal_update_jobs.sqlite"


def _cursor_path(config: LegalAutoFetchConfig) -> Path:
    if str(config.cursor_path or "").strip():
        return Path(config.cursor_path)
    return Path(str(config.intelligence_db or "./intelligence/motori.json")).parent / "legal_autofetch_cursors.json"


def _source_priority(source: Mapping[str, Any]) -> int:
    score = 0
    if bool(source.get("is_official")):
        score += 10
    category = str(source.get("category") or "").lower()
    if category == "giurisprudenza":
        score += 5
    if category == "normativa":
        score += 4
    return score


def _source_code(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().split())


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value or 0)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime) -> str:
    normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
