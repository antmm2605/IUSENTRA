"""Guardiano dello scheduler: battito fermo → worker terminato; battito vivo o worker uscito → nessun intervento."""

from __future__ import annotations

import signal
import subprocess
import sys
import time

from pct import scheduler_guardiano as g


def test_battito_fermo_solo_oltre_la_soglia(tmp_path):
    battito = tmp_path / "battito"
    assert g.battito_fermo(battito, 60) is False  # assente: avvio, non blocco
    battito.write_text(str(time.time() - 120))
    assert g.battito_fermo(battito, 60) is True
    g.scrivi_battito(battito)
    assert g.battito_fermo(battito, 60) is False


def test_un_battito_vuoto_non_e_un_battito_scaduto(tmp_path):
    battito = tmp_path / "battito"
    battito.write_text("")
    assert g.battito_fermo(battito, 60, adesso=1000) is False


def test_il_guardiano_termina_un_worker_con_battito_fermo(tmp_path):
    battito = tmp_path / "battito"
    battito.write_text(str(time.time() - 1000))
    worker = subprocess.Popen(
        [sys.executable, "-c",
         "import signal, sys, time; signal.signal(int(sys.argv[1]), signal.SIG_IGN); "
         "print('ready', flush=True); time.sleep(120)", str(g.SEGNALE_GUARDIANO)],
        stdout=subprocess.PIPE,
    )
    try:
        assert worker.stdout.readline().strip() == b"ready"
        assert g.sorveglia(worker.pid, battito, 60, attesa=0.1, grazia=0.1) in {0, 1}
        assert worker.wait(timeout=2) == -signal.SIGKILL
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.wait()
        worker.stdout.close()


def test_il_guardiano_esce_quando_il_worker_non_ce_piu(tmp_path):
    battito = tmp_path / "battito"
    g.scrivi_battito(battito)
    worker = subprocess.Popen([sys.executable, "-c", "pass"])
    worker.wait()
    assert g.sorveglia(worker.pid, battito, 60, attesa=0.1) == 0
