"""Un passo della catena notturna per giro: il successivo parte solo quando il precedente è finito.

Il lavoro ``sequenza_notturna`` gira ogni minuto nella corsia notturna (un thread): ogni giro esegue al più un passo,
scrive l'esito nel registro e avanza. Così la catena si riprende da sola dopo un riavvio, aspetta la memoria e la
coda OCR, non avvia nulla dopo le 07:30, rinvia un passo che non ottiene il semaforo e ogni notte riparte dalla fase 1.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from pct.scheduler_notturno import finestra
from pct.scheduler_notturno.guardia import ATTESA_CATENA_SECONDI, LAVORO_IN_CORSO, SEMAFORO_OCCUPATO, esegui_in_catena
from pct.scheduler_notturno.registro import RegistroNotte
from pct.scheduler_notturno.sequenza import ATTESA_OCR_LETTURE, LAVORI_ANCHE_DI_GIORNO, Fase, Passo, passi_in_ordine

logger = logging.getLogger(__name__)

ATTESA_MEMORIA_MAX = timedelta(minutes=20)
ATTESA_OCR_MAX = timedelta(minutes=90)
# Un passo che non ottiene il semaforo dei motori entro questo tempo si rinvia e la catena prosegue: nella notte
# del 04/11/2026 un passo in attesa del semaforo ha fermato la catena dalle 05:08 alle 07:30.
ATTESA_SEMAFORO_PASSO_MAX = timedelta(seconds=ATTESA_CATENA_SECONDI)


@dataclass
class Ambiente:
    """Ciò che la catena usa dal mondo esterno (sostituibile nei test)."""

    trova_lavoro: Callable[[str], Any]
    memoria_libera_mb: Callable[[], int]
    ocr_in_coda: Callable[[], int | None]
    scarica_ai_locale: Callable[[], list[str]]
    ultimo_giro: Callable[[str], dict[str, Any]] | None = None


def _iso(m: datetime) -> str:
    return m.isoformat(timespec="seconds")


# Numeri dell'esito che descrivono la configurazione del giro, non il lavoro svolto o rimasto.
_NON_LAVORO = frozenset({"limite", "limite_oggetti", "studi", "tenant", "fascicoli", "errori"})
def _niente_da_fare(esito: Any) -> bool:
    """Per i passi ripetuti: il giro non ha trovato lavoro (nessun conteggio di lavoro positivo nell'esito).

    I conteggi si leggono dai ``totals`` quando l'esito li ha: «limite» (100) e «studi» (1) erano numeri
    sempre positivi in cima all'esito e il recupero delle PEC si ripeteva a vuoto per 40 minuti ogni notte.
    """
    if not esito or not isinstance(esito, dict) or esito.get("skipped") or esito.get("ok") is False:
        return True
    conteggi = esito["totals"] if isinstance(esito.get("totals"), dict) else esito
    residuo = conteggi.get("restano")
    if isinstance(residuo, (int, float)) and not isinstance(residuo, bool):
        return residuo <= 0 or esito.get("status") == "parziale"
    numeri = [v for k, v in conteggi.items()
              if k not in _NON_LAVORO and isinstance(v, (int, float)) and not isinstance(v, bool)]
    return not any(v > 0 for v in numeri)


def _giro_periodico_valido(ambiente: Ambiente, passo: Passo, avviato: datetime, ora: datetime) -> dict[str, Any]:
    """Riusare il giro periodico riuscito durante questo passo della sequenza."""
    if ambiente.ultimo_giro is None or passo.lavoro not in LAVORI_ANCHE_DI_GIORNO:
        return {}
    giro = ambiente.ultimo_giro(passo.lavoro)
    result = giro.get("result") or {}
    if giro.get("origin") != "scheduler" or result.get("job") != passo.lavoro:
        return {}
    if result.get("ok") is not True or result.get("skipped") or result.get("status") == "parziale":
        return {}
    modi = str(result.get("scan_mode") or "").removeprefix("mixed:").split(",")
    if "not_started" in modi:
        return {}
    totali = result.get("totals") or result
    if any(totali.get(campo) for campo in ("errors", "errori", "warnings", "skipped")):
        return {}
    try:
        pianificato = datetime.fromisoformat(giro["scheduled_at"])
        if pianificato.tzinfo is None:
            pianificato = pianificato.replace(tzinfo=finestra.ROME_TZ)
        concluso = datetime.fromisoformat(giro["finished_at"])
        if concluso.tzinfo is None:
            concluso = concluso.replace(tzinfo=UTC)
        if avviato <= pianificato <= concluso <= ora:
            return giro
    except (KeyError, ValueError, TypeError):
        return {}
    return {}


def _esegui_lavoro(
    job: Any, passo: Passo, limite: datetime, adesso: Callable[[], datetime],
    *, risultato: dict[str, Any] | None = None, attesa_massima: float = ATTESA_CATENA_SECONDI,
) -> tuple[str, str]:
    esito = esegui_in_catena(
        job.func, list(job.args or []), dict(job.kwargs or {}), attesa_massima=attesa_massima,
    )
    if not isinstance(esito, dict):
        return "fallito", "Il lavoro non ha restituito un riscontro verificabile."
    if risultato is not None:
        contatori = esito["totals"] if isinstance(esito.get("totals"), dict) else esito
        risultato["totals"] = {k: v for k, v in contatori.items() if isinstance(v, (int, float, bool))}
        for chiave in ("status", "reason", "mode", "source_of_truth", "scan_mode"):
            valore = esito.get(chiave)
            if isinstance(valore, str):
                risultato[chiave] = valore[:240]
    if esito.get("reason") in {SEMAFORO_OCCUPATO, LAVORO_IN_CORSO}:
        return "attesa", str(esito.get("message") or "Risorsa occupata.")
    dettaglio = esito.get("message") or esito.get("summary")
    if esito.get("ok") is False:
        return "fallito", str(esito.get("error") or dettaglio or "Esito negativo.")[:300]

    messaggio = f"Giro eseguito. {dettaglio}"[:300] if dettaglio else "Giro eseguito."
    saltato = esito.get("skipped")
    if saltato is True or isinstance(saltato, str) and saltato:
        return "saltato", str(esito.get("message") or esito.get("reason") or "Nessuna esecuzione richiesta.")[:300]
    if passo.ripeti_minuti and not _niente_da_fare(esito):
        if adesso() < limite:
            return "in_corso", messaggio
        conteggi = esito["totals"] if isinstance(esito.get("totals"), dict) else esito
        restano = conteggi.get("restano")
        if isinstance(restano, (int, float)) and restano > 0:
            return "rinviato", f"Lavoro residuo in coda allo scadere della finestra del passo. {messaggio}"[:300]
    if esito.get("status") == "parziale":
        return "rinviato", f"Risultato parziale. {messaggio}"[:300]
    return "completato", messaggio


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
        # Ogni notte riparte dalla fase 1 (posta e PEC prima di tutto): ripartire dal passo rimasto la notte
        # prima saltava le fasi iniziali (notte del 04/11/2026). Si annota solo dove si era fermata.
        partenza, ripresa = 0, ""
        precedente = registro.ultima_notte_prima(sera)
        if precedente and not precedente["conclusa"]:
            ripresa = f"La notte del {precedente['sera']} si era fermata al passo {int(precedente['indice']) + 1}: si riparte dalla fase 1."
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
    risultato: dict[str, Any] = {}
    giri = list((registro.passo(sera, indice).get("risultato") or {}).get("giri") or [])

    def esito_documentato() -> dict[str, Any]:
        return {**(giri[-1] if giri else {}), "giri": giri} if giri else {}

    def avanza(esito: str, messaggio: str, secondi: float = 0.0) -> dict[str, Any]:
        fine = adesso()
        nuovo = indice + 1
        registro.scrivi_passo(sera, indice, fase.numero, passo.lavoro, esito, messaggio=messaggio,
                              avvio=_iso(avviato), fine=_iso(fine), secondi=secondi, memoria_libera_mb=memoria,
                              avanza=True, conclusa=nuovo >= totale, risultato=esito_documentato())
        if fase.usa_ai_locale and _ultimo_della_fase(passi, fase, passo):
            ambiente.scarica_ai_locale()
        return {"ok": esito != "fallito", "fase": fase.numero, "lavoro": passo.lavoro, "esito": esito,
                "message": messaggio, "passo": nuovo, "totale": totale,
                "avvio": _iso(avviato), "risultato": esito_documentato()}

    if passo.lavoro.startswith("__"):
        return _passo_di_attesa(fase, ambiente, ora, avviato, avanza, attendi_ocr=fase.attendi_ocr or passo.lavoro == ATTESA_OCR_LETTURE)
    sera_data = finestra.sera_della_notte(ora)
    if passo.giorni and sera_data.weekday() not in passo.giorni:
        return avanza("saltato", "Lavoro settimanale: non previsto stanotte.")
    mattina = sera_data + timedelta(days=1)
    if passo.mesi and (mattina.month not in passo.mesi or mattina.day != passo.giorno_mese):
        return avanza("saltato", "Lavoro periodico: non previsto per questa data.")
    job = ambiente.trova_lavoro(passo.esegue or passo.lavoro)
    if job is None or getattr(job, "next_run_time", True) is None:
        return avanza("spento", "Pianificazione spenta o non disponibile in questo processo.")
    if memoria and memoria < fase.memoria_minima_mb and ora - avviato < ATTESA_MEMORIA_MAX:
        return {"ok": True, "skipped": True, "message": f"In attesa di memoria libera ({memoria} MB)."}
    try:
        periodico = _giro_periodico_valido(ambiente, passo, avviato, ora)
    except Exception:
        logger.warning("[notte] Giro periodico non consultabile per %s", passo.lavoro, exc_info=True)
        periodico = {}
    if periodico:
        risultato_periodico = periodico["result"]
        contatori = risultato_periodico.get("totals") or risultato_periodico
        giri.append({"totals": {k: v for k, v in contatori.items() if isinstance(v, (int, float, bool))},
                     "mode": "riuso_giro_periodico", "run_id": str(periodico.get("run_id") or ""),
                     "source_of_truth": str(risultato_periodico.get("source_of_truth") or "")[:240]})
        return avanza("completato", "Usato il risultato del giro periodico concluso dopo l’avvio del passo.")
    inizio = time.monotonic()
    try:
        limite = finestra.scadenza(ora)
        if passo.ripeti_minuti:
            limite = min(limite, avviato + timedelta(minutes=passo.ripeti_minuti))
        scadenza_attesa = min(limite, avviato + ATTESA_SEMAFORO_PASSO_MAX)
        attesa_massima = max(0.0, (scadenza_attesa - ora).total_seconds())
        esito, messaggio = _esegui_lavoro(job, passo, limite, adesso, risultato=risultato, attesa_massima=attesa_massima)
    except Exception as exc:  # una fase che fallisce non blocca le successive
        logger.exception("[notte] Passo %s non riuscito", passo.lavoro)
        esito, messaggio = "fallito", f"{type(exc).__name__}: {str(exc)[:240]}"
    if esito == "attesa":
        fine_attesa = adesso()
        if fine_attesa >= scadenza_attesa:
            # Mai una catena ferma per un semaforo occupato: il passo si rinvia (resta il suo orario diurno).
            durata_attesa = (fine_attesa - avviato).total_seconds()
            return avanza("rinviato", f"Tempo di attesa del semaforo esaurito: passo rinviato. {messaggio}"[:300], durata_attesa)
        # Il passo non è stato eseguito: resta lo stesso e si riprova al giro successivo.
        return {"ok": True, "skipped": True, "message": f"In attesa del turno: {messaggio}"}
    if risultato:
        giri.append(risultato)
    if esito == "in_corso":
        # Rilascia la corsia notturna tra due lotti. Il registro conserva il passo per il prossimo minuto.
        registro.scrivi_passo(sera, indice, fase.numero, passo.lavoro, esito, messaggio=messaggio,
                              avvio=_iso(avviato), secondi=(adesso() - avviato).total_seconds(),
                              memoria_libera_mb=memoria, risultato=esito_documentato())
        return {"ok": True, "fase": fase.numero, "lavoro": passo.lavoro, "esito": esito, "message": messaggio}
    secondi = (adesso() - avviato).total_seconds() if passo.ripeti_minuti else time.monotonic() - inizio
    return avanza(esito, messaggio, secondi)


def _ultimo_della_fase(passi: list[tuple[Fase, Passo]], fase: Fase, passo: Passo) -> bool:
    della_fase = [p for f, p in passi if f.numero == fase.numero]
    return bool(della_fase) and della_fase[-1] is passo


def _passo_di_attesa(fase: Fase, ambiente: Ambiente, ora: datetime, avviato: datetime,
                     avanza: Callable[..., dict[str, Any]], *, attendi_ocr: bool = False) -> dict[str, Any]:
    if not attendi_ocr:
        return avanza("completato", "Nessun lavoro.")
    scaricati = ambiente.scarica_ai_locale() if ora == avviato else []
    in_coda = ambiente.ocr_in_coda()
    if in_coda is None:
        messaggio = "Coda OCR non verificabile. Lo scheduler riproverà a leggere il registro OCR."
        if ora - avviato >= ATTESA_OCR_MAX:
            return avanza("rinviato", messaggio, (ora - avviato).total_seconds())
        return {"ok": True, "skipped": True, "message": messaggio}
    if in_coda and ora - avviato < ATTESA_OCR_MAX:
        nota = f" AI locale scaricata ({len(scaricati)} modelli)." if scaricati else ""
        return {"ok": True, "skipped": True, "message": f"Attesa della coda OCR: {in_coda} documenti.{nota}"}
    if in_coda:
        return avanza("rinviato", f"Coda OCR non vuota dopo 90 minuti ({in_coda}): si prosegue, il worker continua.",
                      (ora - avviato).total_seconds())
    return avanza("completato", "Coda OCR vuota.", (ora - avviato).total_seconds())
