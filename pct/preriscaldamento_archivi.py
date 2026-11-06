"""Preriscaldamento degli archivi normativi: la prima ricerca dopo l'avvio non attende la lettura dal disco.

L'archivio Normattiva (alcuni GB) si legge per intero una volta, in sfondo e a bassa priorità, dal worker dello
scheduler: la cache del sistema operativo è condivisa, quindi ne beneficiano anche i processi dell'app. Si attiva
solo con ``IUSENTRA_PRERISCALDA_ARCHIVI=1`` (copia locale); sul server resta spento finché non lo si decide.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_BLOCCO = 8 * 1024 * 1024
_PAUSA_SECONDI = 0.02  # lascia spazio agli altri lavori del disco


def archivi_da_preriscaldare() -> list[Path]:
    percorsi = [os.getenv("PCT_NORMATTIVA_DB", ""), os.getenv("PCT_CODICI_LEGGI_DB", "")]
    return [Path(p) for p in dict.fromkeys(percorsi) if p and Path(p).is_file()]


def preriscalda(percorso: Path, *, fermo: threading.Event | None = None) -> int:
    """Legge il file a blocchi; restituisce i byte letti (si interrompe all'arresto del worker)."""
    letti = 0
    with open(percorso, "rb", buffering=0) as file:
        while not (fermo and fermo.is_set()):
            blocco = file.read(_BLOCCO)
            if not blocco:
                break
            letti += len(blocco)
            time.sleep(_PAUSA_SECONDI)
    return letti


def avvia_in_sfondo(fermo: threading.Event | None = None) -> threading.Thread | None:
    if os.getenv("IUSENTRA_PRERISCALDA_ARCHIVI", "").strip() != "1":
        return None
    archivi = archivi_da_preriscaldare()
    if not archivi:
        return None

    def _lavoro() -> None:
        try:
            os.nice(19)
        except OSError:
            pass
        for archivio in archivi:
            inizio = time.monotonic()
            try:
                letti = preriscalda(archivio, fermo=fermo)
                logger.info("Archivio %s preriscaldato: %d MB in %.0f s.", archivio.name, letti // 2**20, time.monotonic() - inizio)
            except OSError as exc:
                logger.warning("Preriscaldamento di %s non riuscito: %s", archivio, exc)

    filo = threading.Thread(target=_lavoro, name="preriscaldamento-archivi", daemon=True)
    filo.start()
    return filo


__all__ = ["archivi_da_preriscaldare", "avvia_in_sfondo", "preriscalda"]
