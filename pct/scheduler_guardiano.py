"""Guardiano dello scheduler: se il battito si ferma, il worker viene chiuso e Docker lo riavvia.

Caso reale dell'08/11/2026: un'espressione regolare non lineare nella lettura di un documento ha tenuto il GIL per
oltre 90 minuti; lo scheduler era vivo (CPU al 90%) ma tutti i lavori automatici erano fermi e il container
risultava solo «unhealthy». Un controllo nello stesso processo non può intervenire (anche lui attende il GIL):
il guardiano è un PROCESSO separato che legge un file di battito scritto ogni 30 secondi da un lavoro dello
scheduler. Se il battito è più vecchio della soglia, termina il worker; il container esce e la politica di
riavvio di Docker lo riavvia. Serve che il worker non sia il processo 1 del container (``init: true`` nel compose):
al processo 1 il kernel non consegna i segnali senza gestore.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SOGLIA_SECONDI = int(os.getenv("IUSENTRA_SCHEDULER_GUARDIANO_SOGLIA", "900"))
INTERVALLO_BATTITO = 30
FILE_BATTITO = Path(os.getenv("IUSENTRA_SCHEDULER_BATTITO", "/tmp/iusentra-scheduler-battito"))


def scrivi_battito(percorso: Path = FILE_BATTITO) -> None:
    """Lavoro dello scheduler: registra che il ciclo dei lavori automatici è vivo."""
    percorso.write_text(str(time.time()), encoding="utf-8")


def battito_fermo(percorso: Path, soglia: int, *, adesso: float | None = None) -> bool:
    """Vero se il battito esiste ed è più vecchio della soglia (un file assente è un avvio, non un blocco)."""
    try:
        ultimo = float(percorso.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return False
    return ((adesso if adesso is not None else time.time()) - ultimo) > soglia


def avvia_guardiano(percorso: Path = FILE_BATTITO, soglia: int = SOGLIA_SECONDI) -> subprocess.Popen | None:
    """Avvia il processo guardiano per il worker corrente; non lo avvia se il worker è il processo 1."""
    if os.getenv("IUSENTRA_SCHEDULER_GUARDIANO", "1").strip() == "0":
        return None
    if os.getpid() == 1:
        logger.warning("Guardiano dello scheduler non attivo: il worker è il processo 1 del container (serve «init: true»).")
        return None
    scrivi_battito(percorso)
    return subprocess.Popen([sys.executable, "-m", "pct.scheduler_guardiano", str(os.getpid()), str(percorso), str(soglia)],
                            close_fds=True, start_new_session=True)


def sorveglia(pid: int, percorso: Path, soglia: int, *, attesa: float = INTERVALLO_BATTITO) -> int:
    """Ciclo del guardiano: esce quando il worker termina; se il battito è fermo lo termina (prima TERM, poi KILL)."""
    while True:
        try:
            os.kill(pid, 0)
        except OSError:
            return 0  # il worker non c'è più: niente da sorvegliare
        if battito_fermo(percorso, soglia):
            print(f"[guardiano-scheduler] battito fermo da oltre {soglia} s: termino il worker {pid} per il riavvio", flush=True)
            for segnale, pausa in ((signal.SIGTERM, 30), (signal.SIGKILL, 0)):
                try:
                    os.kill(pid, segnale)
                except OSError:
                    return 0
                time.sleep(pausa)
                try:
                    os.kill(pid, 0)
                except OSError:
                    return 0
            return 1
        time.sleep(attesa)


if __name__ == "__main__":
    sys.exit(sorveglia(int(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])))
