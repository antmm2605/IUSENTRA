"""Guardiano dello scheduler: battito fermo → worker terminato; battito vivo o worker uscito → nessun intervento."""

from __future__ import annotations

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


def test_il_guardiano_termina_un_worker_con_battito_fermo(tmp_path):
    battito = tmp_path / "battito"
    battito.write_text(str(time.time() - 1000))
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        assert g.sorveglia(worker.pid, battito, 60, attesa=0.1) in {0, 1}
        assert worker.wait(timeout=40) is not None
    finally:
        worker.kill()


def test_il_guardiano_esce_quando_il_worker_non_ce_piu(tmp_path):
    battito = tmp_path / "battito"
    g.scrivi_battito(battito)
    worker = subprocess.Popen([sys.executable, "-c", "pass"])
    worker.wait()
    assert g.sorveglia(worker.pid, battito, 60, attesa=0.1) == 0
