"""Corsie dello scheduler: un lavoro alla volta per corsia (verifica del 02/11/2026, tre OOM in una mattina)."""

from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from pct.scheduler_corsie import (
    CORSIA_ACQUISIZIONE_PEC,
    CORSIA_GIURISPRUDENZA,
    CORSIA_INFRASTRUTTURA,
    CORSIA_LUNGA,
    CORSIA_NOTTURNA,
    CORSIA_RAPIDA,
    LAVORI_GIURISPRUDENZA,
    LAVORI_INFRASTRUTTURA,
    LAVORI_RAPIDI,
    TOLLERANZA_RITARDO_SECONDI,
    assegna_corsie,
    corsia_del_lavoro,
    esecutori,
)
from pct.scheduler_recupero_piano import annota_tentativo, recupero_gia_tentato

SORGENTE = Path(__file__).resolve().parents[1] / "pct" / "scheduler.py"


def test_i_lavori_elencati_nelle_corsie_esistono_nello_scheduler():
    ids = set(re.findall(r"""id=['"]([a-z0-9_]+)['"]""", SORGENTE.read_text(encoding="utf-8")))
    assert LAVORI_RAPIDI <= ids, LAVORI_RAPIDI - ids
    assert LAVORI_INFRASTRUTTURA <= ids, LAVORI_INFRASTRUTTURA - ids
    assert LAVORI_GIURISPRUDENZA <= ids, LAVORI_GIURISPRUDENZA - ids
    assert set(TOLLERANZA_RITARDO_SECONDI) <= ids, set(TOLLERANZA_RITARDO_SECONDI) - ids


def test_corsia_di_ogni_lavoro():
    assert corsia_del_lavoro("manual_pec_audit_pipeline_workers_1a2b3c4d") == CORSIA_ACQUISIZIONE_PEC
    assert corsia_del_lavoro("mailbox_sync_runtime") == CORSIA_RAPIDA
    assert corsia_del_lavoro("manual_mailbox_sync_runtime_1a2b3c4d") == CORSIA_RAPIDA
    assert corsia_del_lavoro("scheduler_registry_reload") == CORSIA_INFRASTRUTTURA
    assert corsia_del_lavoro("pannelli_pronti_ricalcolo") == CORSIA_INFRASTRUTTURA
    assert corsia_del_lavoro("fascicoli_document_economic_presidio") == CORSIA_LUNGA
    # Pesanti e sconosciuti, comprese le fonti legali del registro, vanno nella corsia lunga.
    for lavoro in ("operational_crash_morning", "studio_daily_operational_plan", "legal_source_garante", "nuovo"):
        assert corsia_del_lavoro(lavoro) == CORSIA_LUNGA


def _scheduler_con_registro():
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(
        timezone="Europe/Rome", executors=esecutori(),
        job_defaults={"misfire_grace_time": 300, "coalesce": True, "max_instances": 1},
    )
    intervalli: dict[str, tuple[float, float]] = {}
    fatti = threading.Event()

    def lavoro(nome: str) -> None:
        inizio = time.monotonic()
        time.sleep(0.4)
        intervalli[nome] = (inizio, time.monotonic())
        if len(intervalli) == 4:
            fatti.set()

    adesso = datetime.now().astimezone()
    for nome in ("legal_updates_batch", "collaudo_lettore", "mailbox_sync_runtime", "sequenza_notturna"):
        scheduler.add_job(lavoro, "date", run_date=adesso + timedelta(milliseconds=200), args=[nome], id=nome)
    return scheduler, intervalli, fatti


def test_due_lavori_pesanti_non_si_sovrappongono_mentre_la_corsia_rapida_procede():
    scheduler, intervalli, fatti = _scheduler_con_registro()
    conteggio = assegna_corsie(scheduler)
    assert conteggio[CORSIA_LUNGA] == 2 and conteggio[CORSIA_RAPIDA] == 1
    assert conteggio[CORSIA_NOTTURNA] == 1
    scheduler.start()
    try:
        assert fatti.wait(5)
    finally:
        scheduler.shutdown(wait=True)
    (a_inizio, a_fine), (b_inizio, b_fine) = intervalli["legal_updates_batch"], intervalli["collaudo_lettore"]
    assert a_fine <= b_inizio or b_fine <= a_inizio, "due lavori della corsia lunga insieme"
    r_inizio, _ = intervalli["mailbox_sync_runtime"]
    assert r_inizio < max(a_fine, b_fine), "la corsia rapida non deve aspettare la corsia lunga"
    n_inizio, _ = intervalli["sequenza_notturna"]
    assert n_inizio < min(a_fine, b_fine), "la sequenza deve partire durante il primo lavoro lungo"


def test_il_recupero_del_piano_si_tenta_una_volta_al_giorno(tmp_path: Path):
    oggi = date(2026, 11, 2)
    assert not recupero_gia_tentato(tmp_path, oggi)
    assert annota_tentativo(tmp_path, oggi)
    assert recupero_gia_tentato(tmp_path, oggi)
    assert not recupero_gia_tentato(tmp_path, oggi + timedelta(days=1))


def test_acquisizione_pec_non_blocca_gli_avvisi():
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(executors=esecutori())
    acquisizione_avviata = threading.Event()
    avvisi_consegnati = threading.Event()
    chiudi_acquisizione = threading.Event()

    def acquisisci():
        acquisizione_avviata.set()
        chiudi_acquisizione.wait(5)

    scheduler.add_job(acquisisci, id="pec_audit_pipeline_workers")
    assegna_corsie(scheduler)
    scheduler.start()
    try:
        assert acquisizione_avviata.wait(3)
        scheduler.add_job(avvisi_consegnati.set, id="agenda_scadenziario_notifications",
                          executor=corsia_del_lavoro("agenda_scadenziario_notifications"))
        assert avvisi_consegnati.wait(2)
    finally:
        chiudi_acquisizione.set()
        scheduler.shutdown(wait=True)


def test_alimentazione_giurisprudenza_in_corsia_propria():
    """Verifica del 18/11/2026: nella corsia lunga occupava fino a un'ora e faceva saltare gli altri lavori."""
    assert corsia_del_lavoro("giurisprudenza_alimentazione_continua") == CORSIA_GIURISPRUDENZA
    assert corsia_del_lavoro("manual_cassazione_sentenzeweb_nightly_1a2b3c4d") == CORSIA_GIURISPRUDENZA
    assert CORSIA_GIURISPRUDENZA in esecutori()


def test_tolleranza_di_ritardo_per_i_lavori_a_orario_fisso_della_corsia_lunga():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(
        timezone="Europe/Rome", executors=esecutori(),
        job_defaults={"misfire_grace_time": 300, "coalesce": True, "max_instances": 1},
    )
    nulla = lambda: None  # noqa: E731
    scheduler.add_job(nulla, CronTrigger(hour=19, minute=30), id="operational_crash_evening")
    scheduler.add_job(nulla, CronTrigger(hour=20, minute=30), id="time_tracking_passivo")
    scheduler.add_job(nulla, CronTrigger(minute="3-58/10"), id="archivio_letture_automatico", misfire_grace_time=120)
    scheduler.add_job(nulla, CronTrigger(minute=25), id="gazzetta_ufficiale_sommari", misfire_grace_time=3000)
    scheduler.add_job(nulla, CronTrigger(minute="*/1"), id="pannelli_pronti_ricalcolo")
    assegna_corsie(scheduler)
    tolleranze = {job.id: getattr(job, "misfire_grace_time", "predefinita") for job in scheduler.get_jobs()}
    assert tolleranze["operational_crash_evening"] == 2 * 3600
    assert tolleranze["time_tracking_passivo"] == 3600
    assert tolleranze["archivio_letture_automatico"] == 8 * 60
    # Le tolleranze già più ampie e i lavori non elencati restano come sono.
    assert tolleranze["gazzetta_ufficiale_sommari"] == 3000
    assert tolleranze["pannelli_pronti_ricalcolo"] == "predefinita"


def test_giro_in_ritardo_oltre_cinque_minuti_si_esegue_entro_la_tolleranza():
    """Prova con APScheduler reale: corsia lunga occupata, il controllo operativo parte in ritardo e si esegue."""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone="Europe/Rome", executors=esecutori(),
                                    job_defaults={"misfire_grace_time": 1, "coalesce": True, "max_instances": 1})
    eseguito = threading.Event()
    adesso = datetime.now().astimezone()
    # Il lavoro lungo occupa la corsia per 2,5 secondi: con la tolleranza di 1 secondo il controllo verrebbe scartato.
    scheduler.add_job(time.sleep, "date", run_date=adesso + timedelta(milliseconds=100), args=[2.5], id="daily_plan_incremental_refresh")
    scheduler.add_job(eseguito.set, "date", run_date=adesso + timedelta(milliseconds=300), id="operational_crash_evening")
    assegna_corsie(scheduler)
    scheduler.start()
    try:
        assert eseguito.wait(6), "il controllo operativo in ritardo deve essere eseguito, non scartato"
    finally:
        scheduler.shutdown(wait=True)
