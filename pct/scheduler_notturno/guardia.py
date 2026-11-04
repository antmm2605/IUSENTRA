"""Guardia dei lavori: di notte i lavori pesanti partono solo dalla catena, e mai due copie dello stesso lavoro."""

from __future__ import annotations

import contextvars
import threading
from datetime import datetime
from typing import Any, Callable

from pct.scheduler_notturno import finestra
from pct.scheduler_notturno.sequenza import (
    FASI,
    LAVORI_ANCHE_DI_GIORNO,
    LAVORI_FREQUENTI_PESANTI,
    LAVORI_SOLO_NOTTURNI_AI,
    lavori_solo_notturni,
)
from pct.semaforo_motori import PRIORITA_SEQUENZA, PRIORITA_URGENTE, SemaforoOccupato, motore_pesante

# Di giorno un lavoro pianificato aspetta il semaforo al massimo 15 minuti, poi salta al giro successivo
# (la corsia non resta bloccata). Nella catena notturna aspetta il proprio turno senza limite.
ATTESA_DIURNA_SECONDI = 15 * 60
# Nella catena l'attesa è breve: il passo non avanza e si riprova al giro successivo (un minuto dopo), così
# l'unico thread della corsia lunga non resta mai fermo per ore dentro il semaforo (notte del 03-04/11/2026).
ATTESA_CATENA_SECONDI = 5 * 60
SEMAFORO_OCCUPATO = "semaforo_occupato"
_FASE_DEL_LAVORO = {p.lavoro: f.numero for f in FASI for p in f.passi}


def priorita_del_lavoro(lavoro: str) -> int:
    """PEC e collegamenti al fascicolo (fasi 1-2) prima di tutto; poi l'ordine della sequenza."""
    fase = _FASE_DEL_LAVORO.get(lavoro, 9)
    return PRIORITA_URGENTE + fase if fase <= 2 else PRIORITA_SEQUENZA + fase

_IN_CATENA: contextvars.ContextVar[bool] = contextvars.ContextVar("in_catena_notturna", default=False)
_LOCK: dict[str, threading.Lock] = {}
_LOCK_GUARD = threading.Lock()
# Se la catena è spenta dalla console, i lavori tornano ai loro orari (nessuno resta senza esecuzione).
catena_in_servizio: Callable[[], bool] = lambda: True


def _lock(lavoro: str) -> threading.Lock:
    with _LOCK_GUARD:
        return _LOCK.setdefault(lavoro, threading.Lock())


def motivo_per_saltare(lavoro: str, momento: datetime | None = None) -> str:
    """Perché il lavoro, avviato dal proprio orario e non dalla catena, non deve partire ora ('' = può partire)."""
    if _IN_CATENA.get() or not catena_in_servizio():
        return ""
    if lavoro in LAVORI_SOLO_NOTTURNI_AI:
        return "Usa l'AI locale: si esegue solo nella fase Lex della sequenza notturna."
    notte = finestra.in_finestra(momento)
    if notte and lavoro in lavori_solo_notturni():
        return "Eseguito nella sequenza notturna, un lavoro alla volta."
    if notte and lavoro in LAVORI_FREQUENTI_PESANTI:
        return "Di notte si esegue nella sequenza notturna, non a orario fisso."
    return ""


def custodisci(lavoro: str, funzione: Callable[..., Any]) -> Callable[..., Any]:
    if getattr(funzione, "_custodito_notturno", False):
        return funzione

    def custodito(*args: Any, **kwargs: Any) -> Any:
        motivo = motivo_per_saltare(lavoro)
        if motivo:
            return {"ok": True, "skipped": True, "reason": "sequenza_notturna", "message": motivo}
        lock = _lock(lavoro)
        if not lock.acquire(blocking=False):
            return {"ok": True, "skipped": True, "reason": "gia_in_corso", "message": "Lo stesso lavoro è già in corso."}
        try:
            if lavoro in LAVORI_ANCHE_DI_GIORNO and not _IN_CATENA.get():
                # PEC, relate e avvisi a orario fisso sono brevi: non aspettano dietro l'OCR nella corsia rapida.
                return funzione(*args, **kwargs)
            attesa = ATTESA_CATENA_SECONDI if _IN_CATENA.get() else ATTESA_DIURNA_SECONDI
            with motore_pesante(lavoro, priorita=priorita_del_lavoro(lavoro), attesa_massima=attesa):
                return funzione(*args, **kwargs)
        except SemaforoOccupato:
            return {"ok": True, "skipped": True, "reason": SEMAFORO_OCCUPATO,
                    "message": "Un altro motore pesante era in corso: si riprova al giro successivo."}
        finally:
            lock.release()

    custodito._custodito_notturno = True  # type: ignore[attr-defined]
    custodito.__wrapped__ = funzione  # type: ignore[attr-defined]
    custodito.__name__ = getattr(funzione, "__name__", lavoro)
    return custodito


def esegui_in_catena(funzione: Callable[..., Any], args: Any = (), kwargs: dict[str, Any] | None = None) -> Any:
    token = _IN_CATENA.set(True)
    try:
        return funzione(*(args or ()), **(kwargs or {}))
    finally:
        _IN_CATENA.reset(token)
