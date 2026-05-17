"""Payload e azioni per la console superadmin delle pianificazioni."""

from __future__ import annotations

from collections import defaultdict
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


def _job_status(job: dict[str, Any], latest_run: dict[str, Any] | None) -> dict[str, str]:
    if not job.get("enabled"):
        return {"label": "Pausata", "class": "secondary"}
    if latest_run:
        status = str(latest_run.get("status") or "")
        if status in {"failed", "error", "missed"}:
            return {"label": "Da verificare", "class": "danger"}
        if status == "requested":
            return {"label": "Richiesta", "class": "warning"}
        if status == "running":
            return {"label": "In corso", "class": "primary"}
    return {"label": "Attiva", "class": "success"}


def build_scheduler_admin_surface() -> dict[str, Any]:
    repo = _repository()
    repo.upsert_default_jobs(current_app.config)
    latest = repo.latest_runs_by_job()
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
    recent_runs = repo.list_recent_runs(limit=40)
    for run in recent_runs:
        run["status_class"] = _status_class(str(run.get("status") or ""))
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
