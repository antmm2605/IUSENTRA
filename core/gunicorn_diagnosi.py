"""Diagnosi dei worker gunicorn: perché un worker muore o resta fermo.

Collaudo del 21/11/2026: l'8080 è rimasto fermo 50 minuti e il log diceva solo
«Worker (pid) exited with code 1» ogni 15 secondi. Quelle righe erano i
controlli di salute scaduti, adottati da gunicorn come processo 1; il blocco
vero erano i quattro thread del solo worker occupati da ricerche di minuti.

Questo modulo:
- abilita faulthandler, così un worker che muore per un errore nativo lascia la pila;
- tiene l'elenco delle richieste in corso per thread;
- ogni 15 s registra le richieste oltre la soglia (con la pila del thread, una
  volta sola) e avvisa quando tutti i thread sono occupati.
"""
from __future__ import annotations

import faulthandler
import logging
import os
import sys
import threading
import time
import traceback

_LOG = logging.getLogger("gunicorn.error")
_IN_CORSO: dict[int, dict] = {}
_LOCK = threading.Lock()
SOGLIA_LENTA = float(os.getenv("IUSENTRA_RICHIESTA_LENTA_SECONDI", "30"))
INTERVALLO = float(os.getenv("IUSENTRA_SORVEGLIANZA_SECONDI", "15"))


def stato_uscita(pid: int) -> str:  # noqa: ARG001 - il codice d'uscita lo registra già gunicorn
    return "(motivo nelle righe precedenti del worker: pila di faulthandler, «richiesta lenta» o «tutti i thread occupati»)"


def inizio_richiesta(req) -> None:
    with _LOCK:
        _IN_CORSO[threading.get_ident()] = {
            "inizio": time.monotonic(), "metodo": getattr(req, "method", ""),
            "percorso": str(getattr(req, "path", ""))[:200], "segnalata": False,
        }


def fine_richiesta() -> None:
    with _LOCK:
        _IN_CORSO.pop(threading.get_ident(), None)


def richieste_in_corso() -> list[str]:
    adesso = time.monotonic()
    with _LOCK:
        return [f"{r['metodo']} {r['percorso']} da {adesso - r['inizio']:.0f} s" for r in _IN_CORSO.values()]


def registra_pile(log, motivo: str) -> None:
    frames = sys._current_frames()
    log.error("IUSENTRA: %s; richieste in corso: %s", motivo, richieste_in_corso() or "nessuna")
    for ident, frame in frames.items():
        log.error("IUSENTRA: pila del thread %s:\n%s", ident, "".join(traceback.format_stack(frame, limit=25)))


def _controlla(worker) -> None:
    adesso = time.monotonic()
    frames = sys._current_frames()
    with _LOCK:
        voci = list(_IN_CORSO.items())
    for ident, voce in voci:
        durata = adesso - voce["inizio"]
        if durata < SOGLIA_LENTA or voce["segnalata"]:
            continue
        voce["segnalata"] = True
        frame = frames.get(ident)
        pila = "".join(traceback.format_stack(frame, limit=15)) if frame else "(pila non disponibile)"
        worker.log.warning("IUSENTRA: richiesta lenta %.0f s su %s %s (pid %s)\n%s",
                           durata, voce["metodo"], voce["percorso"], worker.pid, pila)
    threads = int(getattr(worker.cfg, "threads", 1) or 1)
    if len(voci) >= threads:
        worker.log.error("IUSENTRA: tutti i %s thread del worker %s sono occupati: %s",
                         threads, worker.pid, richieste_in_corso())


def avvia_sorveglianza(worker) -> None:
    faulthandler.enable(file=sys.stderr, all_threads=True)

    def ciclo():
        while True:
            time.sleep(INTERVALLO)
            try:
                _controlla(worker)
            except Exception:  # la sorveglianza non deve mai fermare il worker
                _LOG.exception("IUSENTRA: sorveglianza dei worker non riuscita")

    threading.Thread(target=ciclo, name="iusentra-sorveglianza-worker", daemon=True).start()
