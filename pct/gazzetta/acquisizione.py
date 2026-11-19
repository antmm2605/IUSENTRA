"""Giro di lettura della Gazzetta Ufficiale: per ogni serie l'elenco degli ultimi 30 giorni, poi i sommari nuovi.

Si leggono solo i fascicoli non ancora in archivio (un fascicolo pubblicato non cambia; le rettifiche escono
in fascicoli successivi). Una serie che non risponde viene registrata con il motivo e non ferma le altre; il
giro ha un tempo massimo e riprende al giro successivo dai fascicoli mancanti.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any, Iterable

import requests

from pct.gazzetta.archivio import ArchivioGazzetta
from pct.gazzetta.serie import HOST_AMMESSI, SERIE, Serie
from pct.gazzetta.sommario import Fascicolo, SommarioIllegibile, atti_del_sommario, fascicoli_in_elenco
from pct.notiziario.feed import ROME_TZ
from pct.notiziario.rete import ErroreFonte, RequestGet, scarica

logger = logging.getLogger(__name__)

TEMPO_MASSIMO_GIRO = 150  # secondi
PAUSA_FRA_RICHIESTE = 0.3  # secondi, per non gravare sul sito istituzionale


def _iso(istante: datetime) -> str:
    return istante.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _messaggio(exc: BaseException) -> str:
    if isinstance(exc, (ErroreFonte, SommarioIllegibile)):
        return str(exc)
    return "La Gazzetta Ufficiale non ha restituito un contenuto leggibile."


def _leggi_fascicolo(archivio: ArchivioGazzetta, serie: Serie, fascicolo: Fascicolo, *, request_get: RequestGet, quando: str) -> int:
    url = serie.url_sommario(fascicolo.data, fascicolo.numero)
    righe = atti_del_sommario(serie, fascicolo, scarica(url, HOST_AMMESSI, request_get=request_get), acquisito_il=quando)
    if not righe:
        raise SommarioIllegibile("Il sommario non elenca alcun atto.")
    return archivio.salva_fascicolo(
        {"serie": serie.codice, "numero": fascicolo.numero, "data": fascicolo.data, "url_sommario": url, "letto_il": quando},
        righe,
    )


def _in_ordine_di_lettura(mancanti: dict[str, list[Fascicolo]]) -> list[tuple[str, Fascicolo]]:
    """Prima il fascicolo più recente di ogni serie, poi a turno i precedenti: nessuna serie resta indietro."""
    coda: list[tuple[str, Fascicolo]] = []
    profondita = max((len(v) for v in mancanti.values()), default=0)
    for indice in range(profondita):
        for codice, fascicoli in mancanti.items():
            if indice < len(fascicoli):
                coda.append((codice, fascicoli[indice]))
    return coda


def esegui_giro(
    archivio: ArchivioGazzetta,
    *,
    request_get: RequestGet = requests.get,
    adesso: datetime | None = None,
    tempo_massimo: int = TEMPO_MASSIMO_GIRO,
    serie: Iterable[Serie] = SERIE,
    pausa: float = PAUSA_FRA_RICHIESTE,
) -> dict[str, Any]:
    adesso = adesso or datetime.now(timezone.utc)
    quando = _iso(adesso)
    scadenza = time.monotonic() + tempo_massimo
    elenco_serie = {voce.codice: voce for voce in serie}
    esiti: dict[str, dict[str, Any]] = {
        codice: {"ok": True, "messaggio": "", "fascicoli_nuovi": 0, "atti_nuovi": 0, "errori": [], "rimasti": 0}
        for codice in elenco_serie
    }
    mancanti: dict[str, list[Fascicolo]] = {}
    for codice, voce in elenco_serie.items():
        try:
            elenco = fascicoli_in_elenco(voce, scarica(voce.url_elenco, HOST_AMMESSI, request_get=request_get))
            if not elenco:
                raise SommarioIllegibile("L'elenco ufficiale dei fascicoli degli ultimi 30 giorni è vuoto.")
            letti = archivio.fascicoli_letti(codice)
            mancanti[codice] = [fascicolo for fascicolo in elenco if fascicolo.chiave not in letti]
        except Exception as exc:  # una serie giù non ferma le altre
            logger.info("[gazzetta] elenco %s non letto: %s", codice, exc)
            esiti[codice].update(ok=False, messaggio=_messaggio(exc))
    for codice, fascicolo in _in_ordine_di_lettura(mancanti):
        if time.monotonic() >= scadenza:
            break
        esito = esiti[codice]
        try:
            esito["atti_nuovi"] += _leggi_fascicolo(archivio, elenco_serie[codice], fascicolo, request_get=request_get, quando=quando)
            esito["fascicoli_nuovi"] += 1
        except Exception as exc:
            logger.info("[gazzetta] sommario %s n. %s non letto: %s", codice, fascicolo.numero, exc)
            esito["errori"].append(f"fascicolo n. {fascicolo.numero} del {_data_it(fascicolo.data)}: {_messaggio(exc)}")
        if pausa:
            time.sleep(pausa)
    for codice, esito in esiti.items():
        if codice in mancanti:
            esito["rimasti"] = len(mancanti[codice]) - esito["fascicoli_nuovi"] - len(esito["errori"])
            if esito["errori"]:
                esito.update(ok=False, messaggio="Sommari non letti: " + "; ".join(esito["errori"][:3]))
            elif esito["rimasti"]:
                esito["messaggio"] = f"Lettura in corso: {esito['rimasti']} fascicoli ancora da leggere al prossimo giro."
        archivio.registra_esito(
            codice, ok=esito["ok"], quando=quando, messaggio=esito["messaggio"], completo=not esito["rimasti"],
        )
    archivio.pota(oggi=adesso.astimezone(ROME_TZ).date())
    return {
        "ok": all(esito["ok"] for esito in esiti.values()),
        "status": "completato",
        "fascicoli_nuovi": sum(esito["fascicoli_nuovi"] for esito in esiti.values()),
        "atti_nuovi": sum(esito["atti_nuovi"] for esito in esiti.values()),
        "serie_non_raggiungibili": sorted(codice for codice, esito in esiti.items() if not esito["ok"]),
        "esiti": esiti,
        "eseguito_il": quando,
    }


def _data_it(valore: str) -> str:
    anno, mese, giorno = (valore.split("-") + ["", ""])[:3]
    return f"{giorno}/{mese}/{anno}" if giorno else valore


__all__ = ["TEMPO_MASSIMO_GIRO", "esegui_giro"]
