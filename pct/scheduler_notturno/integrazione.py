"""Collega la sequenza notturna allo scheduler: guardie sui lavori e passo della catena ogni minuto."""

from __future__ import annotations

import logging
import os
from typing import Any

from pct.scheduler_notturno import catena, finestra, guardia, risorse
from pct.scheduler_notturno.guardia import custodisci
from pct.scheduler_notturno.registro import RegistroNotte
from pct.scheduler_notturno.sequenza import lavori_della_sequenza

logger = logging.getLogger(__name__)

LAVORO_CATENA = "sequenza_notturna"
ESITO_REGISTRO = {"completato": "completed", "fallito": "failed"}


def sequenza_attiva() -> bool:
    return str(os.getenv("PCT_SEQUENZA_NOTTURNA", "1")).strip().lower() not in {"0", "false", "no", "off"}


def installa_sequenza_notturna(scheduler: Any, app: Any, registry_repo: Any = None) -> dict[str, Any]:
    """Da chiamare dopo aver registrato tutti i lavori e prima di ``scheduler.start()``."""
    if not sequenza_attiva():
        logger.info("[notte] Sequenza notturna disattivata (PCT_SEQUENZA_NOTTURNA=0).")
        return {"attiva": False}
    from apscheduler.triggers.cron import CronTrigger

    custoditi = []
    for lavoro in sorted(lavori_della_sequenza()):
        job = scheduler.get_job(lavoro)
        if job is not None:
            scheduler.modify_job(lavoro, func=custodisci(lavoro, job.func))
            custoditi.append(lavoro)
    db_path = getattr(registry_repo, "db_path", None) or os.path.join(
        str(app.config.get("DATA_DIR") or os.getenv("PCT_DATA_DIR", ".")), "intelligence", "scheduler_registry.sqlite")
    registro = RegistroNotte(db_path)
    ambiente = catena.Ambiente(
        trova_lavoro=scheduler.get_job,
        memoria_libera_mb=risorse.memoria_libera_mb,
        ocr_in_coda=lambda: risorse.ocr_in_coda(dict(app.config)),
        scarica_ai_locale=risorse.scarica_ai_locale,
    )

    def _passo() -> dict[str, Any]:
        with app.app_context():
            esito = catena.esegui_passo(registro, ambiente)
        if registry_repo is not None and esito.get("esito") in ESITO_REGISTRO:
            try:
                registry_repo.record_scheduler_event(
                    esito["lavoro"], status=ESITO_REGISTRO[esito["esito"]],
                    message=f"Sequenza notturna, fase {esito['fase']}: {esito['message']}",
                    error_message=esito["message"] if esito["esito"] == "fallito" else "")
            except Exception as exc:  # pragma: no cover - registro best effort
                logger.warning("[notte] Esito non registrato per %s: %s", esito.get("lavoro"), exc)
        return esito

    def _in_servizio() -> bool:
        if not getattr(scheduler, "running", False):
            return False
        job = scheduler.get_job(LAVORO_CATENA)
        return job is not None and getattr(job, "next_run_time", True) is not None

    guardia.catena_in_servizio = _in_servizio
    inizio, fine = finestra.inizio(), finestra.fine()
    ore = f"{inizio.hour}-23,0-{fine.hour}"
    scheduler.add_job(_passo, CronTrigger(timezone="Europe/Rome", hour=ore, minute="*"), id=LAVORO_CATENA,
                      replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=50)
    logger.info("[notte] Sequenza notturna %s-%s: %d lavori custoditi.", inizio, fine, len(custoditi))
    return {"attiva": True, "custoditi": custoditi}
