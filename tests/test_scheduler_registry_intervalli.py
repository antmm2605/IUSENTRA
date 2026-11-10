"""I lavori integrati «a intervallo» non devono essere rimandati a ogni applicazione del registro.

Difetto del 10/11/2026: `apply_scheduler_registry` (ogni 5 minuti) ripianificava tutti i lavori integrati e per un
intervallo di 30 minuti il prossimo giro ripartiva ogni volta da adesso: «Notizie utili dalle fonti ufficiali» non
partiva mai e l'archivio delle notizie (con la Gazzetta Ufficiale) non veniva creato.
"""

from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from pct.scheduler_registry import SchedulerRegistryRepository, apply_scheduler_registry


class _App:
    config: dict = {}


def _scheduler_con(job_id: str, **trigger) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Europe/Rome")
    scheduler.start(paused=True)
    scheduler.add_job(lambda: None, id=job_id, **trigger)
    return scheduler


def test_intervallo_non_viene_rimandato_dal_registro(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs({})
    scheduler = _scheduler_con("notiziario_fonti_ufficiali", trigger="interval", minutes=30)
    try:
        prima = scheduler.get_job("notiziario_fonti_ufficiali").next_run_time
        apply_scheduler_registry(scheduler, _App(), repo)
        apply_scheduler_registry(scheduler, _App(), repo)
        assert scheduler.get_job("notiziario_fonti_ufficiali").next_run_time == prima
    finally:
        scheduler.shutdown(wait=False)


def test_orario_cambiato_dalla_console_si_applica(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs({})
    scheduler = _scheduler_con("notiziario_fonti_ufficiali", trigger="interval", minutes=30)
    try:
        job = repo.get_job("notiziario_fonti_ufficiali")
        repo.save_job("notiziario_fonti_ufficiali", {**job, "interval_minutes": 45}, updated_by="test")
        apply_scheduler_registry(scheduler, _App(), repo)
        assert str(scheduler.get_job("notiziario_fonti_ufficiali").trigger) == "interval[0:45:00]"
    finally:
        scheduler.shutdown(wait=False)


def test_lavoro_in_pausa_riprende_se_attivo(tmp_path: Path):
    repo = SchedulerRegistryRepository(tmp_path / "scheduler.sqlite")
    repo.upsert_default_jobs({})
    scheduler = _scheduler_con("notiziario_fonti_ufficiali", trigger="interval", minutes=30)
    try:
        scheduler.pause_job("notiziario_fonti_ufficiali")
        apply_scheduler_registry(scheduler, _App(), repo)
        assert scheduler.get_job("notiziario_fonti_ufficiali").next_run_time is not None
    finally:
        scheduler.shutdown(wait=False)
