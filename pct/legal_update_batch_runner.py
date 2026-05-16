from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
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
        return {
            "ok": False,
            "timeout": True,
            "label": label,
            "seconds": max(1, int(timeout_seconds or 1)),
            "stderr": str(exc),
        }

    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    return_code = int(getattr(completed, "returncode", 1) or 0)
    return {
        "ok": return_code == 0,
        "timeout": False,
        "label": label,
        "returncode": return_code,
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
    max_items = max(1, int(max_items or 1))
    for _ in range(max_items):
        result = run_legal_update_subprocess(
            config,
            publish_only=True,
            publish_limit=1,
            timeout_seconds=item_timeout_seconds,
            runner=runner,
        )
        reports.append(result)
        if not result.get("ok"):
            break
        count = int(((result.get("payload") or {}).get("published_count")) or 0)
        published_count += count
        if count <= 0:
            break
    return {
        "ok": all(row.get("ok") for row in reports) if reports else True,
        "mode": "publish_queue_timeout",
        "published_count": published_count,
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
) -> dict[str, Any]:
    sources = [str(code or "").strip() for code in source_codes if str(code or "").strip()]
    reports: list[dict[str, Any]] = []
    for source_code in sources:
        reports.append(
            run_legal_update_subprocess(
                config,
                source_code=source_code,
                auto_publish=False,
                timeout_seconds=item_timeout_seconds,
                runner=runner,
            )
        )

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
        },
    }
