"""Il calcolatore dei pannelli pronti, finito, non resta «defunct» nello scheduler (verifica del 24/11/2026)."""

import subprocess
import sys
import time
from pathlib import Path

from web.services import pannelli_pronti_calcolatore as calcolatore


def _stato(pid: int) -> str:
    stat = Path(f"/proc/{pid}/stat")
    if not stat.exists():
        return ""
    return stat.read_text().rsplit(")", 1)[1].split()[0]


def test_il_processo_finito_viene_raccolto():
    processo = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)
    attesa = calcolatore.raccogli_alla_fine(processo)
    attesa.join(10)
    assert processo.returncode == 0
    assert _stato(processo.pid) != "Z"


def test_la_sveglia_raccoglie_il_calcolatore(monkeypatch, tmp_path):
    lanciati = []

    class PopenFinto(subprocess.Popen):
        def __init__(self, comando, **opzioni):
            lanciati.append(comando)
            super().__init__([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL)

    monkeypatch.setattr(calcolatore, "FILE_LOCK", tmp_path / "calcolatore.lock")
    monkeypatch.setattr(calcolatore.subprocess, "Popen", PopenFinto)
    raccolti = []
    originale = calcolatore.raccogli_alla_fine
    monkeypatch.setattr(calcolatore, "raccogli_alla_fine", lambda p: raccolti.append(p) or originale(p))
    assert calcolatore.sveglia_calcolatore() is True
    assert lanciati and len(raccolti) == 1
    scadenza = time.monotonic() + 10
    while raccolti[0].returncode is None and time.monotonic() < scadenza:
        time.sleep(0.05)
    assert raccolti[0].returncode == 0
    assert _stato(raccolti[0].pid) != "Z"
