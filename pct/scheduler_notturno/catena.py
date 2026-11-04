"""Un passo della catena notturna per giro: il successivo parte solo quando il precedente è finito.

Il lavoro ``sequenza_notturna`` gira ogni minuto nella corsia lunga (un thread): ogni giro esegue al più un passo,
scrive l'esito nel registro e avanza. Così la catena si riprende da sola dopo un riavvio, aspetta la memoria e la
coda OCR, non avvia nulla dopo le 07:30 e la notte seguente riparte dal passo non eseguito.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from pct.scheduler_notturno import finestra
from pct.scheduler_notturno.guardia import SEMAFORO_OCCUPATO, esegui_in_catena
from pct.scheduler_notturno.registro import RegistroNotte
from pct.scheduler_notturno.sequenza import Fase, Passo, passi_in_ordine

logger = logging.getLogger(__name__)

ATTESA_MEMORIA_MAX = timedelta(minutes=20)
ATTESA_OCR_MAX = timedelta(minutes=90)


@dataclass
class Ambiente:
    """Ciò che la catena usa dal mondo esterno (sostituibile nei test)."""

    trova_lavoro: Callable[[str], Any]
    memoria_libera_mb: Callable[[], int]
    ocr_in_coda: Callable[[], int]
    scarica_ai_locale: Callable[[], list[str]]


def _iso(m: datetime) -> str:
    return m.isoformat(timespec="seconds")


def _niente_da_fare(esito: Any) -> bool:
    """Per i passi ripetuti: il giro non ha trovato lavoro (nessun numero positivo nell'esito)."""
    if not esito or not isinstance(esito, dict) or esito.get("skipped") or esito.get("ok") is False:
        return True
    numeri = [v for v in esito.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return bool(numeri) and not any(v > 0 for v in numeri)


def _esegui_lavoro(job: Any, passo: Passo, limite: datetime, adesso: Callable[[], datetime]) -> tuple[str, str]:
    giri = 0
    esito: Any = None
    fine_ripetizioni = adesso() + timedelta(minutes=passo.ripeti_minuti)
    while True:
        esito = esegui_in_catena(job.func, list(job.args or []), dict(job.kwargs or {}))
        giri += 1
        if isinstance(esito, dict) and esito.get("reason") == SEMAFORO_OCCUPATO:
            if giri == 1:
                return "attesa", str(esito.get("message") or "Semaforo dei motori occupato.")
            break
        if isinstance(esito, dict) and esito.get("ok") is False:
            return "fallito", str(esito.get("error") or esito.get("message") or "Esito negativo.")[:300]
        if not passo.ripeti_minuti or _niente_da_fare(esito) or adesso() >= min(fine_ripetizioni, limite):
            break
    return "completato", f"Eseguito {giri} {'volta' if giri == 1 else 'volte'}."


def esegui_passo(registro: RegistroNotte, ambiente: Ambiente, momento: datetime | None = None,
                 adesso: Callable[[], datetime] = finestra.adesso) -> dict[str, Any]:
    ora = momento or adesso()
    if not finestra.in_finestra(ora):
        return {"ok": True, "skipped": True, "message": "Fuori dalla finestra notturna."}
    passi = passi_in_ordine()
    totale = len(passi)
    sera = finestra.sera_della_notte(ora).isoformat()
    stato = registro.avanzamento(sera)
    if stato is None:
        partenza, ripresa = 0, ""
        precedente = registro.ultima_notte_prima(sera)
        if precedente and not precedente["conclusa"]:
            partenza = (int(precedente["partenza"]) + int(precedente["indice"])) % totale
            ripresa = f"Ripresa dal passo {partenza + 1} della notte del {precedente['sera']}."
        stato = registro.apri_notte(sera, partenza, ripresa, _iso(ora))
    if stato["conclusa"]:
        return {"ok": True, "skipped": True, "message": "Sequenza notturna già conclusa."}
    if ora >= finestra.scadenza(ora):
        return {"ok": True, "skipped": True, "message": "Oltre le 07:30: si riprende la notte successiva."}

    indice = int(stato["indice"])
    fase, passo = passi[(int(stato["partenza"]) + indice) % totale]
    avviato = datetime.fromisoformat(stato["passo_avviato_alle"]) if stato["passo_avviato_alle"] else ora
    if not stato["passo_avviato_alle"]:
        registro.aggiorna(sera, _iso(ora), passo_avviato_alle=_iso(ora))
    memoria = ambiente.memoria_libera_mb()

    def avanza(esito: str, messaggio: str, secondi: float = 0.0) -> dict[str, Any]:
        fine = adesso()
        registro.scrivi_passo(sera, indice, fase.numero, passo.lavoro, esito, messaggio=messaggio,
                              avvio=_iso(avviato), fine=_iso(fine), secondi=secondi, memoria_libera_mb=memoria)
        nuovo = indice + 1
        registro.aggiorna(sera, _iso(fine), indice=nuovo, passo_avviato_alle="", conclusa=int(nuovo >= totale))
        if fase.usa_ai_locale and _ultimo_della_fase(passi, fase, passo):
            ambiente.scarica_ai_locale()
        return {"ok": esito != "fallito", "fase": fase.numero, "lavoro": passo.lavoro, "esito": esito,
                "message": messaggio, "passo": nuovo, "totale": totale}

    if passo.lavoro.startswith("__"):
        return _passo_di_attesa(fase, ambiente, ora, avviato, avanza)
    if passo.giorni and finestra.sera_della_notte(ora).weekday() not in passo.giorni:
        return avanza("saltato", "Lavoro settimanale: non previsto stanotte.")
    job = ambiente.trova_lavoro(passo.lavoro)
    if job is None or getattr(job, "next_run_time", True) is None:
        return avanza("spento", "Pianificazione spenta o non disponibile in questo processo.")
    if memoria and memoria < fase.memoria_minima_mb and ora - avviato < ATTESA_MEMORIA_MAX:
        return {"ok": True, "skipped": True, "message": f"In attesa di memoria libera ({memoria} MB)."}
    inizio = time.monotonic()
    try:
        esito, messaggio = _esegui_lavoro(job, passo, finestra.scadenza(ora), adesso)
    except Exception as exc:  # una fase che fallisce non blocca le successive
        logger.exception("[notte] Passo %s non riuscito", passo.lavoro)
        esito, messaggio = "fallito", f"{type(exc).__name__}: {str(exc)[:240]}"
    if esito == "attesa":
        # Il passo non è stato eseguito: resta lo stesso e si riprova al giro successivo, entro le 07:30.
        return {"ok": True, "skipped": True, "message": f"In attesa del turno: {messaggio}"}
    return avanza(esito, messaggio, time.monotonic() - inizio)


def _ultimo_della_fase(passi: list[tuple[Fase, Passo]], fase: Fase, passo: Passo) -> bool:
    della_fase = [p for f, p in passi if f.numero == fase.numero]
    return bool(della_fase) and della_fase[-1] is passo


def _passo_di_attesa(fase: Fase, ambiente: Ambiente, ora: datetime, avviato: datetime,
                     avanza: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    if not fase.attendi_ocr:
        return avanza("completato", "Nessun lavoro.")
    scaricati = ambiente.scarica_ai_locale() if ora == avviato else []
    in_coda = ambiente.ocr_in_coda()
    if in_coda and ora - avviato < ATTESA_OCR_MAX:
        nota = f" AI locale scaricata ({len(scaricati)} modelli)." if scaricati else ""
        return {"ok": True, "skipped": True, "message": f"Attesa della coda OCR: {in_coda} documenti.{nota}"}
    if in_coda:
        return avanza("completato", f"Coda OCR non vuota dopo 90 minuti ({in_coda}): si prosegue, il worker continua.",
                      (ora - avviato).total_seconds())
    return avanza("completato", "Coda OCR vuota.", (ora - avviato).total_seconds())
