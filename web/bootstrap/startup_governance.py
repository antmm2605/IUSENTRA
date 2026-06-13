"""Governance di avvio differita per runtime web IUSENTRA."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable

from flask import Flask

from pct import __version__ as APP_VERSION
from pct.installation_packs import bootstrap_pack_governance
from pct.tenant import GestioneTenant
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si", "sì"}


def _startup_governance_sync(app: Flask) -> bool:
    if app.testing:
        return True
    return _truthy(app.config.get("STARTUP_GOVERNANCE_SYNC") or os.getenv("IUSENTRA_STARTUP_GOVERNANCE_SYNC"))


def _startup_governance_child() -> bool:
    return _truthy(os.getenv("IUSENTRA_STARTUP_GOVERNANCE_CHILD"))


def _startup_governance_autorun(app: Flask) -> bool:
    if app.testing:
        return True
    return _truthy(app.config.get("STARTUP_GOVERNANCE_AUTORUN") or os.getenv("IUSENTRA_STARTUP_GOVERNANCE_AUTORUN"))


def _startup_governance_delay_seconds(app: Flask) -> float:
    if app.testing:
        return 0.0
    raw = app.config.get("STARTUP_GOVERNANCE_DELAY_SECONDS") or os.getenv("IUSENTRA_STARTUP_GOVERNANCE_DELAY_SECONDS") or "30"
    try:
        return max(0.0, min(float(raw), 300.0))
    except (TypeError, ValueError):
        return 30.0


def _startup_lock_path(app: Flask, key: str) -> Path:
    root = Path(str(app.config.get("PCT_DATA_ROOT") or os.getenv("PCT_DATA_ROOT") or "/tmp"))
    return root / ".startup-locks" / f"{key}.lock"


def _run_once_with_startup_lock(app: Flask, key: str, task: Callable[[], None]) -> bool:
    lock_path = _startup_lock_path(app, key)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if lock_path.exists() and time.time() - lock_path.stat().st_mtime > 30 * 60:
            lock_path.unlink(missing_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        app.logger.info("Startup governance %s già in corso in un altro worker.", key)
        return False
    except OSError as exc:
        app.logger.warning("Startup governance %s senza lock dedicato: %s", key, exc)
        task()
        return True

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()} started_at={time.time()}\n")
        task()
        return True
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _claim_startup_marker(app: Flask, key: str, *, stale_seconds: int = 6 * 60 * 60) -> bool:
    marker_path = _startup_lock_path(app, key)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if marker_path.exists() and time.time() - marker_path.stat().st_mtime > stale_seconds:
            marker_path.unlink(missing_ok=True)
        fd = os.open(str(marker_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        app.logger.info("Startup governance %s già dispatchata per questo avvio.", key)
        return False
    except OSError as exc:
        app.logger.warning("Startup governance %s senza marker dispatch: %s", key, exc)
        return True
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"pid={os.getpid()} dispatched_at={time.time()}\n")
    return True


def _run_startup_governance(app: Flask) -> None:
    if app.config.get("MULTI_TENANT"):
        _run_once_with_startup_lock(
            app,
            "tenant-user-directory",
            lambda: GestioneTenant(app.config["TENANTS_REGISTRY"]).sync_user_directory(
                secret_key=app.secret_key,
                reconcile_storage=False,
            ),
        )

    _run_once_with_startup_lock(
        app,
        "pack-governance",
        lambda: bootstrap_pack_governance(
            app_root=Path(__file__).resolve().parents[2],
            registry_path=str(app.config.get("TENANTS_REGISTRY", "./data/tenants.json")),
            app_version=APP_VERSION,
        ),
    )

    def _legacy_bootstrap() -> None:
        bootstrap_report = bootstrap_legacy_tenant_runtime_data(app)
        if bootstrap_report.get("copied") or bootstrap_report.get("sqlite_migrated"):
            app.logger.info(
                "Bootstrap legacy tenant in avvio per %s: copied=%s sqlite=%s",
                bootstrap_report.get("target_slug", ""),
                ",".join(sorted(bootstrap_report.get("copied", {}).keys())) or "-",
                bootstrap_report.get("sqlite_migrated", False),
            )

    _run_once_with_startup_lock(app, "legacy-tenant-bootstrap", _legacy_bootstrap)


def _schedule_startup_governance(app: Flask) -> None:
    if _startup_governance_child():
        app.logger.info("Startup governance: runner figlio attivo, non pianifico altri processi.")
        return
    if not _startup_governance_autorun(app):
        app.logger.info(
            "Startup governance non critica disattivata in avvio; usare IUSENTRA_STARTUP_GOVERNANCE_AUTORUN=1 per abilitarla."
        )
        return
    if _startup_governance_sync(app):
        _run_startup_governance(app)
        return
    delay_seconds = _startup_governance_delay_seconds(app)
    app_root = Path(__file__).resolve().parents[2]

    def _worker() -> None:
        with app.app_context():
            try:
                if delay_seconds:
                    app.logger.info(
                        "Startup governance differita: avvio in background tra %.0f secondi.",
                        delay_seconds,
                    )
                    time.sleep(delay_seconds)
                if not _claim_startup_marker(app, "startup-governance-dispatch"):
                    return
                env = os.environ.copy()
                env["IUSENTRA_STARTUP_GOVERNANCE_CHILD"] = "1"
                subprocess.Popen(
                    [sys.executable, "-m", "web.bootstrap.startup_governance_runner"],
                    cwd=str(app_root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=os.name != "nt",
                )
                app.logger.info("Startup governance differita: processo separato avviato.")
            except Exception as exc:
                app.logger.exception("Errore startup governance differita: %s", exc)

    thread = threading.Thread(target=_worker, name="iusentra-startup-governance", daemon=True)
    thread.start()
    app.extensions["startup_governance_thread"] = thread
