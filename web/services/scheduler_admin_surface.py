"""Payload e azioni per la console superadmin delle pianificazioni."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app

from pct.scheduler_registry import (
    DELEGATED_AGENT_TEMPLATES,
    SchedulerRegistryRepository,
    apply_scheduler_registry,
    dispatch_requested_manual_runs,
    scheduler_registry_repository,
    template_catalog,
)


def _repository() -> SchedulerRegistryRepository:
    return scheduler_registry_repository(current_app.config)


def _status_class(status: str) -> str:
    key = str(status or "").strip().lower()
    if key == "completed":
        return "success"
    if key in {"failed", "error", "missed"}:
        return "danger"
    if key == "running":
        return "primary"
    if key == "requested":
        return "warning"
    return "secondary"


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _payload_error_messages(value: Any) -> list[str]:
    messages: list[str] = []
    if isinstance(value, dict):
        if value.get("ok") is False:
            messages.append("Controllo interno non riuscito.")
        for key in ("error", "error_message"):
            message = str(value.get(key) or "").strip()
            if message:
                messages.append(message)
        inner_errors = value.get("inner_errors")
        if isinstance(inner_errors, list):
            messages.extend(str(item).strip() for item in inner_errors if str(item or "").strip())
        for nested in value.values():
            messages.extend(_payload_error_messages(nested))
    elif isinstance(value, list):
        for item in value:
            messages.extend(_payload_error_messages(item))
    return list(dict.fromkeys(messages))


def _sum_metric(value: Any, metric_name: str) -> int:
    if isinstance(value, dict):
        total = _int_value(value.get(metric_name))
        for nested in value.values():
            total += _sum_metric(nested, metric_name)
        return total
    if isinstance(value, list):
        return sum(_sum_metric(item, metric_name) for item in value)
    return 0


def _published_count(value: Any) -> int:
    if isinstance(value, dict):
        total = 0
        for key in ("published_count", "autopublished_count"):
            total += _int_value(value.get(key))
        autopublished = value.get("autopublished")
        if isinstance(autopublished, dict):
            total += _int_value(autopublished.get("count"))
        for nested in value.values():
            if nested is not autopublished:
                total += _published_count(nested)
        return total
    if isinstance(value, list):
        return sum(_published_count(item) for item in value)
    return 0


def _is_legal_update_run(run: dict[str, Any]) -> bool:
    text = " ".join(
        str(run.get(key) or "")
        for key in ("job_id", "template_key", "job_name", "job_family")
    ).lower()
    return "legal_" in text or "aggiornamenti legali" in text or "fonte legale" in text


def _is_stale_running(run: dict[str, Any]) -> bool:
    if str(run.get("status") or "").strip().lower() != "running":
        return False
    started = _parse_datetime(run.get("started_at") or run.get("created_at"))
    if started is None:
        return True
    return datetime.now(timezone.utc) - started > timedelta(hours=2)


def _legal_update_message(run: dict[str, Any]) -> str:
    result = run.get("result") if isinstance(run.get("result"), dict) else {}
    documents_read = _sum_metric(result, "documents_found")
    analyzed = _sum_metric(result, "processed")
    discarded = _sum_metric(result, "skipped_unchanged")
    published = _published_count(result)
    discarded_label = f", {discarded} invariati o scartati" if discarded else ""
    if published > 0:
        return (
            f"{documents_read} documenti letti, {analyzed} analizzati, "
            f"{published} schede pubblicate{discarded_label}."
        )
    return (
        f"Controllo completato, nessuna scheda pubblicata: "
        f"{documents_read} documenti letti, {analyzed} analizzati{discarded_label}."
    )


def _surface_run(run: dict[str, Any]) -> dict[str, Any]:
    row = dict(run)
    status = str(row.get("status") or "").strip().lower()
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    errors = _payload_error_messages(result)
    if status == "completed" and errors:
        row["status"] = "failed"
        row["status_label"] = "Da verificare"
        row["status_class"] = "danger"
        if not str(row.get("message") or "").strip():
            row["message"] = "; ".join(errors[:3])
        return row
    if _is_stale_running(row):
        row["status"] = "failed"
        row["status_label"] = "Interrotto, da verificare"
        row["status_class"] = "danger"
        row["message"] = "Esecuzione rimasta in corso oltre il tempo atteso."
        return row
    row["status_class"] = _status_class(status)
    if status == "completed" and _is_legal_update_run(row):
        row["status_label"] = "Controllo completato"
        row["message"] = _legal_update_message(row)
    return row


def _job_status(job: dict[str, Any], latest_run: dict[str, Any] | None) -> dict[str, str]:
    if not job.get("enabled"):
        return {"label": "Pausata", "class": "secondary"}
    if latest_run:
        status = str(latest_run.get("status") or "")
        if status in {"failed", "error", "missed"}:
            return {"label": str(latest_run.get("status_label") or "Da verificare"), "class": "danger"}
        if status == "requested":
            return {"label": "Richiesta", "class": "warning"}
        if status == "running":
            return {"label": "In corso", "class": "primary"}
    return {"label": "Attiva", "class": "success"}


def build_scheduler_admin_surface() -> dict[str, Any]:
    repo = _repository()
    repo.upsert_default_jobs(current_app.config)
    latest = {job_id: _surface_run(run) for job_id, run in repo.latest_runs_by_job().items()}
    jobs = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in repo.list_jobs():
        latest_run = latest.get(str(job.get("job_id") or ""))
        payload = {
            **job,
            "latest_run": latest_run,
            "status": _job_status(job, latest_run),
        }
        jobs.append(payload)
        grouped[str(job.get("family") or "Altro")].append(payload)
    recent_runs = [_surface_run(run) for run in repo.list_recent_runs(limit=40)]
    templates = [
        {
            "key": tpl.key,
            "name": tpl.name,
            "family": tpl.family,
            "description": tpl.description,
            "criteria": list(tpl.criteria),
        }
        for tpl in DELEGATED_AGENT_TEMPLATES
    ]
    return {
        "totals": repo.totals(),
        "jobs": jobs,
        "families": [
            {"name": family, "jobs": sorted(items, key=lambda row: str(row.get("name") or ""))}
            for family, items in sorted(grouped.items(), key=lambda item: item[0])
        ],
        "recent_runs": recent_runs,
        "agent_templates": templates,
        "template_catalog": [
            {
                "key": tpl.key,
                "name": tpl.name,
                "family": tpl.family,
                "built_in": tpl.built_in,
                "description": tpl.description,
            }
            for tpl in template_catalog(current_app.config)
        ],
        "registry_db": str(repo.db_path),
    }


def save_scheduler_job_from_payload(job_id: str, payload: dict[str, Any], *, username: str = "") -> dict[str, Any]:
    repo = _repository()
    repo.upsert_default_jobs(current_app.config)
    updated = repo.save_job(
        job_id,
        {
            "name": payload.get("name"),
            "description": payload.get("description"),
            "trigger_kind": payload.get("trigger_kind"),
            "hour": payload.get("hour"),
            "minute": payload.get("minute"),
            "interval_minutes": payload.get("interval_minutes"),
            "day_of_week": payload.get("day_of_week"),
            "enabled": payload.get("enabled"),
        },
        updated_by=username,
    )
    _apply_now(repo)
    return updated


def create_scheduler_job_from_payload(payload: dict[str, Any], *, username: str = "") -> dict[str, Any]:
    repo = _repository()
    repo.upsert_default_jobs(current_app.config)
    created = repo.create_job_from_template(
        str(payload.get("template_key") or ""),
        name=str(payload.get("name") or ""),
        trigger_kind=str(payload.get("trigger_kind") or "cron"),
        hour=str(payload.get("hour") or ""),
        minute=str(payload.get("minute") or "0"),
        interval_minutes=int(payload.get("interval_minutes") or 0),
        enabled=str(payload.get("enabled") or "").lower() in {"1", "true", "on", "yes"},
        created_by=username,
    )
    _apply_now(repo)
    return created


def request_scheduler_run(job_id: str, *, username: str = "") -> dict[str, Any]:
    repo = _repository()
    repo.upsert_default_jobs(current_app.config)
    request = repo.request_manual_run(job_id, requested_by=username)
    _apply_now(repo)
    return request


def _apply_now(repo: SchedulerRegistryRepository) -> None:
    scheduler = current_app.config.get("PCT_SCHEDULER")
    if scheduler is None:
        return
    apply_scheduler_registry(scheduler, current_app._get_current_object(), repo)
    dispatch_requested_manual_runs(scheduler, current_app._get_current_object(), repo)
