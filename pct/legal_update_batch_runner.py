from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class LegalUpdateJobConfig:
    intelligence_db: str
    giurisprudenza_db: str = ""
    ai_base_url: str = ""
    ai_model: str = "mistral"
    export_json_enabled: bool = False
    mirror_giurisprudenza_json_enabled: bool = False
    python_executable: str = sys.executable


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    for start in (0, text.find("{")):
        if start < 0:
            continue
        try:
            return json.loads(text[start:])
        except json.JSONDecodeError:
            continue
    return {"raw_stdout": text[-4000:]}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_source_report(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload") or {}
    report = payload.get("report") or {}
    rows = list(report.get("reports") or [])
    documents_found = 0
    processed = 0
    skipped_unchanged = 0
    for row in rows:
        documents_found += int(row.get("documents_found") or 0)
        processed += int(row.get("processed") or 0)
        skipped_unchanged += int(row.get("skipped_unchanged") or 0)
    autopublished = report.get("autopublished") or {}
    publish_reports = list(autopublished.get("reports") or [])
    verification_evidence_saved = int(report.get("verification_evidence_saved") or 0)
    verification_attachments_saved = int(report.get("verification_attachments_saved") or 0)
    web_verification_attempts = int(report.get("web_verification_attempts") or 0)
    for publish_result in publish_reports:
        published_payload = publish_result.get("payload") if isinstance(publish_result, dict) else {}
        published = published_payload.get("published") if isinstance(published_payload, dict) else {}
        if not isinstance(published, dict):
            continue
        verification_evidence_saved += int(published.get("verification_evidence_saved") or 0)
        verification_attachments_saved += int(published.get("verification_attachments_saved") or 0)
        web_verification_attempts += int(published.get("web_verification_attempts") or 0)
    return {
        "documents_found": documents_found,
        "processed": processed,
        "skipped_unchanged": skipped_unchanged,
        "autopublished_count": int(autopublished.get("count") or payload.get("published_count") or 0),
        "verification_evidence_saved": verification_evidence_saved,
        "verification_attachments_saved": verification_attachments_saved,
        "web_verification_attempts": web_verification_attempts,
    }


def _source_payload_errors(result: dict[str, Any]) -> list[str]:
    payload = result.get("payload") or {}
    report = payload.get("report") or {}
    rows = list(report.get("reports") or [])
    errors = [
        str(row.get("error") or "").strip()
        for row in rows
        if str(row.get("error") or "").strip()
    ]
    if str(payload.get("error") or "").strip():
        errors.append(str(payload.get("error")).strip())
    return errors


def _normalize_source_subprocess_result(result: dict[str, Any]) -> dict[str, Any]:
    errors = _source_payload_errors(result)
    if not errors:
        return result
    normalized = dict(result)
    normalized["ok"] = False
    normalized["inner_errors"] = errors
    return normalized


def _source_error_message(result: dict[str, Any], row_errors: list[str]) -> str:
    message = str(result.get("stderr") or "")
    if row_errors:
        message = row_errors[0]
    if str(result.get("label") or "") == "giustizia_amministrativa" and row_errors:
        message = (
            f"{message} Risoluzione automatica: fonte HTML diretta in osservazione; "
            "presidio automatico affidato a OpenGA ufficiale."
        )
    if result.get("timeout"):
        message = f"Timeout dopo {int(result.get('seconds') or 0)} secondi."
    return message


def _record_source_agent_run(
    config: LegalUpdateJobConfig,
    result: dict[str, Any],
    *,
    source_name: str = "",
    trigger_label: str = "batch",
) -> None:
    source_code = str(result.get("label") or "").strip()
    if not source_code or source_code == "publish":
        return
    try:
        from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository

        cfg = LegalUpdateDbConfig.from_anchor(config.intelligence_db)
        repository = LegalUpdateRepository(cfg.db_path, json_path=cfg.json_path)
        source = repository.get_source_by_code(source_code) or {}
        metrics = _extract_source_report(result)
        timeout = bool(result.get("timeout"))
        row_errors = _source_payload_errors(result)
        ok = bool(result.get("ok")) and not row_errors
        payload = result.get("payload") or {}
        error_message = _source_error_message(result, row_errors)
        repository.record_source_agent_run(
            source_code=source_code,
            source_name=source_name or str(source.get("name") or ""),
            trigger_label=trigger_label,
            status="completed" if ok else ("timeout" if timeout else "failed"),
            timeout_seconds=int(result.get("seconds") or 0),
            started_at=str(result.get("started_at") or ""),
            finished_at=str(result.get("finished_at") or ""),
            duration_ms=int(result.get("duration_ms") or 0),
            documents_found=metrics["documents_found"],
            processed=metrics["processed"],
            skipped_unchanged=metrics["skipped_unchanged"],
            autopublished_count=metrics["autopublished_count"],
            error_message=error_message,
            stderr_tail=str(result.get("stderr") or ""),
            payload=payload,
        )
    except Exception:
        return


def build_legal_update_job_command(
    config: LegalUpdateJobConfig,
    *,
    source_code: str = "",
    publish_only: bool = False,
    publish_limit: int = 1,
    auto_publish: bool = False,
) -> list[str]:
    command = [
        config.python_executable or sys.executable,
        "-m",
        "pct.legal_update_job",
        "--intelligence-db",
        config.intelligence_db,
        "--giurisprudenza-db",
        config.giurisprudenza_db,
        "--local-ai-url",
        config.ai_base_url,
        "--local-ai-model",
        config.ai_model or "mistral",
    ]
    if config.export_json_enabled:
        command.append("--export-json")
    if config.mirror_giurisprudenza_json_enabled:
        command.append("--mirror-giurisprudenza-json")
    if publish_only:
        command.extend(["--publish-only", "--publish-limit", str(max(1, int(publish_limit or 1)))])
    else:
        command.extend(["--source-code", str(source_code or "").strip()])
        if not auto_publish:
            command.append("--no-auto-publish")
    return command


def run_legal_update_subprocess(
    config: LegalUpdateJobConfig,
    *,
    source_code: str = "",
    publish_only: bool = False,
    publish_limit: int = 1,
    auto_publish: bool = False,
    timeout_seconds: int = 180,
    runner: Runner | None = None,
) -> dict[str, Any]:
    runner = runner or subprocess.run
    started_at = _iso_now()
    started_monotonic = time.monotonic()
    command = build_legal_update_job_command(
        config,
        source_code=source_code,
        publish_only=publish_only,
        publish_limit=publish_limit,
        auto_publish=auto_publish,
    )
    label = "publish" if publish_only else str(source_code or "")
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds or 1)),
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        finished_at = _iso_now()
        return {
            "ok": False,
            "timeout": True,
            "label": label,
            "seconds": max(1, int(timeout_seconds or 1)),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
            "stderr": str(exc),
        }

    finished_at = _iso_now()
    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    return_code = int(getattr(completed, "returncode", 1) or 0)
    return {
        "ok": return_code == 0,
        "timeout": False,
        "label": label,
        "returncode": return_code,
        "seconds": max(1, int(timeout_seconds or 1)),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
        "payload": _parse_json_stdout(stdout),
        "stderr": stderr[-4000:],
    }


def run_legal_update_publish_queue_with_timeouts(
    config: LegalUpdateJobConfig,
    *,
    item_timeout_seconds: int = 180,
    max_items: int = 40,
    runner: Runner | None = None,
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    published_count = 0
    verification_evidence_saved = 0
    verification_attachments_saved = 0
    web_verification_attempts = 0
    max_items = max(1, int(max_items or 1))
    for _ in range(max_items):
        result = run_legal_update_subprocess(
            config,
            publish_only=True,
            publish_limit=1,
            timeout_seconds=item_timeout_seconds,
            runner=runner,
        )
        result = _normalize_source_subprocess_result(result)
        reports.append(result)
        if not result.get("ok"):
            break
        payload = result.get("payload") or {}
        published_payload = payload.get("published") if isinstance(payload, dict) else {}
        published_metrics = published_payload if isinstance(published_payload, dict) else {}
        if published_metrics:
            verification_evidence_saved += int(published_metrics.get("verification_evidence_saved") or 0)
            verification_attachments_saved += int(published_metrics.get("verification_attachments_saved") or 0)
            web_verification_attempts += int(published_metrics.get("web_verification_attempts") or 0)
        count = int((payload.get("published_count") if isinstance(payload, dict) else 0) or 0)
        published_count += count
        if count <= 0 and not int(published_metrics.get("web_verification_attempts") or 0):
            break
    return {
        "ok": all(row.get("ok") for row in reports) if reports else True,
        "mode": "publish_queue_timeout",
        "published_count": published_count,
        "verification_evidence_saved": verification_evidence_saved,
        "verification_attachments_saved": verification_attachments_saved,
        "web_verification_attempts": web_verification_attempts,
        "timeouts": sum(1 for row in reports if row.get("timeout")),
        "reports": reports,
    }


def run_legal_update_batch_with_timeouts(
    config: LegalUpdateJobConfig,
    *,
    source_codes: Sequence[str],
    auto_publish: bool = True,
    item_timeout_seconds: int = 180,
    publish_max_items: int = 40,
    runner: Runner | None = None,
    record_agent_runs: bool | None = None,
) -> dict[str, Any]:
    should_record_runs = bool(record_agent_runs) if record_agent_runs is not None else runner is None
    sources = [str(code or "").strip() for code in source_codes if str(code or "").strip()]
    reports: list[dict[str, Any]] = []
    for source_code in sources:
        result = run_legal_update_subprocess(
            config,
            source_code=source_code,
            auto_publish=False,
            timeout_seconds=item_timeout_seconds,
            runner=runner,
        )
        result = _normalize_source_subprocess_result(result)
        reports.append(result)
        if should_record_runs:
            _record_source_agent_run(config, result, trigger_label="batch")

    published = {"published_count": 0, "timeouts": 0, "reports": []}
    if auto_publish:
        published = run_legal_update_publish_queue_with_timeouts(
            config,
            item_timeout_seconds=item_timeout_seconds,
            max_items=publish_max_items,
            runner=runner,
        )

    return {
        "ok": all(row.get("ok") for row in reports) and bool(published.get("ok", True)),
        "mode": "source_batch_timeout",
        "sources": sources,
        "reports": reports,
        "timeouts": sum(1 for row in reports if row.get("timeout")) + int(published.get("timeouts") or 0),
        "autopublished": {
            "count": int(published.get("published_count") or 0),
            "items": [],
            "reports": published.get("reports") or [],
            "verification_evidence_saved": int(published.get("verification_evidence_saved") or 0),
            "verification_attachments_saved": int(published.get("verification_attachments_saved") or 0),
            "web_verification_attempts": int(published.get("web_verification_attempts") or 0),
        },
    }
