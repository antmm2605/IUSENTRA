"""Controlla che i servizi Docker IUSENTRA siano allineati alla release corrente."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct import __version__ as APP_VERSION


APPLICATION_SERVICES = ("app", "scheduler-worker", "ocr-worker")
DEFAULT_SCHEDULER_JOB = "lex_sentenza_economia_auto"
INTERNAL_CONTROL_JOBS = {"scheduler_registry_reload"}


def _compose_base(compose_file: str = "", env_file: str = "") -> list[str]:
    command = ["docker", "compose"]
    if env_file:
        command.extend(["--env-file", env_file])
    if compose_file:
        command.extend(["-f", compose_file])
    return command


def _run(command: list[str], *, cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _parse_docker_created_at(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ([+-]\d{4})", raw)
    if match:
        compact = f"{match.group(1)} {match.group(2)}"
        try:
            return datetime.strptime(compact, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            return None
    return _parse_datetime(raw)


def _iso_utc(value: datetime | None = None) -> str:
    return (value or _utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_json_object(output: str) -> dict[str, Any]:
    for line in reversed((output or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def filter_latest_runs_for_wait(
    latest_runs: dict[str, Any],
    *,
    target_job_id: str,
    since_utc: datetime | None,
) -> dict[str, Any]:
    if not since_utc:
        return dict(latest_runs or {})
    since_literal = _iso_utc(since_utc)
    filtered: dict[str, Any] = {}
    for key, row in dict(latest_runs or {}).items():
        if str(key) != target_job_id:
            filtered[key] = row
            continue
        observed_at = str(
            (row or {}).get("finished_at")
            or (row or {}).get("started_at")
            or (row or {}).get("created_at")
            or ""
        )
        if observed_at >= since_literal:
            filtered[key] = row
    return filtered


def parse_compose_ps_json(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    stripped = str(output or "").strip()
    if not stripped:
        return rows
    try:
        payload = json.loads(stripped)
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
    except json.JSONDecodeError:
        pass
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _label_value(labels: Any, key: str) -> str:
    if isinstance(labels, dict):
        return str(labels.get(key) or "").strip()
    raw = str(labels or "")
    match = re.search(rf"(?:^|,){re.escape(key)}=([^,]+)", raw)
    return match.group(1).strip() if match else ""


def validate_compose_services(
    rows: list[dict[str, Any]],
    *,
    expected_version: str = APP_VERSION,
    application_services: tuple[str, ...] = APPLICATION_SERVICES,
) -> dict[str, Any]:
    errors: list[str] = []
    service_rows = {str(row.get("Service") or ""): row for row in rows if row.get("Service")}
    services: list[dict[str, Any]] = []
    for service, row in sorted(service_rows.items()):
        state = str(row.get("State") or "").lower()
        health = str(row.get("Health") or "").lower()
        image_version = _label_value(row.get("Labels"), "org.opencontainers.image.version")
        item = {
            "service": service,
            "state": state,
            "health": health,
            "image": str(row.get("Image") or ""),
            "image_version": image_version,
            "created_at": str(row.get("CreatedAt") or ""),
        }
        services.append(item)
        if state != "running":
            errors.append(f"{service}: stato Docker non running ({state or 'n.d.'}).")
        if health and health != "healthy":
            errors.append(f"{service}: health non healthy ({health}).")
    for service in application_services:
        row = service_rows.get(service)
        if row is None:
            errors.append(f"{service}: servizio applicativo mancante in docker compose ps.")
            continue
        image_version = _label_value(row.get("Labels"), "org.opencontainers.image.version")
        if image_version != expected_version:
            errors.append(
                f"{service}: immagine {image_version or 'senza versione'} diversa dalla release {expected_version}."
            )
    return {"ok": not errors, "expected_version": expected_version, "services": services, "errors": errors}


def validate_container_versions(
    versions: dict[str, str],
    *,
    expected_version: str = APP_VERSION,
    application_services: tuple[str, ...] = APPLICATION_SERVICES,
) -> dict[str, Any]:
    errors: list[str] = []
    for service in application_services:
        found = str(versions.get(service) or "").strip()
        if found != expected_version:
            errors.append(f"{service}: pct.__version__={found or 'n.d.'}, atteso {expected_version}.")
    return {"ok": not errors, "versions": versions, "errors": errors}


def validate_scheduler_job(payload: dict[str, Any], *, job_id: str = DEFAULT_SCHEDULER_JOB) -> dict[str, Any]:
    job = str(payload.get("job") or "").strip()
    trigger = str(payload.get("trigger") or "").strip()
    errors: list[str] = []
    if job != job_id:
        errors.append(f"scheduler-worker: job {job_id} non registrato.")
    if job_id == DEFAULT_SCHEDULER_JOB and "*/10" not in trigger and "7-57/10" not in trigger:
        errors.append(f"scheduler-worker: trigger inatteso per {job_id}: {trigger or 'n.d.'}.")
    return {"ok": not errors, "job": job, "trigger": trigger, "errors": errors}


def expected_job_interval_seconds(job: dict[str, Any]) -> int:
    kind = str(job.get("trigger_kind") or "").strip().lower()
    if kind == "interval":
        try:
            minutes = int(job.get("interval_minutes") or 0)
        except (TypeError, ValueError):
            minutes = 0
        return max(60, minutes * 60) if minutes > 0 else 0
    if kind != "cron":
        return 0
    minute = str(job.get("minute") or "").strip()
    hour = str(job.get("hour") or "").strip()
    day_of_week = str(job.get("day_of_week") or "").strip()
    if day_of_week:
        return 8 * 24 * 60 * 60
    if re.fullmatch(r"\*/([1-9]\d?)", minute):
        interval = int(minute[2:])
        if not hour:
            return interval * 60
        if re.fullmatch(r"\d{1,2}(,\d{1,2})*", hour):
            return 24 * 60 * 60
    if re.fullmatch(r"\d{1,2}-\d{1,2}/([1-9]\d?)", minute):
        interval = int(minute.rsplit("/", 1)[1])
        if not hour:
            return interval * 60
        if re.fullmatch(r"\d{1,2}(,\d{1,2})*", hour):
            return 24 * 60 * 60
    if not hour and re.fullmatch(r"\d{1,2}(,\d{1,2})*", minute):
        return 60 * 60
    return 24 * 60 * 60


def job_due_window_seconds(job: dict[str, Any], *, grace_seconds: int = 180) -> int:
    interval = expected_job_interval_seconds(job)
    return interval + max(60, int(grace_seconds or 0)) if interval else 0


def validate_scheduler_run_audit(
    payload: dict[str, Any],
    *,
    job_id: str = DEFAULT_SCHEDULER_JOB,
    now: datetime | None = None,
    require_all_due: bool = False,
    worker_started_at: datetime | None = None,
    require_target_completed: bool = True,
) -> dict[str, Any]:
    jobs = list(payload.get("jobs") or [])
    latest_runs = dict(payload.get("latest_runs") or {})
    now_dt = now or _utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    audited: list[dict[str, Any]] = []
    for job in jobs:
        current_job_id = str(job.get("job_id") or "").strip()
        if not current_job_id:
            continue
        if not bool(job.get("enabled")):
            audited.append(
                {
                    "job_id": current_job_id,
                    "status": "paused",
                    "reason": "Pianificazione disattivata.",
                }
            )
            continue
        run = latest_runs.get(current_job_id) if isinstance(latest_runs, dict) else None
        status = str((run or {}).get("status") or "").strip().lower()
        finished_at = _parse_datetime((run or {}).get("finished_at") or (run or {}).get("started_at"))
        due_window = job_due_window_seconds(job)
        required_now = current_job_id == job_id
        due_since_worker_start = (
            True
            if worker_started_at is None or due_window <= 0
            else now_dt - worker_started_at > timedelta(seconds=due_window)
        )
        should_have_run = bool(due_window and finished_at and now_dt - finished_at > timedelta(seconds=due_window))
        never_ran = run is None and due_window > 0
        entry = {
            "job_id": current_job_id,
            "name": str(job.get("name") or current_job_id),
            "family": str(job.get("family") or ""),
            "trigger_kind": str(job.get("trigger_kind") or ""),
            "hour": str(job.get("hour") or ""),
            "minute": str(job.get("minute") or ""),
            "day_of_week": str(job.get("day_of_week") or ""),
            "due_window_seconds": due_window,
            "latest_status": status or "none",
            "latest_finished_at": _iso_utc(finished_at) if finished_at else "",
            "latest_message": str((run or {}).get("message") or ""),
            "latest_error": str((run or {}).get("error_message") or ""),
        }
        if current_job_id in INTERNAL_CONTROL_JOBS:
            entry["status"] = "internal_control"
            entry["reason"] = (
                "Job interno del worker: applica modifiche e richieste manuali, "
                "verificato indirettamente dal registro scheduler e dai run applicativi."
            )
            audited.append(entry)
            continue
        if status in {"failed", "error", "missed"}:
            reason = entry["latest_error"] or entry["latest_message"] or "Esecuzione non completata."
            errors.append(f"{current_job_id}: ultimo run {status}: {reason}")
            entry["status"] = "failed"
            entry["reason"] = reason
        elif status == "running":
            started_at = _parse_datetime((run or {}).get("started_at") or (run or {}).get("created_at"))
            max_running = max(due_window, 2 * 60 * 60) if due_window else 2 * 60 * 60
            if not started_at or now_dt - started_at > timedelta(seconds=max_running):
                errors.append(f"{current_job_id}: run in corso oltre il tempo atteso.")
                entry["status"] = "stale_running"
                entry["reason"] = "Run rimasto in corso oltre il tempo atteso."
            elif required_now and require_target_completed:
                errors.append(f"{current_job_id}: run avviato ma non ancora completato dal worker.")
                entry["status"] = "running"
                entry["reason"] = "Run avviato, attesa conclusione con riepilogo operativo."
            else:
                entry["status"] = "running"
                entry["reason"] = "Run in corso nel tempo atteso."
        elif never_ran and (required_now or (require_all_due and due_since_worker_start)):
            errors.append(
                f"{current_job_id}: nessun run registrato; il worker non ha ancora dimostrato l'esecuzione reale."
            )
            entry["status"] = "never_ran"
            entry["reason"] = "Nessun run registrato nel registro pianificazioni."
        elif should_have_run and (required_now or (require_all_due and due_since_worker_start)):
            errors.append(
                f"{current_job_id}: ultimo run troppo vecchio ({entry['latest_finished_at']}); finestra attesa {due_window}s."
            )
            entry["status"] = "stale"
            entry["reason"] = "Ultima esecuzione oltre la finestra attesa."
        elif never_ran:
            if due_since_worker_start:
                warnings.append(f"{current_job_id}: nessun run registrato; non ancora richiesto come gate bloccante.")
                entry["status"] = "not_yet_observed"
                entry["reason"] = "Job attivo, ma senza esecuzione registrata nella finestra di controllo."
            else:
                entry["status"] = "not_due"
                entry["reason"] = "Worker riavviato prima della prossima finestra utile del job."
        elif should_have_run:
            if require_all_due and not due_since_worker_start:
                warnings.append(
                    f"{current_job_id}: ultimo run oltre finestra, ma il worker non ha ancora raggiunto "
                    "la prossima finestra utile dopo il riavvio."
                )
                entry["status"] = "not_due_after_restart"
                entry["reason"] = (
                    "Ultima esecuzione precedente alla finestra attesa; il worker è stato riavviato "
                    "e non ha ancora raggiunto la prossima scadenza del job."
                )
            else:
                warnings.append(f"{current_job_id}: ultimo run oltre finestra, da monitorare.")
                entry["status"] = "stale_warning"
                entry["reason"] = "Ultima esecuzione vecchia, non bloccante per questo gate."
        else:
            entry["status"] = "ok"
            entry["reason"] = "Ultimo run registrato coerente."
        result = (run or {}).get("result") if isinstance((run or {}).get("result"), dict) else {}
        if current_job_id == job_id and status == "completed":
            if result.get("ok") is False:
                reason = str(result.get("error") or entry["latest_error"] or "Esito job negativo.")
                errors.append(f"{current_job_id}: risultato interno negativo: {reason}")
                entry["status"] = "failed"
                entry["reason"] = reason
            totals = result.get("totals") if isinstance(result.get("totals"), dict) else {}
            if not totals:
                errors.append(f"{current_job_id}: run completato senza riepilogo operativo totals.")
                entry["status"] = "failed"
                entry["reason"] = "Manca il riepilogo operativo del backfill."
            elif int(totals.get("errors") or 0) > 0:
                errors.append(f"{current_job_id}: backfill con {int(totals.get('errors') or 0)} errori.")
                entry["status"] = "failed"
                entry["reason"] = "Il motore backfill ha registrato errori."
            elif int(totals.get("vector_embedding_errors") or 0) > 0:
                errors.append(
                    f"{current_job_id}: Lex AI ha {int(totals.get('vector_embedding_errors') or 0)} errori embedding."
                )
                entry["status"] = "failed"
                entry["reason"] = "Indicizzazione vettoriale non completata."
            entry["totals"] = totals
        audited.append(entry)
    if job_id and not any(str(job.get("job_id") or "") == job_id for job in jobs):
        errors.append(f"{job_id}: pianificazione non presente nel registro scheduler.")
    return {
        "ok": not errors,
        "checked_at": _iso_utc(now_dt),
        "jobs_checked": len(audited),
        "jobs": audited,
        "errors": errors,
        "warnings": warnings,
    }


def collect_compose_services(*, cwd: Path, compose_file: str = "", env_file: str = "") -> dict[str, Any]:
    completed = _run(_compose_base(compose_file, env_file) + ["ps", "--format", "json"], cwd=cwd, timeout=60)
    if completed.returncode != 0:
        return {"ok": False, "error": completed.stderr.strip() or completed.stdout.strip()}
    rows = parse_compose_ps_json(completed.stdout)
    return validate_compose_services(rows)


def collect_container_versions(*, cwd: Path, compose_file: str = "", env_file: str = "") -> dict[str, Any]:
    versions: dict[str, str] = {}
    for service in APPLICATION_SERVICES:
        completed = _run(
            _compose_base(compose_file, env_file)
            + ["exec", "-T", service, "python", "-c", "import pct; print(pct.__version__)"],
            cwd=cwd,
            timeout=60,
        )
        versions[service] = (completed.stdout or "").strip().splitlines()[-1] if completed.returncode == 0 else ""
    return validate_container_versions(versions)


def collect_scheduler_job(
    *, cwd: Path, compose_file: str = "", env_file: str = "", job_id: str = DEFAULT_SCHEDULER_JOB
) -> dict[str, Any]:
    code = f"""
import json
from pct.scheduler_worker import start_scheduler_worker
app = start_scheduler_worker()
scheduler = app.config.get("PCT_SCHEDULER")
job = scheduler.get_job({job_id!r}) if scheduler else None
print(json.dumps({{"job": job.id if job else "", "trigger": str(job.trigger) if job else ""}}))
if scheduler:
    scheduler.shutdown(wait=False)
"""
    completed = _run(
        _compose_base(compose_file, env_file) + ["exec", "-T", "scheduler-worker", "python", "-c", code],
        cwd=cwd,
        timeout=120,
    )
    if completed.returncode != 0:
        return {"ok": False, "job": "", "trigger": "", "errors": [completed.stderr.strip() or completed.stdout.strip()]}
    payload: dict[str, Any] = {}
    for line in reversed((completed.stdout or "").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    return validate_scheduler_job(payload, job_id=job_id)


def _collect_scheduler_audit_once(
    *,
    cwd: Path,
    compose_file: str = "",
    env_file: str = "",
    job_id: str = DEFAULT_SCHEDULER_JOB,
    since_utc: datetime | None = None,
    require_all_due: bool = False,
    worker_started_at: datetime | None = None,
    require_target_completed: bool = True,
) -> dict[str, Any]:
    code = f"""
import json
from pct.scheduler_worker import create_scheduler_app
from pct.scheduler_registry import scheduler_registry_repository
app = create_scheduler_app()
repo = scheduler_registry_repository(app.config)
repo.upsert_default_jobs(app.config)
jobs = repo.list_jobs(include_disabled=True)
latest = repo.latest_runs_by_job()
print(json.dumps({{"jobs": jobs, "latest_runs": latest}}, ensure_ascii=False, default=str))
"""
    completed = _run(
        _compose_base(compose_file, env_file) + ["exec", "-T", "scheduler-worker", "python", "-c", code],
        cwd=cwd,
        timeout=120,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        return {
            "ok": False,
            "checked_at": _iso_utc(),
            "jobs_checked": 0,
            "jobs": [],
            "errors": [f"scheduler-worker: registro job non leggibile: {detail}"],
            "warnings": [],
        }
    payload = _last_json_object(completed.stdout)
    if not payload:
        return {
            "ok": False,
            "checked_at": _iso_utc(),
            "jobs_checked": 0,
            "jobs": [],
            "errors": ["scheduler-worker: risposta audit job non leggibile."],
            "warnings": [],
        }
    payload["latest_runs"] = filter_latest_runs_for_wait(
        dict(payload.get("latest_runs") or {}),
        target_job_id=job_id,
        since_utc=since_utc,
    )
    return validate_scheduler_run_audit(
        payload,
        job_id=job_id,
        require_all_due=require_all_due,
        worker_started_at=worker_started_at,
        require_target_completed=require_target_completed,
    )


def collect_scheduler_run_audit(
    *,
    cwd: Path,
    compose_file: str = "",
    env_file: str = "",
    job_id: str = DEFAULT_SCHEDULER_JOB,
    wait_seconds: int = 0,
    poll_seconds: int = 20,
    require_all_due: bool = False,
    worker_started_at: datetime | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0, int(wait_seconds or 0))
    since_utc = _utc_now() if wait_seconds else None
    attempts: list[dict[str, Any]] = []
    while True:
        report = _collect_scheduler_audit_once(
            cwd=cwd,
            compose_file=compose_file,
            env_file=env_file,
            job_id=job_id,
            since_utc=since_utc,
            require_all_due=require_all_due,
            worker_started_at=worker_started_at,
            require_target_completed=True,
        )
        attempts.append(
            {
                "checked_at": report.get("checked_at"),
                "ok": report.get("ok"),
                "errors": list(report.get("errors") or []),
            }
        )
        if report.get("ok") or time.monotonic() >= deadline:
            if attempts:
                report["attempts"] = attempts
            if wait_seconds:
                report["wait_seconds"] = int(wait_seconds)
                report["wait_started_at"] = _iso_utc(since_utc)
            return report
        sleep_for = min(max(1, int(poll_seconds or 20)), max(1, int(deadline - time.monotonic())))
        time.sleep(sleep_for)


def run_check(
    *,
    cwd: Path = REPO_ROOT,
    compose_file: str = "",
    env_file: str = "",
    job_id: str = DEFAULT_SCHEDULER_JOB,
    wait_job_seconds: int = 0,
    require_all_due_jobs: bool = False,
) -> dict[str, Any]:
    services = collect_compose_services(cwd=cwd, compose_file=compose_file, env_file=env_file)
    versions = collect_container_versions(cwd=cwd, compose_file=compose_file, env_file=env_file)
    scheduler = collect_scheduler_job(cwd=cwd, compose_file=compose_file, env_file=env_file, job_id=job_id)
    scheduler_started_at = None
    for service in services.get("services") or []:
        if service.get("service") == "scheduler-worker":
            scheduler_started_at = _parse_docker_created_at(service.get("created_at"))
            break
    scheduler_runs = collect_scheduler_run_audit(
        cwd=cwd,
        compose_file=compose_file,
        env_file=env_file,
        job_id=job_id,
        wait_seconds=wait_job_seconds,
        require_all_due=require_all_due_jobs,
        worker_started_at=scheduler_started_at,
    )
    errors = (
        list(services.get("errors") or [])
        + list(versions.get("errors") or [])
        + list(scheduler.get("errors") or [])
        + list(scheduler_runs.get("errors") or [])
    )
    if services.get("error"):
        errors.append(str(services["error"]))
    return {
        "ok": not errors,
        "expected_version": APP_VERSION,
        "services": services,
        "versions": versions,
        "scheduler": scheduler,
        "scheduler_runs": scheduler_runs,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica servizi runtime IUSENTRA Docker.")
    parser.add_argument("--cwd", default=str(REPO_ROOT), help="Directory del progetto Docker Compose.")
    parser.add_argument("--compose-file", default="", help="File compose alternativo.")
    parser.add_argument("--env-file", default="", help="File env da passare a docker compose.")
    parser.add_argument("--scheduler-job", default=DEFAULT_SCHEDULER_JOB, help="Job scheduler obbligatorio.")
    parser.add_argument(
        "--wait-job-seconds",
        type=int,
        default=0,
        help="Attende una nuova esecuzione reale del job obbligatorio prima di fallire.",
    )
    parser.add_argument(
        "--require-all-due-jobs",
        action="store_true",
        help="Rende bloccanti anche i job attivi con esecuzione dovuta ma mancante o troppo vecchia.",
    )
    args = parser.parse_args(argv)
    report = run_check(
        cwd=Path(args.cwd),
        compose_file=args.compose_file,
        env_file=args.env_file,
        job_id=args.scheduler_job,
        wait_job_seconds=max(0, int(args.wait_job_seconds or 0)),
        require_all_due_jobs=bool(args.require_all_due_jobs),
    )
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
