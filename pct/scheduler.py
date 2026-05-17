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
from pathlib import Path
import subprocess
import sys

from pct.runtime_env import is_managed_cloud_runtime

logger = logging.getLogger("pct.scheduler")


def _flag_enabled(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _runtime_path(app, key: str, env_key: str, default: str) -> str:
    return str(app.config.get(key) or os.getenv(env_key) or default)


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

    scheduler = BackgroundScheduler(timezone="Europe/Rome")

    # ---- Backup giornaliero ----
    ora_backup = app.config.get("BACKUP_ORA", os.getenv("PCT_BACKUP_ORA", "02:00"))
    h, m = _parse_hhmm(ora_backup, "02:00")

    @scheduler.scheduled_job(CronTrigger(hour=h, minute=m), id="backup_giornaliero")
    def _backup():
        with app.app_context():
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
                from pct.notifiche_wa import (ConfigWA,
                                               promemoria_appuntamenti_di_domani)
                from pct.agenda import Agenda
                from pct.clienti import GestioneClienti
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
                from pct.legal_update_batch_runner import LegalUpdateJobConfig, run_legal_update_batch_with_timeouts

                timeout_seconds = _parse_positive_int(
                    app.config.get("LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS")
                    or os.getenv("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS"),
                    180,
                )
                publish_max_items = _parse_positive_int(
                    app.config.get("LEGAL_UPDATES_PUBLISH_MAX_ITEMS")
                    or os.getenv("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS"),
                    80,
                )
                config = LegalUpdateJobConfig(
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
                report = run_legal_update_batch_with_timeouts(
                    config,
                    source_codes=source_ids,
                    auto_publish=auto_publish,
                    item_timeout_seconds=timeout_seconds,
                    publish_max_items=publish_max_items,
                )
                logger.info(
                    "[scheduler] Legal updates %s: %d fonti, %d news autopubblicate, %d timeout per elemento",
                    label,
                    len(report.get("reports") or []),
                    int((report.get("autopublished") or {}).get("count") or 0),
                    int(report.get("timeouts") or 0),
                )
            except Exception as e:
                logger.error("[scheduler] Legal updates %s fallito: %s", label, e)

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

    @scheduler.scheduled_job(CronTrigger(hour=23, minute=10), id="legal_updates_gazzetta")
    def _legal_updates_gazzetta():
        _run_legal_updates(["gazzetta_ufficiale"], "gazzetta")

    @scheduler.scheduled_job(CronTrigger(hour=23, minute=15), id="legal_updates_batch")
    def _legal_updates_batch():
        _run_legal_updates(
            [
                "gazzetta_ufficiale",
                "normattiva",
                "dati_normattiva",
                "corte_costituzionale",
                "cassazione_massimario",
                "openga_giustizia_amministrativa",
                "openga_calendario_udienze",
                "openga_decreti",
                "openga_ordinanze",
                "openga_pareri",
                "openga_provvedimenti_pubblicati",
                "openga_ricorsi_definiti",
                "openga_ricorsi_pendenti",
                "openga_ricorsi_pervenuti",
                "openga_sentenze",
                "eur_lex",
                "agenzia_entrate",
                "ministero_lavoro",
                "ministero_lavoro_interpelli",
                "garante_privacy",
                "anac_documenti",
                "inps_circolari",
                "inps_messaggi",
                "inps_sentenze",
                "curia_cgue_rss",
                "istat_prezzi",
                "mimit_incentivi",
                "agcm_bollettino",
                "agcom_provvedimenti",
                "banca_italia_normativa",
                "pst_giustizia_download",
            ],
            "batch",
        )

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

    def _mailbox_sync_targets():
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
                for target in _calendar_engine_targets():
                    engine = CalendarSyncEngine.from_paths(
                        agenda_db=target["agenda_db"],
                        scadenziario_db=target["scadenziario_db"],
                        sync_db=target["calendar_sync_db"],
                        tenant_id=target["tenant_id"],
                    )
                    report = engine.sync_due_jobs()
                    processed += int(report.get("processed") or 0)
                if processed:
                    logger.info("[scheduler] Calendar retry completato: %d job", processed)
            except Exception as e:
                logger.error("[scheduler] Calendar retry fallito: %s", e)

    @scheduler.scheduled_job(CronTrigger(minute="*/15"), id="mailbox_sync_runtime")
    def _mailbox_sync_runtime():
        with app.app_context():
            try:
                from web.services.mailbox_sync_runtime import sync_mailboxes_for_paths

                processed_targets = 0
                for label, paths in _mailbox_sync_targets():
                    report = sync_mailboxes_for_paths(paths, tenant_label=label, cooldown_seconds=180.0)
                    processed_targets += 1
                    pec = report.get("pec") or {}
                    ordinary = report.get("ordinary") or {}
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
            except Exception as e:
                logger.error("[scheduler] Mailbox sync fallita: %s", e)

    @scheduler.scheduled_job(CronTrigger(minute="*/20"), id="workspace_intelligence_snapshot")
    def _workspace_intelligence_snapshot():
        with app.app_context():
            try:
                from pct.agenda import Agenda
                from pct.calendar_sync import GestioneCalendarSync
                from pct.fascicoli import GestioneFascicoli
                from pct.giurisprudenza import GestioneGiurisprudenza
                from pct.scadenziario import GestioneScadenziario, regola_patrono_studio
                from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
                from pct.workspace_intelligente import WorkspaceIntelligenteService
                from pct.config_studio import GestioneConfigStudio

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

                    snapshot = service.save_snapshot(target["snapshot_db"])
                    processed_targets += 1
                    logger.info(
                        "[scheduler] Workspace intelligence %s: %d fascicoli attenzionati, %d scadenze urgenti",
                        target["label"],
                        snapshot.get("overview", {}).get("summary", {}).get("fascicoli_attenzionati", 0),
                        snapshot.get("overview", {}).get("summary", {}).get("scadenze_urgenti", 0),
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
                    return

                from pct.fascicoli import GestioneFascicoli
                from pct.local_ai import LocalAIService

                processed_targets = 0
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
                    logger.info(
                        "[scheduler] Local AI %s: stato=%s, indexed=%s, embed=%s",
                        target["label"],
                        report.get("status"),
                        report.get("indexed", 0),
                        (report.get("embeddings") or {}).get("embedded", 0),
                    )
                if processed_targets:
                    logger.info("[scheduler] Local AI maintenance completata per %d target", processed_targets)
            except Exception as e:
                logger.error("[scheduler] Local AI maintenance fallita: %s", e)

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
                        int(((report.get("summary") or {}).get("passed_phases") or 0)),
                        int(((report.get("summary") or {}).get("phase_total") or 0)),
                    )
            except Exception as exc:
                logger.error("[scheduler] Crash test operativo %s fallito: %s", schedule_code, exc)

    def _run_operational_backup(schedule_code: str):
        with app.app_context():
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
        _run_operational_backup("nightly")

    # ---- Polling automatico esiti depositi telematici (ogni 15 minuti) ----
    # Aggiorna EsitoDepositoPCT in stati pendenti (INVIATO -> ACCETTATO_PEC -> CONSEGNATO)
    # interrogando PEC IMAP e PDP REST senza bloccare il thread principale.
    @scheduler.scheduled_job(CronTrigger(minute="*/15"), id="polling_esiti_deposito")
    def _polling_esiti_deposito():
        with app.app_context():
            try:
                from pct.fascicoli import GestioneFascicoli
                from pct.config_studio import GestioneConfigStudio
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
                from pct.fascicoli import GestioneFascicoli
                from pct.config_studio import GestioneConfigStudio
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
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
        from pct.scheduler_registry import (
            apply_scheduler_registry,
            dispatch_requested_manual_runs,
            scheduler_registry_repository,
        )

        registry_repo = scheduler_registry_repository(app.config)
        registry_repo.upsert_default_jobs(app.config)

        def _scheduler_registry_tick():
            with app.app_context():
                apply_scheduler_registry(scheduler, app, registry_repo)
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
                if getattr(event, "exception", None):
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
                    registry_repo.record_scheduler_event(
                        job_id,
                        status="completed",
                        scheduled_at=scheduled_at,
                        message="Esecuzione completata dal worker.",
                    )
            except Exception as exc:  # pragma: no cover - audit best effort
                logger.debug("[scheduler] Evento pianificazione non registrato: %s", exc)

        scheduler.add_listener(
            _record_scheduler_event,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED,
        )
        apply_scheduler_registry(scheduler, app, registry_repo)
        dispatch_requested_manual_runs(scheduler, app, registry_repo)
    except Exception as exc:
        logger.warning("[scheduler] Registro pianificazioni non disponibile: %s", exc)

    scheduler.start()
    # Salva il riferimento nell'app per consentire il reschedule dinamico
    app.config["PCT_SCHEDULER"] = scheduler
    logger.info(f"[scheduler] Avviato - backup alle {ora_backup}, WA reminder alle {wa_ora}.")
    return scheduler
