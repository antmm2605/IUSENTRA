"""
pct/scheduler.py — Scheduler background per task automatici.

Usa APScheduler (già in requirements.txt) per:
  - Backup automatico giornaliero (ora configurabile)
  - Promemoria WhatsApp appuntamenti di domani (ogni giorno alle 18:00)
  - Aggiornamento scadenze SCADUTE (ogni notte)
  - Invio email di report settimanale (opzionale)

Avviato una sola volta da create_app() tramite start_scheduler(app).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

logger = logging.getLogger("pct.scheduler")


def start_scheduler(app):
    """
    Avvia lo scheduler APScheduler in background.
    Chiamare una sola volta da create_app().
    Sicuro in modalità multi-worker Gunicorn grazie al lock su file.
    """
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
        logger.warning("APScheduler non disponibile — task automatici disabilitati.")
        return

    scheduler = BackgroundScheduler(timezone="Europe/Rome")

    # ---- Backup giornaliero ----
    ora_backup = app.config.get("BACKUP_ORA", os.getenv("PCT_BACKUP_ORA", "02:00"))
    try:
        h, m = map(int, ora_backup.split(":"))
    except (ValueError, AttributeError):
        h, m = 2, 0

    @scheduler.scheduled_job(CronTrigger(hour=h, minute=m), id="backup_giornaliero")
    def _backup():
        with app.app_context():
            try:
                from pct.database import GestioneDatabase
                db = GestioneDatabase(app.config)
                import tempfile
                out = tempfile.mkdtemp(prefix="hacs_sched_")
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
    try:
        wh, wm = map(int, wa_ora.split(":"))
    except (ValueError, AttributeError):
        wh, wm = 18, 0

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
                # Solo se c'è un canale configurato
                if not cfg.ha_twilio and not cfg.ha_callmebot:
                    return
                ag = Agenda(db_path=app.config["AGENDA_DB"])
                gc = GestioneClienti(db_path=app.config["CLIENTI_DB"])
                studio_nome = app.config.get("STUDIO_NOME", "Studio Legale PCT")
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
    @scheduler.scheduled_job(CronTrigger(hour=3, minute=30), id="sync_uffici")
    def _sync_uffici():
        with app.app_context():
            try:
                from pct.sync_uffici import esegui_sync_completo
                cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                report = esegui_sync_completo(cache_path)
                if report.get("ok"):
                    logger.info(
                        "[scheduler] Sync uffici completato: %d totali, "
                        "+%d nuovi, %d PEC aggiornate",
                        report.get("n_totale_post", 0),
                        report.get("n_nuovi", 0),
                        report.get("n_pec_aggiornate", 0),
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
            ],
            "daily",
        )

    @scheduler.scheduled_job(CronTrigger(hour="6,12,18", minute=15), id="legal_monitor_pst")
    def _legal_monitor_pst():
        _run_legal_monitor(["pst_giustizia"], "pst")

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

    scheduler.start()
    # Salva il riferimento nell'app per consentire il reschedule dinamico
    app.config["PCT_SCHEDULER"] = scheduler
    logger.info(f"[scheduler] Avviato — backup alle {ora_backup}, WA reminder alle {wa_ora}.")
    return scheduler
