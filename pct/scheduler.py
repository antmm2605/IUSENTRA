"""
pct/scheduler.py - Scheduler background per task automatici.

Usa APScheduler (gia' in requirements.txt) per:
  - Backup automatico giornaliero (ora configurabile)
  - Promemoria WhatsApp appuntamenti di domani (ogni giorno alle 18:00)
  - Aggiornamento scadenze SCADUTE (ogni notte)
  - Invio email di report settimanale (opzionale)

Avviato da un worker dedicato tramite pct.scheduler_worker.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from pct.daily_plan.clock import ROME_TZ
from pct.legal_update_autofetch import (
    LEGAL_UPDATE_PROGRESSIVE_CASSAZIONE_MAX_ITEMS,
    LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS,
    LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS,
    LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET,
    LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES,
)
from pct.runtime_env import is_managed_cloud_runtime

logger = logging.getLogger("pct.scheduler")

_DAILY_PLAN_AUTOMATIC_HOUR = "5"
_DAILY_PLAN_AUTOMATIC_MINUTE = "30"
_DAILY_PLAN_RECOVERY_START = (6, 0)


def _flag_enabled(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _backup_jobs_disabled(app) -> bool:
    """Fail closed: gli archivi automatici richiedono un opt-in esplicito."""
    from pct.backup import backup_operations_disabled

    return backup_operations_disabled(app.config)


def _scheduler_bootstrap_allowed(app) -> bool:
    return bool(app.config.get("PCT_SCHEDULER_WORKER")) or _flag_enabled(
        app.config.get("ALLOW_INLINE_SCHEDULER")
    ) or _flag_enabled(os.environ.get("PCT_ALLOW_INLINE_SCHEDULER"))


def _parse_hhmm(value: object, default: str) -> tuple[int, int]:
    raw = str(value or default).strip()
    try:
        hour, minute = map(int, raw.split(":", 1))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (TypeError, ValueError):
        pass
    default_hour, default_minute = map(int, default.split(":", 1))
    return default_hour, default_minute


def _parse_positive_int(value: object, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _runtime_path(app, key: str, env_key: str, default: str) -> str:
    return str(app.config.get(key) or os.getenv(env_key) or default)


def _scheduler_rome_now(app) -> datetime:
    """Ora del worker; il valore fissato serve solo ai test isolati."""
    fixed = app.config.get("PCT_SCHEDULER_NOW_FOR_TESTS")
    if isinstance(fixed, datetime):
        if fixed.tzinfo is None:
            return fixed.replace(tzinfo=ROME_TZ)
        return fixed.astimezone(ROME_TZ)
    return datetime.now(ROME_TZ)


def daily_plan_startup_recovery_allowed(
    now: datetime, registry_job: dict[str, object] | None
) -> bool:
    """Decide il recupero post-avvio senza sovrapporsi al cron delle 05:30.

    Dalle 05:30 alle 05:59 APScheduler puo' ancora eseguire il cron mancato
    grazie al relativo ``misfire_grace_time``. Il recovery separato parte
    quindi solo dalle 06:00 e rispetta un'eventuale scelta umana fatta nella
    console Pianificazioni.
    """
    current = now.replace(tzinfo=ROME_TZ) if now.tzinfo is None else now.astimezone(ROME_TZ)
    if (current.hour, current.minute) < _DAILY_PLAN_RECOVERY_START:
        return False
    if registry_job is None:
        # Se il registro non e' leggibile, il cron nativo resta il presidio
        # primario; il recupero mantiene la garanzia di non lasciare vuota la
        # giornata quando il worker e' ripartito tardi.
        return True

    enabled = registry_job.get("enabled", True)
    if str(enabled).strip().lower() in {"0", "false", "off", "no", ""}:
        return False
    if str(registry_job.get("updated_by") or "system") == "system":
        return True

    # Una persona puo' mantenere il job attivo ma spostarlo o convertirlo in
    # manuale: in quel caso il suo orario prevale anche sul self-heal.
    return (
        str(registry_job.get("trigger_kind") or "cron") == "cron"
        and str(registry_job.get("hour") or "") == _DAILY_PLAN_AUTOMATIC_HOUR
        and str(registry_job.get("minute") or "") == _DAILY_PLAN_AUTOMATIC_MINUTE
    )


def _run_scheduler_command(label: str, command: list[str], *, timeout_seconds: int) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_seconds or 1)),
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("[scheduler] %s timeout dopo %ss", label, timeout_seconds)
        return {"ok": False, "timeout": True, "label": label, "stderr": str(exc)}

    if completed.returncode != 0:
        logger.error(
            "[scheduler] %s fallito rc=%s: %s",
            label,
            completed.returncode,
            (completed.stderr or completed.stdout or "")[-1200:],
        )
        return {
            "ok": False,
            "timeout": False,
            "label": label,
            "returncode": completed.returncode,
            "stderr": (completed.stderr or "")[-4000:],
            "stdout": (completed.stdout or "")[-4000:],
        }
    logger.info("[scheduler] %s completato: %s", label, (completed.stdout or "").strip()[-800:])
    return {
        "ok": True,
        "timeout": False,
        "label": label,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-4000:],
    }


def start_scheduler(app):
    """
    Avvia lo scheduler APScheduler in background.
    Chiamare una sola volta dal worker dedicato.
    Sicuro in modalita' multi-worker grazie al lock ambientale.
    """
    if _flag_enabled(os.environ.get("PCT_DISABLE_SCHEDULER")) or _flag_enabled(
        app.config.get("DISABLE_SCHEDULER")
    ):
        logger.info("[scheduler] Avvio disabilitato da configurazione.")
        return None
    if not _scheduler_bootstrap_allowed(app):
        logger.info(
            "[scheduler] Avvio ignorato: consentito solo su worker dedicato o con override esplicito."
        )
        return None
    # Evita di avviare lo scheduler in Flask debug reloader (processo duplicato)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" and app.debug:
        return
    # Evita doppioni in ambienti multi-worker (usa solo il master process)
    if os.environ.get("PCT_SCHEDULER_RUNNING"):
        return
    os.environ["PCT_SCHEDULER_RUNNING"] = "1"

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler non disponibile - task automatici disabilitati.")
        return

    # misfire_grace_time di APScheduler vale 1 secondo per default: su un worker
    # occupato (OCR della pipeline PEC, aggiornamenti legali) il giro successivo
    # dei presidi veniva semplicemente saltato e registrato come "missed",
    # lasciando lo studio senza PEC lavorate senza che nulla sembrasse rotto.
    # Cinque minuti di tolleranza fanno recuperare il giro; max_instances=1 e
    # coalesce evitano che i giri arretrati si accumulino e saturino la CPU.
    scheduler = BackgroundScheduler(
        timezone="Europe/Rome",
        job_defaults={"misfire_grace_time": 300, "coalesce": True, "max_instances": 1},
    )
    # Il cron mattutino, il recupero post-avvio e il primo giro incrementale
    # condividono il mutex: anche in caso di misfire o restart non possono
    # materializzare due volte lo stesso piano nello stesso processo.
    daily_plan_full_lock = Lock()
    registry_repo = None

    # ---- Backup giornaliero ----
    ora_backup = app.config.get("BACKUP_ORA", os.getenv("PCT_BACKUP_ORA", "02:00"))
    h, m = _parse_hhmm(ora_backup, "02:00")

    @scheduler.scheduled_job(CronTrigger(hour=h, minute=m), id="backup_giornaliero")
    def _backup():
        with app.app_context():
            if _backup_jobs_disabled(app):
                logger.info("[scheduler] Backup giornaliero non eseguito: archivi automatici disattivati.")
                return {"ok": True, "skipped": True, "reason": "backup_jobs_disabled"}
            try:
                from pct.database import GestioneDatabase
                db = GestioneDatabase(app.config)
                import tempfile
                out = tempfile.mkdtemp(prefix="iusentra_sched_")
                zip_path = db.esporta_tutto(out)
                logger.info(f"[scheduler] Backup completato: {zip_path}")
            except Exception as e:
                logger.error(f"[scheduler] Backup fallito: {e}")

    # ---- Aggiornamento scadenze scadute (ogni notte alle 00:05) ----
    @scheduler.scheduled_job(CronTrigger(hour=0, minute=5), id="aggiorna_scadute")
    def _aggiorna_scadute():
        with app.app_context():
            try:
                from pct.scadenziario import GestioneScadenziario
                gs = GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"])
                gs.aggiorna_scadute()
                logger.info("[scheduler] Scadenze aggiornate.")
            except Exception as e:
                logger.error(f"[scheduler] Aggiorna scadute fallito: {e}")

    # ---- Promemoria WhatsApp appuntamenti domani (ogni giorno alle 18:00) ----
    wa_ora = app.config.get("WA_REMINDER_ORA", os.getenv("PCT_WA_REMINDER_ORA", "18:00"))
    wh, wm = _parse_hhmm(wa_ora, "18:00")

    @scheduler.scheduled_job(CronTrigger(hour=wh, minute=wm), id="wa_reminder")
    def _wa_reminder():
        with app.app_context():
            try:
                from pct.agenda import Agenda
                from pct.clienti import GestioneClienti
                from pct.notifiche_wa import ConfigWA, promemoria_appuntamenti_di_domani
                cfg = ConfigWA(
                    twilio_sid=app.config.get("TWILIO_SID", ""),
                    twilio_token=app.config.get("TWILIO_TOKEN", ""),
                    twilio_numero=app.config.get("TWILIO_NUMERO", ""),
                    callmebot_key=app.config.get("CALLMEBOT_KEY", ""),
                )
                # Solo se c'e' un canale configurato
                if not cfg.ha_twilio and not cfg.ha_callmebot:
                    return
                ag = Agenda(db_path=app.config["AGENDA_DB"])
                gc = GestioneClienti(db_path=app.config["CLIENTI_DB"])
                studio_nome = app.config.get("STUDIO_NOME", "IUSENTRA")
                risultati = promemoria_appuntamenti_di_domani(
                    agenda=ag,
                    get_cliente_fn=gc.get,
                    config=cfg,
                    studio_nome=studio_nome,
                )
                if risultati:
                    logger.info(f"[scheduler] Promemoria WA inviati: {len(risultati)}")
            except Exception as e:
                logger.error(f"[scheduler] WA reminder fallito: {e}")

    # ---- Aggiorna parcelle scadute (ogni giorno alle 01:00) ----
    @scheduler.scheduled_job(CronTrigger(hour=1, minute=0), id="aggiorna_parcelle_scadute")
    def _parcelle_scadute():
        with app.app_context():
            try:
                db_path = app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
                if not os.path.exists(db_path):
                    return
                from pct.fatturazione import GestioneFatturazione
                gf = GestioneFatturazione(db_path=db_path)
                gf.aggiorna_scadute()
                logger.info("[scheduler] Parcelle scadute aggiornate.")
            except Exception as e:
                logger.error(f"[scheduler] Parcelle scadute fallito: {e}")

    # ---- Sync uffici giudiziari da fonti ufficiali (ogni giorno alle 03:30) ----
    # Fonti: PST MinGiust, giustizia-amministrativa.it, giustiziatributaria.gov.it, IPA PEC
    sync_uffici_ora = app.config.get("UFFICI_SYNC_ORA", os.getenv("PCT_UFFICI_SYNC_ORA", "03:30"))
    uh, um = _parse_hhmm(sync_uffici_ora, "03:30")

    @scheduler.scheduled_job(CronTrigger(hour=uh, minute=um), id="sync_uffici")
    def _sync_uffici():
        with app.app_context():
            try:
                from pct.sync_uffici import esegui_sync_completo
                cache_path = (
                    app.config.get("UFFICI_GIUDIZIARI_DB")
                    or os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                )
                report = esegui_sync_completo(cache_path)
                if report.get("ok"):
                    logger.info(
                        "[scheduler] Sync uffici completato: %d totali, +%d nuovi, %d PEC aggiornate, resolver PST=%s, report=%s",
                        report.get("n_totale_post", 0),
                        report.get("n_nuovi", 0),
                        report.get("n_pec_aggiornate", 0),
                        "ok" if (report.get("resolver_pst") or {}).get("ok") else "da_verificare",
                        report.get("report_markdown_path") or "n.d.",
                    )
                    # Log warning per ogni fonte fallita
                    for fonte, stato in report.get("fonti", {}).items():
                        if not stato.get("ok"):
                            logger.warning(
                                "[scheduler] Sync uffici: fonte '%s' non disponibile (%s)",
                                fonte, stato.get("motivo", "errore"),
                            )
                else:
                    logger.error("[scheduler] Sync uffici fallito: %s", report.get("errore"))
            except Exception as e:
                logger.error(f"[scheduler] Sync uffici fallito: {e}")

    # ---- Certificati pubblici PST di cifratura Atto.enc (settimanale) ----
    cert_sync_ora = app.config.get(
        "PST_CERTIFICATI_CIFRATURA_SYNC_ORA",
        os.getenv("PCT_PST_CERTIFICATI_CIFRATURA_SYNC_ORA", "03:45"),
    )
    cert_h, cert_m = _parse_hhmm(cert_sync_ora, "03:45")
    cert_day = str(
        app.config.get(
            "PST_CERTIFICATI_CIFRATURA_SYNC_GIORNO",
            os.getenv("PCT_PST_CERTIFICATI_CIFRATURA_SYNC_GIORNO", "sun"),
        )
        or "sun"
    ).strip() or "sun"

    @scheduler.scheduled_job(
        CronTrigger(day_of_week=cert_day, hour=cert_h, minute=cert_m),
        id="pst_certificati_cifratura_weekly",
    )
    def _sync_certificati_cifratura_pst():
        with app.app_context():
            try:
                from pct.pst_cifratura import (
                    esegui_controllo_settimanale_certificati_cifratura,
                )

                force_refresh = _flag_enabled(
                    app.config.get("PCT_PST_CERTIFICATI_CIFRATURA_FORCE_REFRESH")
                    or os.getenv("PCT_PST_CERTIFICATI_CIFRATURA_FORCE_REFRESH")
                )
                report = esegui_controllo_settimanale_certificati_cifratura(
                    force_refresh=force_refresh,
                    max_workers=_parse_positive_int(
                        app.config.get("PST_CERTIFICATI_CIFRATURA_WORKERS")
                        or os.getenv("PCT_PST_CERTIFICATI_CIFRATURA_WORKERS"),
                        6,
                    ),
                )
                if report.get("ok"):
                    logger.info(
                        "[scheduler] Certificati PST cifratura aggiornati: %d/%d, report=%s",
                        report.get("scaricati_o_validi", 0),
                        report.get("totale", 0),
                        report.get("report_path", "n.d."),
                    )
                else:
                    logger.warning(
                        "[scheduler] Certificati PST cifratura: %d ok, %d errori, report=%s",
                        report.get("scaricati_o_validi", 0),
                        report.get("errori", 0),
                        report.get("report_path", "n.d."),
                    )
                return report
            except Exception as e:
                logger.error("[scheduler] Certificati PST cifratura falliti: %s", e)
                return {"ok": False, "error": str(e), "job": "pst_certificati_cifratura_weekly"}

    def _run_legal_monitor(source_ids, label):
        with app.app_context():
            try:
                from pct.legal_intelligence import GestioneLegalIntelligence

                gestore = GestioneLegalIntelligence(
                    db_path=app.config.get("LEGAL_INTELLIGENCE_DB", "./intelligence/legal_intelligence.json"),
                    normative_db_path=app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json"),
                )
                report = gestore.run_monitor_cycle(source_ids=source_ids)
                if report.get("ok"):
                    logger.info(
                        "[scheduler] Legal intelligence %s: %d fonti aggiornate, %d tabelle sincronizzate",
                        label,
                        report.get("successful", 0),
                        report.get("normative_sync", {}).get("processed_tables", 0),
                    )
                else:
                    logger.warning(
                        "[scheduler] Legal intelligence %s: %d ok / %d fallite / %d tabelle in sync",
                        label,
                        report.get("successful", 0),
                        report.get("failed", 0),
                        report.get("normative_sync", {}).get("processed_tables", 0),
                    )
            except Exception as e:
                logger.error("[scheduler] Legal intelligence %s fallito: %s", label, e)

    def _run_legal_updates(source_ids, label, *, auto_publish=True):
        with app.app_context():
            try:
                from pct.legal_update_autofetch import LegalAutoFetchConfig, run_legal_update_autofetch_tick
                from pct.legal_update_batch_runner import LegalUpdateJobConfig

                timeout_seconds = _parse_positive_int(
                    app.config.get("LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS")
                    or os.getenv("LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS")
                    or os.getenv("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS"),
                    LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS,
                )
                publish_max_items = _parse_positive_int(
                    app.config.get("LEGAL_UPDATES_PUBLISH_MAX_ITEMS")
                    or os.getenv("LEGAL_UPDATES_PUBLISH_MAX_ITEMS")
                    or os.getenv("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS"),
                    LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS,
                )
                source_budget = _parse_positive_int(
                    app.config.get("LEGAL_AUTOFETCH_SOURCE_BUDGET")
                    or os.getenv("LEGAL_AUTOFETCH_SOURCE_BUDGET")
                    or os.getenv("IUSENTRA_LEGAL_AUTOFETCH_SOURCE_BUDGET"),
                    min(max(1, len(source_ids or [])), LEGAL_UPDATE_PROGRESSIVE_SOURCE_BUDGET),
                )
                os.environ.setdefault(
                    "IUSENTRA_CASSAZIONE_LATEST_MAX_ITEMS",
                    str(LEGAL_UPDATE_PROGRESSIVE_CASSAZIONE_MAX_ITEMS),
                )
                job_config = LegalUpdateJobConfig(
                    intelligence_db=str(
                        app.config.get("LEGAL_INTELLIGENCE_DB")
                        or "./intelligence/legal_intelligence.json"
                    ),
                    giurisprudenza_db=str(
                        app.config.get("GIURISPRUDENZA_DB")
                        or "./intelligence/giurisprudenza.json"
                    ),
                    ai_base_url=str(
                        app.config.get("LOCAL_AI_BASE_URL", "")
                        or app.config.get("PCT_LOCAL_AI_BASE_URL", "")
                    ),
                    ai_model=str(
                        app.config.get("LOCAL_AI_CHAT_MODEL", "")
                        or app.config.get("OLLAMA_MODEL", "mistral")
                    ),
                    export_json_enabled=_flag_enabled(app.config.get("LEGAL_UPDATES_EXPORT_JSON_ENABLED")),
                    mirror_giurisprudenza_json_enabled=_flag_enabled(
                        app.config.get("LEGAL_UPDATES_MIRROR_GIURISPRUDENZA_JSON_ENABLED")
                    ),
                )
                config = LegalAutoFetchConfig.from_job_config(
                    job_config,
                    source_budget=source_budget,
                    item_timeout_seconds=timeout_seconds,
                    publish_max_items=publish_max_items,
                    execute_due_sources=auto_publish,
                )
                report = run_legal_update_autofetch_tick(config, source_codes=source_ids)
                plan = report.get("plan") or {}
                execution = report.get("execution_report") or {}
                logger.info(
                    "[scheduler] Legal updates %s: %d fonti pianificate, %d job accodati, %d news autopubblicate, %d timeout per elemento",
                    label,
                    int(plan.get("selected_count") or 0),
                    len(report.get("enqueued_jobs") or []),
                    int((execution.get("autopublished") or {}).get("count") or 0),
                    int(execution.get("timeouts") or 0),
                )
                return report
            except Exception as e:
                logger.error("[scheduler] Legal updates %s fallito: %s", label, e)
                return {"ok": False, "error": str(e), "label": label}

    def _run_official_archives_sync(label: str):
        with app.app_context():
            official_db = _runtime_path(
                app,
                "LEX_OFFICIAL_DB",
                "PCT_LEX_OFFICIAL_DB",
                "/data/fonti_ufficiali/lex_sources.sqlite",
            )
            official_raw = _runtime_path(
                app,
                "LEX_OFFICIAL_RAW_DIR",
                "PCT_LEX_OFFICIAL_RAW_DIR",
                "/data/fonti_ufficiali/raw",
            )
            official_text = _runtime_path(
                app,
                "LEX_OFFICIAL_TEXT_DIR",
                "PCT_LEX_OFFICIAL_TEXT_DIR",
                "/data/fonti_ufficiali/text",
            )
            official_jsonl = _runtime_path(
                app,
                "LEX_OFFICIAL_JSONL",
                "PCT_LEX_OFFICIAL_JSONL",
                "/data/fonti_ufficiali/index/lex_sources_chunks.jsonl",
            )
            normativa_raw = _runtime_path(
                app,
                "NORMATTIVA_RAW_DIR",
                "PCT_NORMATTIVA_RAW_DIR",
                "/data/normativa/raw",
            )
            normativa_db = _runtime_path(
                app,
                "NORMATTIVA_DB",
                "PCT_NORMATTIVA_DB",
                "/data/normativa/normattiva.sqlite",
            )
            normativa_jsonl = _runtime_path(
                app,
                "NORMATTIVA_JSONL",
                "PCT_NORMATTIVA_JSONL",
                "/data/normativa/index/normattiva_chunks.jsonl",
            )
            normativa_report = _runtime_path(
                app,
                "NORMATTIVA_IMPORT_REPORT",
                "PCT_NORMATTIVA_IMPORT_REPORT",
                "/data/normativa/reports/normattiva_import_report.json",
            )
            normativa_manifest = _runtime_path(
                app,
                "NORMATTIVA_DOWNLOAD_MANIFEST",
                "PCT_NORMATTIVA_DOWNLOAD_MANIFEST",
                "/data/normativa/manifests/normattiva_download_manifest.json",
            )
            max_issues = _parse_positive_int(
                app.config.get("LEGAL_UPDATES_GAZZETTA_MAX_ISSUES")
                or os.getenv("IUSENTRA_GAZZETTA_MAX_ISSUES"),
                12,
            )
            timeout_seconds = _parse_positive_int(
                app.config.get("LEGAL_OFFICIAL_ARCHIVES_TIMEOUT_SECONDS")
                or os.getenv("IUSENTRA_LEGAL_OFFICIAL_ARCHIVES_TIMEOUT_SECONDS"),
                7200,
            )
            commands = [
                (
                    "gazzetta ufficiale",
                    [
                        sys.executable,
                        "tools/gazzetta_ufficiale_sync.py",
                        "--db",
                        official_db,
                        "--raw-dir",
                        official_raw,
                        "--text-dir",
                        official_text,
                        "--jsonl",
                        official_jsonl,
                        "--max-issues",
                        str(max_issues),
                        "--init-db",
                        "--export-jsonl",
                    ],
                ),
                (
                    "normattiva download core",
                    [
                        sys.executable,
                        "tools/normattiva_multi_sync.py",
                        "--download-core",
                        "--replace-existing",
                        "--out",
                        normativa_raw,
                        "--manifest",
                        normativa_manifest,
                        "--sleep",
                        str(os.getenv("IUSENTRA_NORMATTIVA_DOWNLOAD_SLEEP_SECONDS", "1.0")),
                    ],
                ),
                (
                    "normattiva import lex",
                    [
                        sys.executable,
                        "tools/normattiva_import.py",
                        "--raw-dir",
                        normativa_raw,
                        "--db",
                        normativa_db,
                        "--jsonl",
                        normativa_jsonl,
                        "--report",
                        normativa_report,
                    ],
                ),
            ]
            results = [
                _run_scheduler_command(f"{label}: {step_label}", command, timeout_seconds=timeout_seconds)
                for step_label, command in commands
            ]
            logger.info(
                "[scheduler] Archivi ufficiali %s: %d/%d passaggi completati",
                label,
                sum(1 for row in results if row.get("ok")),
                len(results),
            )
            return results

    @scheduler.scheduled_job(CronTrigger(hour=23, minute=0), id="legal_official_archives_daily")
    def _legal_official_archives_daily():
        _run_official_archives_sync("daily")

    @scheduler.scheduled_job(CronTrigger(hour=5, minute=45), id="legal_monitor_daily")
    def _legal_monitor_daily():
        _run_legal_monitor(
            [
                "normattiva",
                "gazzetta_ufficiale",
                "cnf",
                "cassazione",
                "corte_costituzionale",
                "giustizia_amministrativa",
                "eur_lex",
                "bancaditalia",
                "istat",
                "cassa_forense",
                "corte_conti",
                "ministero_lavoro",
                "anac",
                "cedu",
            ],
            "daily",
        )

    @scheduler.scheduled_job(CronTrigger(hour="6,12,18", minute=15), id="legal_monitor_pst")
    def _legal_monitor_pst():
        _run_legal_monitor(["pst_giustizia"], "pst")

    @scheduler.scheduled_job(CronTrigger(hour=23, minute=15), id="legal_updates_batch")
    def _legal_updates_batch():
        _run_legal_updates(list(LEGAL_UPDATE_PROGRESSIVE_STEP1_SOURCE_CODES), "fase9_fonti_verdi")

    # ---- Sync tabelle normative giornaliero (ogni giorno alle 04:30) ----
    # Sincronizza tutte le tabelle (tassi, indici ISTAT, Cassa Forense, soglie appalti, ecc.)
    @scheduler.scheduled_job(CronTrigger(hour=4, minute=30), id="sync_tabelle_normative_daily")
    def _sync_tabelle_normative():
        with app.app_context():
            try:
                from pct.legal_intelligence import GestioneLegalIntelligence

                gestore = GestioneLegalIntelligence(
                    db_path=app.config.get("LEGAL_INTELLIGENCE_DB", "./intelligence/legal_intelligence.json"),
                    normative_db_path=app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json"),
                )
                report = gestore.sync_normative_tables()
                updated = report.get("updated", 0)
                review = report.get("review_required", 0)
                errors = report.get("errors", 0)
                logger.info(
                    "[scheduler] Sync tabelle normative: %d aggiornate, %d da verificare, %d errori",
                    updated,
                    review,
                    errors,
                )
                if review:
                    logger.warning(
                        "[scheduler] %d tabelle normative richiedono verifica manuale "
                        "(la fonte e cambiata - accedere a /legal-intelligence per dettagli)",
                        review,
                    )
            except Exception as e:
                logger.error("[scheduler] Sync tabelle normative fallito: %s", e)

    def _calendar_sync_targets():
        if app.config.get("MULTI_TENANT"):
            try:
                from pct.tenant import GestioneTenant, StatoTenant

                tm = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                found = False
                for studio in tm.lista():
                    if studio.stato == StatoTenant.SOSPESO:
                        continue
                    paths = tm.percorsi_dati(studio.slug)
                    found = True
                    yield studio.slug, paths["AGENDA_DB"], paths["CALENDAR_SYNC_DB"]
                if found:
                    return
            except Exception as e:
                logger.warning("[scheduler] Calendar sync multi-tenant non disponibile: %s", e)
        yield "default", app.config["AGENDA_DB"], app.config.get("CALENDAR_SYNC_DB", "./agenda/calendar_sync.json")

    def _calendar_engine_targets():
        if app.config.get("MULTI_TENANT"):
            try:
                from pct.tenant import GestioneTenant, StatoTenant

                tm = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                found = False
                for studio in tm.lista():
                    if studio.stato == StatoTenant.SOSPESO:
                        continue
                    paths = tm.percorsi_dati(studio.slug)
                    found = True
                    yield {
                        "label": studio.slug,
                        "tenant_id": studio.slug,
                        "agenda_db": paths["AGENDA_DB"],
                        "scadenziario_db": paths["SCADENZIARIO_DB"],
                        "calendar_sync_db": paths["CALENDAR_SYNC_DB"],
                    }
                if found:
                    return
            except Exception as e:
                logger.warning("[scheduler] Calendar engine multi-tenant non disponibile: %s", e)
        yield {
            "label": "default",
            "tenant_id": "default",
            "agenda_db": app.config["AGENDA_DB"],
            "scadenziario_db": app.config["SCADENZIARIO_DB"],
            "calendar_sync_db": app.config.get("CALENDAR_SYNC_DB", "./agenda/calendar_sync.json"),
        }

    def _workspace_intelligence_targets():
        if app.config.get("MULTI_TENANT"):
            try:
                from pct.tenant import GestioneTenant, StatoTenant

                tm = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                found = False
                for studio in tm.lista():
                    if studio.stato == StatoTenant.SOSPESO:
                        continue
                    paths = tm.percorsi_dati(studio.slug)
                    found = True
                    yield {
                        "label": studio.slug,
                        "database": studio.database,
                        "agenda_db": paths["AGENDA_DB"],
                        "calendar_sync_db": paths["CALENDAR_SYNC_DB"],
                        "fascicoli_db": paths["FASCICOLI_DB"],
                        "fascicoli_docs": paths["FASCICOLI_DOCS"],
                        "fascicoli_arch": paths["FASCICOLI_ARCH"],
                        "scadenziario_db": paths["SCADENZIARIO_DB"],
                        "giurisprudenza_db": paths["GIURISPRUDENZA_DB"],
                        "studio_config_db": paths.get("CONFIG_STUDIO_DB", ""),
                        "snapshot_db": paths.get(
                            "WORKSPACE_INTELLIGENCE_DB",
                            str(Path(paths["GIURISPRUDENZA_DB"]).with_name("workspace_intelligence.json")),
                        ),
                        "local_ai_db": paths.get(
                            "LOCAL_AI_DB",
                            str(Path(paths["GIURISPRUDENZA_DB"]).with_name("local_ai.db")),
                        ),
                        "local_ai_models_dir": paths.get(
                            "LOCAL_AI_MODELS_DIR",
                            str(Path(paths["GIURISPRUDENZA_DB"]).with_name("models")),
                        ),
                    }
                if found:
                    return
            except Exception as e:
                logger.warning("[scheduler] Workspace intelligence multi-tenant non disponibile: %s", e)
        yield {
            "label": "default",
            "agenda_db": app.config["AGENDA_DB"],
            "calendar_sync_db": app.config.get("CALENDAR_SYNC_DB", "./agenda/calendar_sync.json"),
            "fascicoli_db": app.config["FASCICOLI_DB"],
            "fascicoli_docs": app.config["FASCICOLI_DOCS"],
            "fascicoli_arch": app.config["FASCICOLI_ARCH"],
            "scadenziario_db": app.config["SCADENZIARIO_DB"],
            "giurisprudenza_db": app.config.get("GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"),
            "studio_config_db": app.config.get("STUDIO_CONFIG") or app.config.get("CONFIG_STUDIO_DB", ""),
            "snapshot_db": app.config.get("WORKSPACE_INTELLIGENCE_DB", "./intelligence/workspace_intelligence.json"),
            "local_ai_db": app.config.get("LOCAL_AI_DB", "./intelligence/local_ai.db"),
            "local_ai_models_dir": app.config.get("LOCAL_AI_MODELS_DIR", "./intelligence/models"),
        }

    def _mailbox_sync_plan() -> tuple[list[tuple[str, dict]], str]:
        """Target dei presidi e motivo dell'eventuale assenza.

        I presidi PEC, relata, fascicoli, agenda e notifiche lavorano tutti su
        questa lista. Finche' era una sola generator muta, ogni suo fallimento
        (registro studi illeggibile, nessuno studio attivo) faceva girare i job
        a vuoto con esito «ok»: il guasto restava invisibile in console
        Pianificazioni. Qui il motivo viene restituito al chiamante, che lo
        trasforma in un esito fallito e quindi in una riga rossa tracciabile.
        """

        try:
            targets = list(_mailbox_sync_targets())
        except Exception as exc:  # pragma: no cover - difesa, la generator gia' cattura
            return [], f"target dei presidi non calcolabili: {exc}"
        if targets:
            return targets, ""
        if app.config.get("MULTI_TENANT"):
            return [], (
                "nessuno studio attivo o registro studi non leggibile: i presidi non hanno "
                "alcun archivio su cui lavorare"
            )
        return [], "nessun percorso dati disponibile per i presidi"

    def _presidio_senza_target(job_id: str, reason: str) -> dict:
        logger.error("[scheduler] %s non eseguito: %s", job_id, reason)
        return {
            "ok": False,
            "job": job_id,
            "error": reason,
            "targets": 0,
            "source_of_truth": "registro studi e percorsi dati del worker scheduler",
        }

    def _mailbox_sync_targets():
        if app.config.get("MULTI_TENANT"):
            try:
                from pct.tenant import GestioneTenant, StatoTenant

                tm = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                found = False
                for studio in tm.lista():
                    if studio.stato == StatoTenant.SOSPESO:
                        continue
                    paths = dict(tm.percorsi_dati(studio.slug))
                    paths["_TENANT_DATABASE_CONFIG"] = studio.database
                    paths["_TENANT_PRESIDIO_ID"] = str(
                        getattr(studio, "slug", "")
                        or getattr(studio, "storage_key", "")
                        or getattr(studio, "id", "")
                        or "tenant"
                    )
                    paths["_TENANT_NOTIFICATION_ID"] = str(
                        getattr(studio, "id", "") or studio.slug or "tenant"
                    )
                    found = True
                    yield str(studio.slug or "tenant"), paths
                if found:
                    return
                logger.info("[scheduler] Mailbox sync multi-tenant: nessuno studio attivo, sync globale non eseguita.")
                return
            except Exception as e:
                logger.warning("[scheduler] Mailbox sync multi-tenant non disponibile: %s", e)
                return
        yield "default", {
            "EMAIL_CASELLA_DB": app.config.get("EMAIL_CASELLA_DB", "./email/casella.json"),
            "EMAIL_ORDINARIA_DB": app.config.get("EMAIL_ORDINARIA_DB", "./email/ordinaria.json"),
            "STUDIO_CONFIG": app.config.get("STUDIO_CONFIG") or app.config.get("CONFIG_STUDIO_DB", "./config/studio.json"),
            "CONFIG_STUDIO_DB": app.config.get("CONFIG_STUDIO_DB", app.config.get("STUDIO_CONFIG", "./config/studio.json")),
            "FASCICOLI_DB": app.config.get("FASCICOLI_DB", "./fascicoli/fascicoli.json"),
            "FASCICOLI_DOCS": app.config.get("FASCICOLI_DOCS", "./fascicoli/documenti"),
            "FASCICOLI_ARCH": app.config.get("FASCICOLI_ARCH", "./fascicoli/archivio"),
            "AUTH_DB": app.config.get("AUTH_DB", "./auth/utenti.json"),
            "AUDIT_DB": app.config.get("AUDIT_DB", "./audit/audit.json"),
            "MESSAGGI_DB": app.config.get("MESSAGGI_DB", "./messaggi/messaggi.json"),
            "AGENDA_DB": app.config.get("AGENDA_DB", "./agenda/appuntamenti.json"),
            "SCADENZIARIO_DB": app.config.get("SCADENZIARIO_DB", "./scadenziario/scadenze.json"),
            "NOTIFICATIONS_DB": app.config.get("NOTIFICATIONS_DB", "./notifications/notifications.db"),
            "STUDIO_DB": app.config.get("STUDIO_DB", "./studio.db"),
            "_TENANT_DATABASE_CONFIG": app.config.get("TENANT_DATABASE_CONFIG"),
            "_TENANT_PRESIDIO_ID": "default",
            "_TENANT_NOTIFICATION_ID": "default",
        }

    @scheduler.scheduled_job(CronTrigger(minute=12), id="calendar_sync_hourly")
    def _calendar_sync_hourly():
        with app.app_context():
            try:
                from pct.agenda import Agenda
                from pct.calendar_sync import GestioneCalendarSync

                processed_targets = 0
                synced_profiles = 0
                failed_profiles = 0
                for label, agenda_db, sync_db in _calendar_sync_targets():
                    gestore = GestioneCalendarSync(db_path=sync_db)
                    if not gestore.list_profiles():
                        continue
                    report = gestore.sync_enabled_profiles(agenda=Agenda(db_path=agenda_db))
                    processed_targets += 1
                    synced_profiles += report.get("successful", 0)
                    failed_profiles += report.get("failed", 0)
                    logger.info(
                        "[scheduler] Calendar sync %s: %d ok / %d fallite",
                        label,
                        report.get("successful", 0),
                        report.get("failed", 0),
                    )
                if processed_targets:
                    logger.info(
                        "[scheduler] Calendar sync completato: %d profili ok / %d falliti",
                        synced_profiles,
                        failed_profiles,
                    )
            except Exception as e:
                logger.error("[scheduler] Calendar sync fallito: %s", e)

    @scheduler.scheduled_job(CronTrigger(minute="*/10"), id="calendar_sync_engine_polling")
    def _calendar_sync_engine_polling():
        with app.app_context():
            try:
                from pct.calendar_sync_engine import CalendarSyncEngine

                processed_targets = 0
                processed_accounts = 0
                for target in _calendar_engine_targets():
                    engine = CalendarSyncEngine.from_paths(
                        agenda_db=target["agenda_db"],
                        scadenziario_db=target["scadenziario_db"],
                        sync_db=target["calendar_sync_db"],
                        tenant_id=target["tenant_id"],
                    )
                    accounts = engine.repository.list_accounts(target["tenant_id"])
                    if not accounts:
                        continue
                    processed_targets += 1
                    for account in accounts:
                        provider = str(account.get("provider") or "")
                        if provider in {"webcal", "ics"}:
                            continue
                        try:
                            report = engine.sync_account(str(account.get("id") or ""))
                            processed_accounts += 1
                            logger.info(
                                "[scheduler] Calendar engine %s/%s: pull=%d push=%d conflitti=%d",
                                target["label"],
                                provider,
                                report.get("pulled", 0),
                                report.get("pushed", 0),
                                report.get("conflicts", 0),
                            )
                        except Exception as account_error:
                            logger.warning(
                                "[scheduler] Calendar engine %s/%s non completato: %s",
                                target["label"],
                                provider,
                                account_error,
                            )
                if processed_targets:
                    logger.info("[scheduler] Calendar engine completato per %d account", processed_accounts)
            except Exception as e:
                logger.error("[scheduler] Calendar engine fallito: %s", e)

    @scheduler.scheduled_job(CronTrigger(minute=42), id="calendar_sync_engine_webcal")
    def _calendar_sync_engine_webcal():
        with app.app_context():
            try:
                from pct.calendar_sync_engine import CalendarSyncEngine

                processed_accounts = 0
                for target in _calendar_engine_targets():
                    engine = CalendarSyncEngine.from_paths(
                        agenda_db=target["agenda_db"],
                        scadenziario_db=target["scadenziario_db"],
                        sync_db=target["calendar_sync_db"],
                        tenant_id=target["tenant_id"],
                    )
                    for account in engine.repository.list_accounts(target["tenant_id"]):
                        if str(account.get("provider") or "") not in {"webcal", "ics"}:
                            continue
                        try:
                            engine.sync_account(str(account.get("id") or ""))
                            processed_accounts += 1
                        except Exception as account_error:
                            logger.warning("[scheduler] Calendar WebCal %s non completato: %s", target["label"], account_error)
                if processed_accounts:
                    logger.info("[scheduler] Calendar WebCal engine completato per %d account", processed_accounts)
            except Exception as e:
                logger.error("[scheduler] Calendar WebCal engine fallito: %s", e)

    @scheduler.scheduled_job(CronTrigger(minute="*/5"), id="calendar_sync_engine_retry")
    def _calendar_sync_engine_retry():
        with app.app_context():
            try:
                from pct.calendar_sync_engine import CalendarSyncEngine

                processed = 0
                targets = 0
                target_reports: list[dict[str, object]] = []
                for target in _calendar_engine_targets():
                    engine = CalendarSyncEngine.from_paths(
                        agenda_db=target["agenda_db"],
                        scadenziario_db=target["scadenziario_db"],
                        sync_db=target["calendar_sync_db"],
                        tenant_id=target["tenant_id"],
                    )
                    report = engine.sync_due_jobs()
                    processed += _as_int(report.get("processed"))
                    targets += 1
                    target_reports.append(
                        {
                            "tenant": str(target.get("label") or target.get("tenant_id") or ""),
                            "processed": _as_int(report.get("processed")),
                            "failed": _as_int(report.get("failed")),
                            "report": report,
                        }
                    )
                if processed:
                    logger.info("[scheduler] Calendar retry completato: %d job", processed)
                failed = sum(_as_int(item.get("failed")) for item in target_reports)
                return {
                    "ok": failed == 0,
                    "job": "calendar_sync_engine_retry",
                    "scan_mode": "pending_jobs_only",
                    "source_of_truth": "calendar_sync_engine repository",
                    "targets": targets,
                    "totals": {"targets": targets, "processed": processed, "failed": failed, "errors": failed},
                    "tenants": target_reports,
                }
            except Exception as e:
                logger.error("[scheduler] Calendar retry fallito: %s", e)
                return {"ok": False, "job": "calendar_sync_engine_retry", "error": str(e)}

    @scheduler.scheduled_job(
        CronTrigger(minute="*/15"),
        id="mailbox_sync_runtime",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )
    def _mailbox_sync_runtime():
        with app.app_context():
            try:
                from web.services.mailbox_sync_runtime import sync_mailboxes_for_paths

                automatic_limit = min(
                    _parse_positive_int(
                        app.config.get("IUSENTRA_MAILBOX_SYNC_AUTOMATIC_LIMIT")
                        or os.getenv("IUSENTRA_MAILBOX_SYNC_AUTOMATIC_LIMIT"),
                        25,
                    ),
                    100,
                )
                targets, no_target_reason = _mailbox_sync_plan()
                if not targets:
                    return _presidio_senza_target("mailbox_sync_runtime", no_target_reason)
                processed_targets = 0
                tenant_reports: list[dict[str, object]] = []
                totals = {
                    "targets": 0,
                    "channels": 0,
                    "skipped": 0,
                    "nuove": 0,
                    "pst_trovate": 0,
                    "allegati_salvati": 0,
                    "warnings": 0,
                    "errors": 0,
                }
                for label, paths in targets:
                    report = sync_mailboxes_for_paths(
                        paths,
                        tenant_label=label,
                        cooldown_seconds=180.0,
                        limite=automatic_limit,
                        incremental_only=True,
                    )
                    processed_targets += 1
                    totals["targets"] += 1
                    pec = report.get("pec") or {}
                    ordinary = report.get("ordinary") or {}
                    tenant_item: dict[str, object] = {"tenant": label, "channels": {}}
                    for channel_name, channel_report in (("pec", pec), ("ordinary", ordinary)):
                        channel = channel_report if isinstance(channel_report, dict) else {}
                        result = channel.get("result") if isinstance(channel.get("result"), dict) else {}
                        errore = str(result.get("errore") or result.get("sync_errore") or "").strip()
                        warning = bool(result.get("warning")) or bool(errore)
                        channel_payload = {
                            "ok": channel.get("ok"),
                            "skipped": bool(channel.get("skipped")),
                            "reason": str(channel.get("reason") or ""),
                            "nuove": _as_int(result.get("nuove")),
                            "pst_trovate": _as_int(result.get("pst_trovate")),
                            "allegati_salvati": _as_int(result.get("allegati_salvati")),
                            "warning": warning,
                            "errore": errore,
                        }
                        tenant_item["channels"][channel_name] = channel_payload
                        totals["channels"] += 1
                        totals["nuove"] += int(channel_payload["nuove"])
                        totals["pst_trovate"] += int(channel_payload["pst_trovate"])
                        totals["allegati_salvati"] += int(channel_payload["allegati_salvati"])
                        if channel_payload["skipped"]:
                            totals["skipped"] += 1
                        if warning:
                            totals["warnings"] += 1
                        if channel.get("ok") is False and not str(channel_payload["reason"]).strip() and "non configurato" not in errore.lower():
                            totals["errors"] += 1
                    tenant_reports.append(tenant_item)
                    logger.info(
                        "[scheduler] Mailbox sync %s: pec=%s/%s ordinary=%s/%s",
                        label,
                        "skipped" if pec.get("skipped") else "run",
                        pec.get("reason") or "ok",
                        "skipped" if ordinary.get("skipped") else "run",
                        ordinary.get("reason") or "ok",
                    )
                if processed_targets:
                    logger.info("[scheduler] Mailbox sync completata per %d target", processed_targets)
                return {
                    "ok": totals["errors"] == 0,
                    "job": "mailbox_sync_runtime",
                    "scan_mode": "incremental_runtime_guard",
                    "source_of_truth": "mailbox UID/Message-ID tenant-aware",
                    "automatic_limit": automatic_limit,
                    "incremental_only": True,
                    "targets": processed_targets,
                    "totals": totals,
                    "tenants": tenant_reports,
                }
            except Exception as e:
                logger.error("[scheduler] Mailbox sync fallita: %s", e)
                return {"ok": False, "job": "mailbox_sync_runtime", "error": str(e)}

    @scheduler.scheduled_job(
        CronTrigger(minute="*/5"),
        id="pec_audit_pipeline_workers",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=240,
    )
    def _pec_audit_pipeline_workers():
        with app.app_context():
            try:
                from web.services.pec_pipeline_runtime import (
                    acquire_local_pec_for_paths,
                    run_workers_for_paths,
                )

                try:
                    auto_batch = int(os.environ.get("IUSENTRA_PEC_AUTO_ACQUIRE_BATCH", "5") or 5)
                except (TypeError, ValueError):
                    auto_batch = 5
                try:
                    worker_jobs = int(os.environ.get("IUSENTRA_PEC_WORKER_JOBS_PER_TICK", "20") or 20)
                except (TypeError, ValueError):
                    worker_jobs = 20
                try:
                    document_presidio_limit = int(os.environ.get("IUSENTRA_PEC_DOCUMENT_PRESIDIO_LIMIT", "10") or 10)
                except (TypeError, ValueError):
                    document_presidio_limit = 10
                targets, no_target_reason = _mailbox_sync_plan()
                if not targets:
                    return _presidio_senza_target("pec_audit_pipeline_workers", no_target_reason)
                processed_targets = 0
                processed_jobs = 0
                tenant_reports: list[dict[str, object]] = []
                totals = {
                    "targets": 0,
                    "archive_seen": 0,
                    "scanned": 0,
                    "relevant": 0,
                    "ingested": 0,
                    "duplicates": 0,
                    "skipped_presided": 0,
                    "missing_mime": 0,
                    "acquire_errors": 0,
                    "processed_jobs": 0,
                    "failed_jobs": 0,
                    "document_errors": 0,
                    "notification_errors": 0,
                    "errors": 0,
                }
                scan_modes: set[str] = set()
                for label, paths in targets:
                    # Prima l'acquisizione automatica delle PEC archiviate non ancora
                    # presidiate (a budget, 0 = disattivata), poi i worker che lavorano
                    # classificazione, scadenze automatiche e collegamento fascicoli.
                    # Budget prudenti: l'OCR degli allegati gira in questo processo e
                    # un arretrato grande deve scalare in più giri senza saturare RAM.
                    acquired: dict[str, object] = {
                        "scan_mode": "disabled",
                        "skipped": True,
                        "reason": "acquisizione automatica disattivata",
                    }
                    if auto_batch > 0:
                        logger.info("[scheduler] Presidio PEC %s: acquisizione batch=%d", label, auto_batch)
                        acquired = acquire_local_pec_for_paths(paths, tenant_label=label, batch_size=auto_batch)
                        scan_modes.add(str(acquired.get("scan_mode") or "unknown"))
                        totals["archive_seen"] += _as_int(acquired.get("archive_seen"))
                        totals["scanned"] += _as_int(acquired.get("scanned"))
                        totals["relevant"] += _as_int(acquired.get("relevant"))
                        totals["ingested"] += _as_int(acquired.get("ingested"))
                        totals["duplicates"] += _as_int(acquired.get("duplicates"))
                        totals["skipped_presided"] += _as_int(acquired.get("skipped_presided"))
                        totals["missing_mime"] += _as_int(acquired.get("missing_mime"))
                        totals["acquire_errors"] += _as_int(acquired.get("errors"))
                        if acquired.get("ingested") or acquired.get("missing_mime") or acquired.get("errors"):
                            logger.info(
                                "[scheduler] Presidio PEC %s: %d acquisite, %d duplicate, %d senza MIME, %d errori",
                                label,
                                acquired.get("ingested", 0),
                                acquired.get("duplicates", 0),
                                acquired.get("missing_mime", 0),
                                acquired.get("errors", 0),
                            )
                    logger.info(
                        "[scheduler] Presidio PEC %s: worker limit=%d, documenti Lex limit=%d",
                        label,
                        max(1, worker_jobs),
                        max(0, document_presidio_limit),
                    )
                    report = run_workers_for_paths(
                        paths,
                        tenant_label=label,
                        limit=max(1, worker_jobs),
                        document_presidio_limit=max(0, document_presidio_limit),
                    )
                    processed_targets += 1
                    processed_jobs += int(report.get("processed") or 0)
                    totals["targets"] += 1
                    totals["processed_jobs"] += _as_int(report.get("processed"))
                    totals["failed_jobs"] += _as_int(report.get("failed"))
                    document_presidio = report.get("document_presidio") if isinstance(report.get("document_presidio"), dict) else {}
                    document_errors = _as_int(document_presidio.get("errors"))
                    if isinstance(document_presidio.get("errors"), list):
                        document_errors = len(document_presidio.get("errors") or [])
                    document_retries = _as_int(document_presidio.get("retry_locked_documents"))
                    if isinstance(document_presidio.get("transient_errors"), list):
                        document_retries = max(document_retries, len(document_presidio.get("transient_errors") or []))
                    totals["document_errors"] += document_errors
                    notifications = report.get("auto_deadline_notifications") if isinstance(report.get("auto_deadline_notifications"), dict) else {}
                    processed_count = _as_int(report.get("processed"))
                    failed_count = _as_int(report.get("failed"))
                    checked_documents = _as_int(document_presidio.get("checked_documents"))
                    checked_fascicoli = _as_int(document_presidio.get("checked_fascicoli"))
                    notification_created = _as_int(notifications.get("created"))
                    notification_failed = _as_int(notifications.get("errors"))
                    totals["notification_errors"] += _as_int(notifications.get("errors"))
                    tenant_reports.append(
                        {
                            "tenant": label,
                            "acquired": acquired,
                            "workers": {
                                "processed": processed_count,
                                "failed": failed_count,
                                "document_presidio": document_presidio,
                                "auto_deadline_notifications": notifications,
                            },
                        }
                    )
                    logger.info(
                        "[scheduler] Pipeline PEC %s: %d job completati, %d errori, documenti=%s/%s, rinviati=%d, errori documenti=%d, notifiche=%s/%s",
                        label,
                        processed_count,
                        failed_count,
                        checked_documents,
                        checked_fascicoli,
                        document_retries,
                        document_errors,
                        notification_created,
                        notification_failed,
                    )
                if processed_targets:
                    logger.info("[scheduler] Pipeline PEC controllata per %d target; job=%d", processed_targets, processed_jobs)
                totals["errors"] = (
                    int(totals["acquire_errors"])
                    + int(totals["failed_jobs"])
                    + int(totals["document_errors"])
                    + int(totals["notification_errors"])
                )
                ordered_modes = sorted(mode for mode in scan_modes if mode)
                return {
                    "ok": totals["errors"] == 0,
                    "job": "pec_audit_pipeline_workers",
                    "scan_mode": ordered_modes[0] if len(ordered_modes) == 1 else ("mixed:" + ",".join(ordered_modes) if ordered_modes else "workers_only"),
                    "source_of_truth": "pec_audit.sqlite + email tenant-aware",
                    "batch_size": max(0, auto_batch),
                    "worker_limit": max(1, worker_jobs),
                    "document_presidio_limit": max(0, document_presidio_limit),
                    "targets": processed_targets,
                    "processed_jobs": processed_jobs,
                    "totals": totals,
                    "tenants": tenant_reports,
                }
            except Exception as e:
                logger.error("[scheduler] Pipeline PEC fallita: %s", e)
                return {"ok": False, "job": "pec_audit_pipeline_workers", "error": str(e)}

    @scheduler.scheduled_job(
        CronTrigger(minute="2-57/5"),
        id="agenda_scadenziario_notifications",
        max_instances=1,
        coalesce=True,
    )
    def _agenda_scadenziario_notifications():
        with app.app_context():
            try:
                from web.services.notifications_runtime import (
                    materialize_agenda_scadenziario_notifications_for_paths,
                )

                targets, no_target_reason = _mailbox_sync_plan()
                if not targets:
                    return _presidio_senza_target("agenda_scadenziario_notifications", no_target_reason)
                tenant_reports: list[dict[str, object]] = []
                errors = 0
                recipients = 0
                items = 0
                for label, paths in targets:
                    report = materialize_agenda_scadenziario_notifications_for_paths(
                        paths,
                        tenant_label=label,
                        tenant_id=str(paths.get("_TENANT_NOTIFICATION_ID") or label),
                        database=paths.get("_TENANT_DATABASE_CONFIG"),
                    )
                    tenant_reports.append(report)
                    errors += _as_int(report.get("errors"))
                    recipients += _as_int(report.get("recipients"))
                    items += _as_int(report.get("items"))
                return {
                    "ok": errors == 0,
                    "job": "agenda_scadenziario_notifications",
                    "source_of_truth": "agenda/scadenziario e notification repository tenant-aware",
                    "recipients": recipients,
                    "items": items,
                    "errors": errors,
                    "tenants": tenant_reports,
                }
            except Exception as exc:
                logger.error("[scheduler] Materializzazione notifiche Agenda/Scadenziario fallita: %s", exc)
                return {
                    "ok": False,
                    "job": "agenda_scadenziario_notifications",
                    "error": str(exc),
                }

    @scheduler.scheduled_job(
        CronTrigger(minute="4-59/15"),
        id="legal_notification_relata_presidio",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    def _legal_notification_relata_presidio():
        with app.app_context():
            try:
                from web.services.notifications_runtime import (
                    materialize_notification_relata_presidio_for_paths,
                )

                targets, no_target_reason = _mailbox_sync_plan()
                if not targets:
                    return _presidio_senza_target("legal_notification_relata_presidio", no_target_reason)
                tenant_reports: list[dict[str, object]] = []
                errors = 0
                recipients = 0
                items = 0
                to_notify = 0
                scanned = 0
                for label, paths in targets:
                    report = materialize_notification_relata_presidio_for_paths(
                        paths,
                        tenant_label=label,
                        tenant_id=str(paths.get("_TENANT_NOTIFICATION_ID") or label),
                        presidio_tenant_id=str(paths.get("_TENANT_PRESIDIO_ID") or label),
                        database=paths.get("_TENANT_DATABASE_CONFIG"),
                    )
                    tenant_reports.append(report)
                    errors += _as_int(report.get("errors"))
                    recipients += _as_int(report.get("recipients"))
                    items += _as_int(report.get("items"))
                    to_notify += _as_int(report.get("to_notify"))
                    scanned += _as_int(report.get("scanned"))
                return {
                    "ok": errors == 0,
                    "job": "legal_notification_relata_presidio",
                    "source_of_truth": "studio.db fascicoli.documenti_json e notification repository tenant-aware",
                    "scanned": scanned,
                    "items": items,
                    "to_notify": to_notify,
                    "recipients": recipients,
                    "errors": errors,
                    "tenants": tenant_reports,
                }
            except Exception as exc:
                logger.error("[scheduler] Presidio relata/notifiche fascicoli fallito: %s", exc)
                return {
                    "ok": False,
                    "job": "legal_notification_relata_presidio",
                    "error": str(exc),
                }

    @scheduler.scheduled_job(
        CronTrigger(minute="13-58/15"),
        id="fascicoli_document_economic_presidio",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    def _fascicoli_document_economic_presidio():
        with app.app_context():
            try:
                from web.services.fascicoli_presidi_runtime import (
                    run_fascicoli_document_economic_presidio_for_all_tenants,
                )

                limit = _parse_positive_int(
                    app.config.get("IUSENTRA_FASCICOLI_PRESIDIO_LIMIT")
                    or os.getenv("IUSENTRA_FASCICOLI_PRESIDIO_LIMIT"),
                    25,
                )
                report = run_fascicoli_document_economic_presidio_for_all_tenants(
                    app,
                    limit_per_tenant=limit,
                    actor="IUSENTRA scheduler",
                )
                totals = report.get("totals") or {}
                logger.info(
                    "[scheduler] Presidio fascicoli/economia: %d contributi controllati, "
                    "%d contributi consolidati, %d analisi documentali, %d stati definiti, %d proforme create",
                    int(totals.get("contributiCheckedCount") or 0),
                    int(totals.get("contributiUpdatedCount") or 0),
                    int(totals.get("documentAnalysisUpdatedCount") or 0),
                    int(totals.get("statusDefinedUpdatedCount") or 0),
                    int(totals.get("createdCount") or 0),
                )
                return report
            except Exception as e:
                logger.error("[scheduler] Presidio fascicoli/economia fallito: %s", e)
                return {"ok": False, "job": "fascicoli_document_economic_presidio", "error": str(e)}

    def _daily_plan_enabled() -> bool:
        try:
            from web.services.feature_flags import is_feature_enabled

            return bool(is_feature_enabled("lex.dailyPlan.enabled", app.config))
        except Exception:
            return False

    def _daily_plan_scheduled_runs_enabled() -> bool:
        try:
            from web.services.feature_flags import is_feature_enabled

            return bool(is_feature_enabled("lex.dailyPlan.scheduledRuns", app.config))
        except Exception:
            return False

    def _daily_plan_regular_recovery_due(now: datetime | None = None) -> bool:
        current = now or _scheduler_rome_now(app)
        return (current.hour, current.minute) >= _DAILY_PLAN_RECOVERY_START

    def _daily_plan_registry_enabled() -> bool:
        try:
            job = registry_repo.get_job("studio_daily_operational_plan") if registry_repo else None
        except Exception:
            job = None
        if job is None:
            return True
        return str(job.get("enabled", True)).strip().lower() not in {
            "0", "false", "off", "no", ""
        }

    def _daily_plan_registry_recovery_enabled() -> bool:
        try:
            job = registry_repo.get_job("studio_daily_operational_plan") if registry_repo else None
        except Exception:
            job = None
        return daily_plan_startup_recovery_allowed(_scheduler_rome_now(app), job)

    def _daily_plan_startup_recovery():
        with app.app_context():
            if not (
                _daily_plan_enabled()
                and _daily_plan_scheduled_runs_enabled()
                and _daily_plan_registry_recovery_enabled()
            ):
                return {
                    "ok": True,
                    "job": "daily_plan_startup_recovery",
                    "skipped": "automatic_generation_not_enabled",
                }
            if not daily_plan_full_lock.acquire(blocking=False):
                return {
                    "ok": True,
                    "job": "daily_plan_startup_recovery",
                    "skipped": "daily_plan_generation_in_progress",
                }
            try:
                from web.services.daily_plan_runtime import run_daily_plan_for_all_tenants

                return run_daily_plan_for_all_tenants(
                    app,
                    mode="incremental",
                    include_dirty=True,
                    ensure_today_snapshots=True,
                )
            except Exception as exc:
                logger.error("[scheduler] Recupero automatico piano del giorno fallito: %s", exc)
                return {"ok": False, "job": "daily_plan_startup_recovery", "error": str(exc)}
            finally:
                daily_plan_full_lock.release()

    @scheduler.scheduled_job(
        CronTrigger(hour=5, minute=30, timezone="Europe/Rome"),
        id="studio_daily_operational_plan",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    def _studio_daily_operational_plan():
        """Piano del giorno (Lex Oggi): riconciliazione completa mattutina.

        Un piano per ogni utente attivo di ogni studio. Nessuna scrittura
        applicativa automatica: produce solo la proiezione materializzata.
        """
        with app.app_context():
            if not (
                _daily_plan_enabled()
                and _daily_plan_scheduled_runs_enabled()
                and _daily_plan_registry_enabled()
            ):
                return {"ok": True, "job": "studio_daily_operational_plan", "skipped": "feature_flag_disattivo"}
            if not daily_plan_full_lock.acquire(blocking=False):
                return {
                    "ok": True,
                    "job": "studio_daily_operational_plan",
                    "skipped": "daily_plan_generation_in_progress",
                }
            try:
                from web.services.daily_plan_runtime import run_daily_plan_for_all_tenants

                report = run_daily_plan_for_all_tenants(
                    app,
                    mode="full",
                    scheduled_daily=True,
                )
                totals = report.get("totals") or {}
                logger.info(
                    "[scheduler] Piano del giorno completo: %d studi elaborati, %d attività, %d errori",
                    int(totals.get("tenants") or 0),
                    int(totals.get("items_written") or 0),
                    int(totals.get("errors") or 0),
                )
                return report
            except Exception as e:
                logger.error("[scheduler] Piano del giorno completo fallito: %s", e)
                return {"ok": False, "job": "studio_daily_operational_plan", "error": str(e)}
            finally:
                daily_plan_full_lock.release()

    @scheduler.scheduled_job(
        CronTrigger(minute="7-59/15"),
        id="daily_plan_incremental_refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    def _daily_plan_incremental_refresh():
        """Consuma le richieste manuali e, se abilitato, le entita' cambiate."""
        with app.app_context():
            if not _daily_plan_enabled():
                return {"ok": True, "job": "daily_plan_incremental_refresh", "skipped": "feature_flag_disattivo"}
            try:
                from web.services.daily_plan_runtime import run_daily_plan_for_all_tenants

                scheduled_runs_enabled = _daily_plan_scheduled_runs_enabled()
                ensure_today_snapshots = (
                    scheduled_runs_enabled
                    and _daily_plan_regular_recovery_due()
                    and _daily_plan_registry_recovery_enabled()
                )
                if ensure_today_snapshots and not daily_plan_full_lock.acquire(blocking=False):
                    return {
                        "ok": True,
                        "job": "daily_plan_incremental_refresh",
                        "skipped": "daily_plan_generation_in_progress",
                    }
                try:
                    report = run_daily_plan_for_all_tenants(
                        app,
                        mode="incremental",
                        include_dirty=scheduled_runs_enabled,
                        ensure_today_snapshots=ensure_today_snapshots,
                    )
                finally:
                    if ensure_today_snapshots:
                        daily_plan_full_lock.release()
                totals = report.get("totals") or {}
                if int(totals.get("tenants") or 0) or int(totals.get("errors") or 0):
                    logger.info(
                        "[scheduler] Piano del giorno incrementale: %d studi, %d saltati, %d errori",
                        int(totals.get("tenants") or 0),
                        int(totals.get("skipped") or 0),
                        int(totals.get("errors") or 0),
                    )
                return report
            except Exception as e:
                logger.error("[scheduler] Piano del giorno incrementale fallito: %s", e)
                return {"ok": False, "job": "daily_plan_incremental_refresh", "error": str(e)}

    @scheduler.scheduled_job(CronTrigger(hour=8, minute=0, timezone="Europe/Rome"), id="pec_audit_digest_daily")
    def _pec_audit_digest_daily():
        with app.app_context():
            try:
                from web.services.pec_pipeline_runtime import build_digest_for_paths

                processed_targets = 0
                for label, paths in _mailbox_sync_targets():
                    digest = build_digest_for_paths(paths, tenant_label=label)
                    processed_targets += 1
                    logger.info(
                        "[scheduler] Digest PEC %s: %d nuovi, %d anomalie",
                        label,
                        digest.get("new_messages", 0),
                        len(digest.get("anomalies") or []),
                    )
                if processed_targets:
                    logger.info("[scheduler] Digest PEC creato per %d target", processed_targets)
            except Exception as e:
                logger.error("[scheduler] Digest PEC fallito: %s", e)

    @scheduler.scheduled_job(CronTrigger(minute="*/20"), id="workspace_intelligence_snapshot")
    def _workspace_intelligence_snapshot():
        with app.app_context():
            try:
                from pct.agenda import Agenda
                from pct.calendar_sync import GestioneCalendarSync
                from pct.config_studio import GestioneConfigStudio
                from pct.fascicoli import GestioneFascicoli
                from pct.giurisprudenza import GestioneGiurisprudenza
                from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
                from pct.scadenziario import GestioneScadenziario, regola_patrono_studio
                from pct.workspace_intelligente import WorkspaceIntelligenteService

                processed_targets = 0
                for target in _workspace_intelligence_targets():
                    if not os.path.exists(target["fascicoli_db"]):
                        continue
                    service = WorkspaceIntelligenteService(
                        agenda=Agenda(db_path=target["agenda_db"]),
                        scadenziario=GestioneScadenziario(db_path=target["scadenziario_db"]),
                        fascicoli=GestioneFascicoli(
                            db_path=target["fascicoli_db"],
                            documents_dir=target["fascicoli_docs"],
                            archive_dir=target["fascicoli_arch"],
                        ),
                        calendar_sync=GestioneCalendarSync(db_path=target["calendar_sync_db"]),
                        giurisprudenza=GestioneGiurisprudenza(db_path=target["giurisprudenza_db"]),
                        snapshot_path=target["snapshot_db"],
                        postgres_dsn=resolve_runtime_postgres_dsn(database=target.get("database")),
                    )

                    try:
                        config_path = target.get("studio_config_db") or app.config.get("STUDIO_CONFIG") or app.config.get("CONFIG_STUDIO_DB", "")
                        if config_path and os.path.exists(config_path):
                            studio_cfg = GestioneConfigStudio(config_path=config_path).config.studio
                            service.studio_patron_rule = regola_patrono_studio(
                                "default-studio",
                                str(getattr(studio_cfg, "patron_name", "") or "").strip(),
                                int(getattr(studio_cfg, "patron_day", 0) or 0),
                                int(getattr(studio_cfg, "patron_month", 0) or 0),
                            )
                    except Exception as config_error:
                        logger.debug(
                            "[scheduler] Workspace intelligence %s: patrono studio non disponibile (%s)",
                            target["label"],
                            config_error,
                        )

                    service.save_snapshot(target["snapshot_db"])
                    processed_targets += 1
                    logger.info(
                        "[scheduler] Workspace intelligence %s: snapshot aggiornato con conteggi redatti",
                        target["label"],
                    )
                if processed_targets:
                    logger.info("[scheduler] Workspace intelligence aggiornato per %d target", processed_targets)
            except Exception as e:
                logger.error("[scheduler] Workspace intelligence fallito: %s", e)

    @scheduler.scheduled_job(CronTrigger(minute="*/30"), id="local_ai_maintenance")
    def _local_ai_maintenance():
        with app.app_context():
            try:
                if is_managed_cloud_runtime():
                    logger.info(
                        "[scheduler] Local AI maintenance disabilitata su runtime cloud-hosted: AI delegata al companion locale del cliente."
                    )
                    return {
                        "ok": True,
                        "job": "local_ai_maintenance",
                        "status": "disabled_cloud_hosted",
                        "scan_mode": "not_applicable",
                        "totals": {"targets": 0, "indexed": 0, "embedded": 0, "errors": 0},
                    }
                maintenance_enabled = _flag_enabled(
                    app.config.get("IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED")
                    or app.config.get("PCT_LOCAL_AI_MAINTENANCE_ENABLED")
                    or os.getenv("IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED")
                    or os.getenv("PCT_LOCAL_AI_MAINTENANCE_ENABLED")
                )
                if not maintenance_enabled:
                    logger.info(
                        "[scheduler] Local AI maintenance automatica disabilitata: impostare IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED=1 per eseguirla sul server."
                    )
                    return {
                        "ok": True,
                        "job": "local_ai_maintenance",
                        "status": "disabled_by_default",
                        "scan_mode": "manual_or_explicit_opt_in",
                        "totals": {"targets": 0, "indexed": 0, "embedded": 0, "errors": 0},
                    }

                from pct.fascicoli import GestioneFascicoli
                from pct.local_ai import LocalAIService

                processed_targets = 0
                tenant_reports: list[dict[str, object]] = []
                totals = {"targets": 0, "indexed": 0, "embedded": 0, "errors": 0}
                for target in _workspace_intelligence_targets():
                    service = LocalAIService(
                        db_path=target["local_ai_db"],
                        policy_path=app.config.get("LOCAL_AI_POLICY", "./config/ai-policy.json"),
                        config_path=target.get("studio_config_db") or app.config.get("STUDIO_CONFIG", "./config/studio.json"),
                        app_root=str(Path(__file__).resolve().parents[1]),
                        models_path=target["local_ai_models_dir"],
                    )
                    fascicoli = None
                    if os.path.exists(target["fascicoli_db"]):
                        fascicoli = GestioneFascicoli(
                            db_path=target["fascicoli_db"],
                            documents_dir=target["fascicoli_docs"],
                            archive_dir=target["fascicoli_arch"],
                        )
                    report = service.scheduled_maintenance(fascicoli, target["fascicoli_docs"])
                    processed_targets += 1
                    embeddings = report.get("embeddings") if isinstance(report.get("embeddings"), dict) else {}
                    target_errors = _as_int(report.get("errors")) + _as_int(embeddings.get("errors"))
                    totals["targets"] += 1
                    totals["indexed"] += _as_int(report.get("indexed"))
                    totals["embedded"] += _as_int(embeddings.get("embedded"))
                    totals["errors"] += target_errors
                    tenant_reports.append(
                        {
                            "tenant": str(target.get("label") or target.get("tenant_id") or ""),
                            "status": str(report.get("status") or ""),
                            "indexed": _as_int(report.get("indexed")),
                            "embedded": _as_int(embeddings.get("embedded")),
                            "errors": target_errors,
                        }
                    )
                    logger.info(
                        "[scheduler] Local AI %s: stato=%s, indexed=%s, embed=%s",
                        target["label"],
                        report.get("status"),
                        report.get("indexed", 0),
                        (report.get("embeddings") or {}).get("embedded", 0),
                    )
                if processed_targets:
                    logger.info("[scheduler] Local AI maintenance completata per %d target", processed_targets)
                return {
                    "ok": totals["errors"] == 0,
                    "job": "local_ai_maintenance",
                    "scan_mode": "maintenance_incremental",
                    "source_of_truth": "local_ai.db tenant-aware",
                    "targets": processed_targets,
                    "totals": totals,
                    "tenants": tenant_reports,
                }
            except Exception as e:
                logger.error("[scheduler] Local AI maintenance fallita: %s", e)
                return {"ok": False, "job": "local_ai_maintenance", "error": str(e)}

    @scheduler.scheduled_job(CronTrigger(minute="7-57/10"), id="lex_sentenza_economia_auto")
    def _lex_sentenza_economia_auto():
        with app.app_context():
            try:
                if _flag_enabled(
                    app.config.get("IUSENTRA_DISABLE_SENTENZA_LEX_AUTO")
                    or os.getenv("IUSENTRA_DISABLE_SENTENZA_LEX_AUTO")
                ):
                    return {"ok": True, "status": "disabled", "job": "lex_sentenza_economia_auto"}

                from pct.scheduler_registry import scheduler_registry_repository
                from scripts.backfill_sentenza_lex_economics import run_backfill

                registry = Path(
                    app.config.get("TENANTS_REGISTRY")
                    or os.getenv("PCT_TENANTS_REGISTRY")
                    or "/data/tenants.json"
                ).expanduser()
                data_root = Path(
                    app.config.get("PCT_DATA_ROOT")
                    or app.config.get("DATA_ROOT")
                    or os.getenv("PCT_DATA_ROOT")
                    or registry.parent
                ).expanduser()
                repo_root = Path(__file__).resolve().parents[1]
                skip_lex = _flag_enabled(
                    app.config.get("IUSENTRA_SENTENZA_LEX_SKIP_VECTOR")
                    or os.getenv("IUSENTRA_SENTENZA_LEX_SKIP_VECTOR")
                )
                force_full_scan = _flag_enabled(
                    app.config.get("IUSENTRA_SENTENZA_LEX_FULL_SCAN")
                    or os.getenv("IUSENTRA_SENTENZA_LEX_FULL_SCAN")
                )
                modified_after_ns = 0
                if not force_full_scan:
                    try:
                        last_run = scheduler_registry_repository(app.config).latest_completed_run(
                            "lex_sentenza_economia_auto"
                        )
                        incremental = (last_run.get("result") or {}).get("incremental")
                        if isinstance(incremental, dict):
                            modified_after_ns = int(incremental.get("newest_mtime_ns") or 0)
                    except Exception:
                        modified_after_ns = 0
                report = run_backfill(
                    data_root=data_root,
                    registry=registry,
                    repo_root=repo_root,
                    apply=True,
                    skip_lex=skip_lex,
                    limit=_parse_positive_int(
                        app.config.get("IUSENTRA_SENTENZA_LEX_AUTO_LIMIT")
                        or os.getenv("IUSENTRA_SENTENZA_LEX_AUTO_LIMIT"),
                        0,
                    ),
                    modified_after_ns=max(0, modified_after_ns),
                    lex_embed_batch_size=_parse_positive_int(
                        app.config.get("IUSENTRA_SENTENZA_LEX_EMBED_BATCH_SIZE")
                        or os.getenv("IUSENTRA_SENTENZA_LEX_EMBED_BATCH_SIZE"),
                        64,
                    ),
                    lex_embed_max_batches=_parse_positive_int(
                        app.config.get("IUSENTRA_SENTENZA_LEX_EMBED_MAX_BATCHES")
                        or os.getenv("IUSENTRA_SENTENZA_LEX_EMBED_MAX_BATCHES"),
                        3,
                    ),
                )
                totals = report.get("totals") or {}
                logger.info(
                    "[scheduler] Sentenze Lex/economia: %d documenti, %d sentenze confermate, "
                    "%d fascicoli confermati, %d applicati, %d Lex, %d salti contesto RG/cliente",
                    int(totals.get("documents_seen") or 0),
                    int(totals.get("sentenze_found") or 0),
                    int(totals.get("unique_fascicoli_confirmed") or 0),
                    int(totals.get("applied") or 0),
                    int(totals.get("vector_indexed") or 0),
                    int(totals.get("context_mismatch_skipped") or 0),
                )
                return {
                    "ok": bool(report.get("ok")),
                    "job": "lex_sentenza_economia_auto",
                    "source_of_truth": report.get("source_of_truth"),
                    "scan_mode": report.get("scan_mode"),
                    "incremental": report.get("incremental"),
                    "force_full_scan": force_full_scan,
                    "totals": totals,
                    "skip_lex": skip_lex,
                }
            except Exception as e:
                logger.error("[scheduler] Sentenze Lex/economia automatiche fallite: %s", e)
                return {"ok": False, "job": "lex_sentenza_economia_auto", "error": str(e)}

    @scheduler.scheduled_job(CronTrigger(hour=1, minute=20), id="lex_operational_agents_nightly")
    def _lex_operational_agents_nightly():
        with app.app_context():
            try:
                from lex.operational_knowledge.nightly_agents import run_operational_micro_agents
                from pct.scheduler_registry import delegated_operational_agent_specs

                report = run_operational_micro_agents(
                    app=app,
                    agents=delegated_operational_agent_specs(app.config),
                )
                results = list(report.get("results") or [])
                ok_count = sum(1 for row in results if row.get("ok"))
                verify_count = len(results) - ok_count
                logger.info(
                    "[scheduler] Agenti Lex notturni: %d ok, %d da verificare",
                    ok_count,
                    verify_count,
                )
            except Exception as e:
                logger.error("[scheduler] Agenti Lex notturni falliti: %s", e)

    @scheduler.scheduled_job(CronTrigger(hour=2, minute=40), id="lex_autonomous_learning_nightly")
    def _lex_autonomous_learning_nightly():
        # Default OFF: il template di registro nasce enabled=False, quindi
        # apply_scheduler_registry mette il job in pausa all'avvio; si attiva
        # solo dalla console Pianificazioni. Il runner ricontrolla comunque il
        # registro (cintura contro la finestra di avvio).
        with app.app_context():
            try:
                from lex.autonomy.nightly import run_lex_autonomous_learning_nightly

                report = run_lex_autonomous_learning_nightly(app=app)
                if report.get("skipped"):
                    logger.info("[scheduler] Apprendimento autonomo Lex: saltato (%s)", report.get("reason"))
                elif report.get("ok"):
                    logger.info(
                        "[scheduler] Apprendimento autonomo Lex: %d letture, %d citazioni nuove, %d proposte, stop=%s",
                        int(report.get("letture") or 0),
                        int(report.get("nuove_citazioni") or 0),
                        int(report.get("proposte") or 0),
                        report.get("stop_reason"),
                    )
                else:
                    logger.warning("[scheduler] Apprendimento autonomo Lex non riuscito: %s", report.get("error"))
            except Exception as e:
                logger.error("[scheduler] Apprendimento autonomo Lex fallito: %s", e)

    @scheduler.scheduled_job(CronTrigger(hour=1, minute=45), id="lex_dataset_nightly")
    def _lex_dataset_nightly():
        with app.app_context():
            try:
                from lex.dataset.nightly import run_lex_dataset_nightly

                report = run_lex_dataset_nightly(app=app)
                logger.info(
                    "[scheduler] Dataset Lex notturno: %d tenant, %d documenti, %d blocchi, %d domande candidate",
                    int(report.get("tenants_processed") or 0),
                    int(report.get("documents_count") or 0),
                    int(report.get("chunks_count") or 0),
                    int(report.get("qa_pairs_count") or 0),
                )
                return report
            except Exception as e:
                logger.error("[scheduler] Dataset Lex notturno fallito: %s", e)
                raise

    @scheduler.scheduled_job(CronTrigger(hour=0, minute=35), id="utf8_integrity_nightly")
    def _utf8_integrity_nightly():
        with app.app_context():
            try:
                from pct.utf8_integrity import run_utf8_integrity_service

                report = run_utf8_integrity_service(app.config, repair=True)
                logger.info(
                    "[scheduler] Integrità UTF-8: %d file controllati, %d riparati, %d da verificare",
                    int(report.get("checked_files") or 0),
                    int(report.get("repaired_files") or 0),
                    int(report.get("unresolved_replacement_files") or 0) + int(report.get("error_files") or 0),
                )
            except Exception as e:
                logger.error("[scheduler] Integrità UTF-8 fallita: %s", e)

    def _operational_resilience_targets():
        if app.config.get("MULTI_TENANT"):
            try:
                from pct.tenant import GestioneTenant, StatoTenant

                manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                found = False
                for studio in manager.lista():
                    if studio.stato == StatoTenant.SOSPESO:
                        continue
                    found = True
                    yield str(studio.slug or "").strip().lower() or "", str(studio.nome or "").strip() or "tenant"
                if found:
                    return
            except Exception as exc:
                logger.warning("[scheduler] Crash test operativo multi-tenant non disponibile: %s", exc)
        yield "", "single-studio"

    def _run_operational_crash(schedule_code: str):
        with app.app_context():
            try:
                from web.services.operational_resilience_surface import execute_operational_crash_surface

                for slug, label in _operational_resilience_targets():
                    report = execute_operational_crash_surface(
                        selected_slug=slug,
                        trigger_source="scheduler",
                        schedule_code=schedule_code,
                        auto_repair=True,
                        max_attempts=3,
                    )
                    logger.info(
                        "[scheduler] Crash test operativo %s %s: %s (%d/%d fasi passate)",
                        schedule_code,
                        label,
                        "OK" if report.get("overall_ok") else "CRITICO",
                        int((report.get("summary") or {}).get("passed_phases") or 0),
                        int((report.get("summary") or {}).get("phase_total") or 0),
                    )
            except Exception as exc:
                logger.error("[scheduler] Crash test operativo %s fallito: %s", schedule_code, exc)

    def _run_operational_backup(schedule_code: str):
        with app.app_context():
            if _backup_jobs_disabled(app):
                logger.info(
                    "[scheduler] Backup blindato %s non eseguito: archivi automatici disattivati.",
                    schedule_code,
                )
                return {"ok": True, "skipped": True, "reason": "backup_jobs_disabled"}
            try:
                from web.services.operational_resilience_surface import execute_operational_backup_surface

                for slug, label in _operational_resilience_targets():
                    report = execute_operational_backup_surface(
                        selected_slug=slug,
                        trigger_source="scheduler",
                        schedule_code=schedule_code,
                    )
                    logger.info(
                        "[scheduler] Backup blindato %s %s: %s",
                        schedule_code,
                        label,
                        "OK" if report.get("success") else "CRITICO",
                    )
            except Exception as exc:
                logger.error("[scheduler] Backup blindato %s fallito: %s", schedule_code, exc)

    @scheduler.scheduled_job(CronTrigger(hour=7, minute=0), id="operational_crash_morning")
    def _operational_crash_morning():
        _run_operational_crash("morning")

    @scheduler.scheduled_job(CronTrigger(hour=13, minute=30), id="operational_crash_midday")
    def _operational_crash_midday():
        _run_operational_crash("midday")

    @scheduler.scheduled_job(CronTrigger(hour=19, minute=30), id="operational_crash_evening")
    def _operational_crash_evening():
        _run_operational_crash("evening")

    @scheduler.scheduled_job(CronTrigger(hour=23, minute=50), id="operational_backup_nightly")
    def _operational_backup_nightly():
        return _run_operational_backup("nightly")

    # ---- Polling automatico esiti depositi telematici (ogni 15 minuti) ----
    # Aggiorna EsitoDepositoPCT in stati pendenti (INVIATO -> ACCETTATO_PEC -> CONSEGNATO)
    # interrogando PEC IMAP e PDP REST senza bloccare il thread principale.
    @scheduler.scheduled_job(CronTrigger(minute="*/15"), id="polling_esiti_deposito")
    def _polling_esiti_deposito():
        with app.app_context():
            try:
                from pct.config_studio import GestioneConfigStudio
                from pct.fascicoli import GestioneFascicoli
                from pct.polling_depositi import esegui_polling

                fascicoli_db = app.config.get("FASCICOLI_DB", "./fascicoli/fascicoli.json")
                if not os.path.exists(fascicoli_db):
                    return

                gf = GestioneFascicoli(
                    db_path=fascicoli_db,
                    documents_dir=app.config.get("FASCICOLI_DOCS", "./fascicoli/documenti"),
                    archive_dir=app.config.get("FASCICOLI_ARCH", "./fascicoli/archivio"),
                )

                # Recupera configurazione PEC studio
                config_pec = None
                try:
                    config_studio_db = (
                        app.config.get("STUDIO_CONFIG")
                        or app.config.get("CONFIG_STUDIO_DB", "./config/studio.json")
                    )
                    cfg_studio = GestioneConfigStudio(config_path=config_studio_db)
                    config_pec = getattr(cfg_studio.config, "pec", None)
                    if config_pec and (
                        not getattr(config_pec, "imap_host", "")
                        or not getattr(config_pec, "indirizzo", "")
                    ):
                        config_pec = None  # IMAP non configurato
                except Exception as e:
                    logger.debug("[scheduler] Config PEC non disponibile: %s", e)

                # Credenziali PDP (penale) se presenti
                credenziali_pdp = None
                try:
                    p12 = app.config.get("PDP_P12_PATH", os.getenv("PDP_P12_PATH", ""))
                    p12_pwd = app.config.get("PDP_P12_PASSWORD", os.getenv("PDP_P12_PASSWORD", ""))
                    if p12 and os.path.exists(p12):
                        credenziali_pdp = {"p12_path": p12, "p12_password": p12_pwd}
                except Exception:
                    pass

                report = esegui_polling(
                    gf=gf,
                    config_pec=config_pec,
                    credenziali_pdp=credenziali_pdp,
                    giorni_indietro=min(
                        _parse_positive_int(
                            app.config.get("IUSENTRA_DEPOSIT_POLL_DAYS")
                            or os.getenv("IUSENTRA_DEPOSIT_POLL_DAYS"),
                            3,
                        ),
                        7,
                    ),
                )
                if report["controllati"]:
                    logger.info(
                        "[scheduler] Polling depositi: %d controllati, %d aggiornati, %d errori",
                        report["controllati"], report["aggiornati"], report["errori"],
                    )
            except Exception as e:
                logger.error("[scheduler] Polling esiti deposito fallito: %s", e)

    # ---- Polling PEC -> Comunicazioni di cancelleria (ogni 30 minuti) ----
    # Scansiona la casella PEC alla ricerca di email di cancelleria (ACCETTAZIONE,
    # RIFIUTO, ecc.) che contengono un numero RG e le associa automaticamente
    # ai fascicoli corrispondenti nella sezione "Comunicazioni di cancelleria".
    @scheduler.scheduled_job(CronTrigger(minute="*/30"), id="poll_pec_cancelleria")
    def _poll_pec_cancelleria():
        with app.app_context():
            try:
                from pct.config_studio import GestioneConfigStudio
                from pct.fascicoli import GestioneFascicoli
                from pct.polling_depositi import poll_cancelleria_pec

                fascicoli_db = app.config.get("FASCICOLI_DB", "./fascicoli/fascicoli.json")
                if not os.path.exists(fascicoli_db):
                    return

                config_pec = None
                try:
                    config_studio_db = (
                        app.config.get("STUDIO_CONFIG")
                        or app.config.get("CONFIG_STUDIO_DB", "./config/studio.json")
                    )
                    cfg_studio = GestioneConfigStudio(config_path=config_studio_db)
                    config_pec = getattr(cfg_studio.config, "pec", None)
                    if config_pec and (
                        not getattr(config_pec, "imap_host", "")
                        or not getattr(config_pec, "indirizzo", "")
                    ):
                        config_pec = None
                except Exception as e:
                    logger.debug("[scheduler] Config PEC cancelleria non disponibile: %s", e)

                if not config_pec:
                    return

                gf = GestioneFascicoli(
                    db_path=fascicoli_db,
                    documents_dir=app.config.get("FASCICOLI_DOCS", "./fascicoli/documenti"),
                    archive_dir=app.config.get("FASCICOLI_ARCH", "./fascicoli/archivio"),
                )
                import os as _os
                state_path = _os.path.join(
                    _os.path.dirname(_os.path.abspath(fascicoli_db)),
                    "pec_cancelleria_state.json",
                )
                report = poll_cancelleria_pec(
                    gf=gf,
                    config_pec=config_pec,
                    state_path=state_path,
                    giorni_indietro=min(
                        _parse_positive_int(
                            app.config.get("IUSENTRA_PEC_CANCELLERIA_POLL_DAYS")
                            or os.getenv("IUSENTRA_PEC_CANCELLERIA_POLL_DAYS"),
                            2,
                        ),
                        7,
                    ),
                )
                if report["trovati"] or report["associati"]:
                    logger.info(
                        "[scheduler] Poll PEC cancelleria: %d trovati, %d associati, "
                        "%d duplicati, %d errori",
                        report["trovati"],
                        report["associati"],
                        report.get("duplicati", 0),
                        report["errori"],
                    )
            except Exception as e:
                logger.error("[scheduler] Poll PEC cancelleria fallito: %s", e)

    try:
        from apscheduler.events import (
            EVENT_JOB_ERROR,
            EVENT_JOB_EXECUTED,
            EVENT_JOB_MAX_INSTANCES,
            EVENT_JOB_MISSED,
            EVENT_JOB_SUBMITTED,
        )

        from pct.scheduler_registry import (
            apply_scheduler_registry,
            dispatch_requested_manual_runs,
            scheduler_registry_repository,
        )

        registry_repo = scheduler_registry_repository(app.config)
        registry_repo.upsert_default_jobs(app.config)
        startup_cutoff = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        recovered = registry_repo.cancel_manual_runs_started_before(
            startup_cutoff,
            reason="Esecuzione interrotta dal riavvio del worker; rilanciare dalla console.",
        )
        if recovered.get("cancelled"):
            logger.warning(
                "[scheduler] Richieste manuali rimaste aperte dal worker precedente chiuse: %d",
                int(recovered.get("cancelled") or 0),
            )
        recovered_scheduler = registry_repo.cancel_scheduler_runs_started_before(
            startup_cutoff,
            reason=(
                "Esecuzione scheduler interrotta dal riavvio del worker; "
                "sarà ripresa alla prossima finestra utile."
            ),
        )
        if recovered_scheduler.get("cancelled"):
            logger.warning(
                "[scheduler] Run scheduler rimasti aperti dal worker precedente chiusi: %d",
                int(recovered_scheduler.get("cancelled") or 0),
            )

        # Le richieste manuali vanno prese entro un minuto; l'apply completo
        # (upsert dei template, incluse le ~50 fonti legali, e re-schedule)
        # costa CPU/I-O a ogni giro e basta ogni 5 minuti: le modifiche di
        # orario dalla console diventano effettive entro quella finestra.
        registry_tick_state = {"count": 0}

        def _scheduler_registry_tick():
            with app.app_context():
                if registry_tick_state["count"] % 5 == 0:
                    apply_scheduler_registry(scheduler, app, registry_repo)
                registry_tick_state["count"] += 1
                dispatch_requested_manual_runs(scheduler, app, registry_repo)

        scheduler.add_job(
            _scheduler_registry_tick,
            CronTrigger(minute="*/1"),
            id="scheduler_registry_reload",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        def _record_scheduler_event(event):
            job_id = str(getattr(event, "job_id", "") or "")
            if not job_id or job_id == "scheduler_registry_reload" or job_id.startswith("manual_"):
                return
            try:
                job_row = registry_repo.get_job(job_id)
                if not job_row or not job_row.get("built_in"):
                    return
                scheduled_at = str(getattr(event, "scheduled_run_time", "") or "")
                if not scheduled_at:
                    scheduled_times = list(getattr(event, "scheduled_run_times", None) or [])
                    scheduled_at = str(scheduled_times[-1] if scheduled_times else "")
                event_code = getattr(event, "code", None)
                if event_code == EVENT_JOB_SUBMITTED:
                    registry_repo.record_scheduler_event(
                        job_id,
                        status="running",
                        scheduled_at=scheduled_at,
                        message="Esecuzione avviata dal worker.",
                        result={"ok": True, "event": "submitted"},
                    )
                elif event_code == EVENT_JOB_MAX_INSTANCES:
                    registry_repo.record_scheduler_event(
                        job_id,
                        status="missed",
                        scheduled_at=scheduled_at,
                        message="Esecuzione non avviata: istanza precedente ancora in corso.",
                    )
                elif getattr(event, "exception", None):
                    registry_repo.record_scheduler_event(
                        job_id,
                        status="failed",
                        scheduled_at=scheduled_at,
                        message="Esecuzione non completata.",
                        error_message=str(getattr(event, "exception", "")),
                    )
                elif getattr(event, "code", None) == EVENT_JOB_MISSED:
                    registry_repo.record_scheduler_event(
                        job_id,
                        status="missed",
                        scheduled_at=scheduled_at,
                        message="Esecuzione saltata dal worker.",
                    )
                else:
                    result = getattr(event, "retval", None)
                    result_payload = result if isinstance(result, dict) else {}
                    result_ok = result_payload.get("ok") if result_payload else True
                    registry_repo.record_scheduler_event(
                        job_id,
                        status="completed" if result_ok is not False else "failed",
                        scheduled_at=scheduled_at,
                        message=(
                            "Esecuzione completata dal worker."
                            if result_ok is not False
                            else "Esecuzione non completata dal worker."
                        ),
                        result=result_payload,
                        error_message=str(result_payload.get("error") or ""),
                    )
            except Exception as exc:  # pragma: no cover - audit best effort
                logger.debug("[scheduler] Evento pianificazione non registrato: %s", exc)

        scheduler.add_listener(
            _record_scheduler_event,
            EVENT_JOB_SUBMITTED
            | EVENT_JOB_EXECUTED
            | EVENT_JOB_ERROR
            | EVENT_JOB_MISSED
            | EVENT_JOB_MAX_INSTANCES,
        )
        apply_scheduler_registry(scheduler, app, registry_repo)
        dispatch_requested_manual_runs(scheduler, app, registry_repo)
    except Exception as exc:
        logger.warning("[scheduler] Registro pianificazioni non disponibile: %s", exc)

    scheduler.start()
    # Salva il riferimento nell'app per consentire il reschedule dinamico
    app.config["PCT_SCHEDULER"] = scheduler
    if (
        _daily_plan_regular_recovery_due()
        and _daily_plan_enabled()
        and _daily_plan_scheduled_runs_enabled()
        and _daily_plan_registry_recovery_enabled()
    ):
        try:
            scheduler.add_job(
                _daily_plan_startup_recovery,
                trigger="date",
                run_date=_scheduler_rome_now(app),
                id="daily_plan_startup_recovery",
                replace_existing=True,
                max_instances=1,
            )
        except Exception as exc:
            logger.warning(
                "[scheduler] Recupero automatico piano del giorno non pianificato: %s",
                exc,
            )
    logger.info(f"[scheduler] Avviato - backup alle {ora_backup}, WA reminder alle {wa_ora}.")
    return scheduler
