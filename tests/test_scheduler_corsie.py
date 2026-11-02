"""Corsie dello scheduler: un lavoro alla volta per corsia (verifica del 02/11/2026, tre OOM in una mattina)."""

from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from pct.scheduler_corsie import (
    CORSIA_INFRASTRUTTURA,
    CORSIA_LUNGA,
    CORSIA_RAPIDA,
    LAVORI_INFRASTRUTTURA,
    LAVORI_RAPIDI,
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


def test_corsia_di_ogni_lavoro():
    assert corsia_del_lavoro("mailbox_sync_runtime") == CORSIA_RAPIDA
    assert corsia_del_lavoro("manual_mailbox_sync_runtime_1a2b3c4d") == CORSIA_RAPIDA
    assert corsia_del_lavoro("scheduler_registry_reload") == CORSIA_INFRASTRUTTURA
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
        if len(intervalli) == 3:
            fatti.set()

    adesso = datetime.now().astimezone()
    for nome in ("legal_updates_batch", "collaudo_lettore", "mailbox_sync_runtime"):
        scheduler.add_job(lavoro, "date", run_date=adesso + timedelta(milliseconds=200), args=[nome], id=nome)
    return scheduler, intervalli, fatti


def test_due_lavori_pesanti_non_si_sovrappongono_mentre_la_corsia_rapida_procede():
    scheduler, intervalli, fatti = _scheduler_con_registro()
    conteggio = assegna_corsie(scheduler)
    assert conteggio[CORSIA_LUNGA] == 2 and conteggio[CORSIA_RAPIDA] == 1
    scheduler.start()
    try:
        assert fatti.wait(5)
    finally:
        scheduler.shutdown(wait=True)
    (a_inizio, a_fine), (b_inizio, b_fine) = intervalli["legal_updates_batch"], intervalli["collaudo_lettore"]
    assert a_fine <= b_inizio or b_fine <= a_inizio, "due lavori della corsia lunga insieme"
    r_inizio, _ = intervalli["mailbox_sync_runtime"]
    assert r_inizio < max(a_fine, b_fine), "la corsia rapida non deve aspettare la corsia lunga"


def test_il_recupero_del_piano_si_tenta_una_volta_al_giorno(tmp_path: Path):
    oggi = date(2026, 11, 2)
    assert not recupero_gia_tentato(tmp_path, oggi)
    assert annota_tentativo(tmp_path, oggi)
    assert recupero_gia_tentato(tmp_path, oggi)
    assert not recupero_gia_tentato(tmp_path, oggi + timedelta(days=1))
