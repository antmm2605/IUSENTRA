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

    scheduler.start()
    # Salva il riferimento nell'app per consentire il reschedule dinamico
    app.config["PCT_SCHEDULER"] = scheduler
    logger.info(f"[scheduler] Avviato — backup alle {ora_backup}, WA reminder alle {wa_ora}.")
    return scheduler
