"""Assemblaggio dei runtime applicativi per i profili web IUSENTRA."""

from __future__ import annotations

from dataclasses import dataclass, field
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
from pct.runtime_env import is_managed_cloud_runtime
from pct.tenant import GestioneTenant
from web.services.core_runtime import build_core_runtime
from web.services.document_crypto import decrypt_doc, encrypt_doc
from web.services.fascicoli_runtime import build_fascicoli_runtime
from web.services.ocr_runtime import build_ocr_runtime
from web.services.pdp_penale_runtime import build_pdp_penale_runtime
from web.services.telematico_runtime import build_telematico_runtime
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data
from web.services.tenant_isolation_runtime import register_tenant_isolation_runtime


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


@dataclass(slots=True)
class ApplicationRuntimeBundle:
    """Bundle dei runtime costruiti durante il bootstrap dell'applicazione."""

    scheduler_only: bool
    core: dict[str, Any]
    ocr_runtime: Any | None = None
    fascicoli: dict[str, Any] = field(default_factory=dict)
    telematico: dict[str, Any] = field(default_factory=dict)
    pdp_penale: dict[str, Any] = field(default_factory=dict)


def build_application_runtime_bundle(
    app: Flask,
    cfg: dict[str, Any],
) -> ApplicationRuntimeBundle:
    """Costruisce i runtime del profilo web completo o del worker scheduler."""

    core = build_core_runtime(app, cfg)
    register_tenant_isolation_runtime(app)
    scheduler_only = bool(app.config.get("PCT_SCHEDULER_WORKER"))
    if scheduler_only:
        return ApplicationRuntimeBundle(
            scheduler_only=True,
            core=core,
        )

    startup_governance_enabled = not is_managed_cloud_runtime()

    if startup_governance_enabled:
        _schedule_startup_governance(app)
    else:
        app.logger.info(
            "Runtime cloud gestito: rinvio bootstrap tenant e governance pesante dopo il primo avvio."
        )

    ocr_runtime = build_ocr_runtime(
        queue_db_path=app.config.get("OCR_QUEUE_DB"),
        search_index_path=str(app.config.get("SEARCH_INDEX", "")),
    )
    app.extensions["ocr_runtime"] = ocr_runtime
    fascicoli = build_fascicoli_runtime(
        app,
        get_deposito_guidato=core["get_deposito_guidato"],
        get_config_studio=core["get_config_studio"],
        get_utenti=core["get_utenti"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        accoda_ocr=ocr_runtime.enqueue,
        encrypt_doc=encrypt_doc,
        decrypt_doc=decrypt_doc,
    )

    telematico: dict[str, Any] = {}
    pdp_penale = build_pdp_penale_runtime(
        app,
        get_pdp_penale=core["get_pdp_penale"],
        get_fascicoli=core["get_fascicoli"],
        get_config_studio=core["get_config_studio"],
        get_clienti=core["get_clienti"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        resolve_ufficio_destinatario=fascicoli["resolve_ufficio_destinatario"],
        polis_demo_mode=lambda: telematico.get("polis_demo_mode", lambda: True)(),
        salva_documento_fascicolo=fascicoli["salva_documento_fascicolo"],
        espandi_file_importato_portale=fascicoli["espandi_file_importato_portale"],
        pst_import_dir_for_fascicolo=fascicoli["pst_import_dir_for_fascicolo"],
        leggi_staging_documenti_portale=fascicoli["leggi_staging_documenti_portale"],
        archivia_staging_documenti_portale=fascicoli["archivia_staging_documenti_portale"],
        normalizza_nome_match_portale=fascicoli["normalizza_nome_match_portale"],
        fascicolo_text=fascicoli["fascicolo_text"],
    )
    telematico = build_telematico_runtime(
        app,
        cfg_data_path=core["cfg_data_path"],
        get_config_studio=core["get_config_studio"],
        get_pdp_penale=core["get_pdp_penale"],
        get_telematico=core["get_telematico"],
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_soggetti=core["get_soggetti"],
        get_scadenziario=core["get_scadenziario"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        normalizza_nome_match_portale=fascicoli["normalizza_nome_match_portale"],
        tipo_documento_da_item_portale=fascicoli["tipo_documento_da_item_portale"],
        salva_documento_fascicolo=fascicoli["salva_documento_fascicolo"],
        salva_albero_originale_documenti_portale=fascicoli["salva_albero_originale_documenti_portale"],
        catalogo_documenti_portale_fascicolo=fascicoli["catalogo_documenti_portale_fascicolo"],
        gruppa_catalogo_documenti_portale=fascicoli["gruppa_catalogo_documenti_portale"],
        decode_portale_downloaded_items=fascicoli["decode_portale_downloaded_items"],
        importa_documenti_portale_items=fascicoli["importa_documenti_portale_items"],
        portale_ufficiale_label=fascicoli["portale_ufficiale_label"],
        ensure_pdp_penale_case_after_import=pdp_penale["ensure_pdp_penale_case_after_import"],
    )

    return ApplicationRuntimeBundle(
        scheduler_only=False,
        core=core,
        ocr_runtime=ocr_runtime,
        fascicoli=fascicoli,
        telematico=telematico,
        pdp_penale=pdp_penale,
    )
