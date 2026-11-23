"""Recupero storico della Gazzetta Ufficiale dal 01/01/2022: sommari di tutte le serie e testi completi degli atti.

Riusa l'acquisitore dei sommari (``acquisizione._leggi_fascicolo``) e aggiunge due fonti ufficiali:
- l'archivio annuale di ogni serie, ``/ricercaArchivioCompleto/<serie>/<anno>`` (verificato il 21/11/2026 sulla
  Serie generale 2023: 303 fascicoli, con gli stessi collegamenti ``caricaDettaglio`` dell'elenco dei 30 giorni);
- il testo completo di ogni atto dalla navigazione ufficiale (``testo_atto.leggi_testo``).

Il recupero è a tratti: ogni tratto ha un tempo massimo e una pausa gentile fra una richiesta e l'altra; lo stato
è nell'archivio (fascicoli letti, anni completati, testi salvati, errori con i tentativi), quindi il tratto successivo
riprende da dove si era fermato. Ordine: prima i sommari (anno più recente, una serie alla volta a turno), poi i
testi (Serie generale e Corte costituzionale, poi Unione europea e Regioni, poi Concorsi e Contratti; dai più recenti).
Un anno passato si dichiara completo solo quando tutti i suoi fascicoli sono in archivio; l'anno in corso si rilegge
al più una volta al giorno.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import time
from typing import Any, Callable, Iterable

import requests

from pct.gazzetta.acquisizione import _iso, _leggi_fascicolo, _messaggio
from pct.gazzetta.archivio import DATA_INIZIO_ARCHIVIO, ArchivioGazzetta
from pct.gazzetta.serie import HOST_AMMESSI, SERIE, SITO, Serie
from pct.gazzetta.sommario import fascicoli_in_elenco
from pct.gazzetta.testo_atto import leggi_testo
from pct.notiziario.rete import RequestGet, scarica

logger = logging.getLogger(__name__)

PAUSA_GENTILE = 2.0  # secondi fra due richieste al sito istituzionale
TEMPO_TRATTO = 1200  # secondi per tratto nel lavoro pianificato
TENTATIVI_TESTO = 3
QUOTA_SOMMARI = 0.5  # parte del tratto per i sommari; il resto ai testi degli atti
INTESTAZIONI = {"User-Agent": "IUSENTRA archivio Gazzetta Ufficiale (consultazione professionale)"}


def url_anno(serie: Serie, anno: int) -> str:
    return f"{SITO}/ricercaArchivioCompleto/{serie.percorso}/{anno}"


def anni_da_recuperare(oggi: date) -> list[int]:
    return list(range(oggi.year, int(DATA_INIZIO_ARCHIVIO[:4]) - 1, -1))


def _sessione() -> requests.Session:
    sessione = requests.Session()
    sessione.headers.update(INTESTAZIONI)
    return sessione


def _anno_da_leggere(stato: dict[str, Any] | None, anno: int, oggi: date, adesso: datetime) -> bool:
    if stato is None:
        return True
    if anno < oggi.year:
        return not stato.get("completo")
    try:
        letto = datetime.fromisoformat(str(stato.get("letto_il") or "").replace("Z", "+00:00"))
    except ValueError:
        return True
    return adesso - letto >= timedelta(days=1)


def recupera_sommari(
    archivio: ArchivioGazzetta, *, request_get: RequestGet, adesso: datetime, scadenza: float, pausa: float,
    serie: Iterable[Serie] = SERIE, dormi: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Sommari dei fascicoli mancanti dal 01/01/2022, anno per anno dal più recente."""
    oggi = adesso.date()
    quando = _iso(adesso)
    esito = {"fascicoli_nuovi": 0, "atti_nuovi": 0, "errori": [], "completo": True}
    elenco_serie = list(serie)
    for anno in anni_da_recuperare(oggi):
        for voce in elenco_serie:
            if time.monotonic() >= scadenza:
                esito["completo"] = False
                return esito
            stato = archivio.anni_letti(voce.codice).get(anno)
            if not _anno_da_leggere(stato, anno, oggi, adesso):
                continue
            try:
                elenco = [f for f in fascicoli_in_elenco(voce, scarica(url_anno(voce, anno), HOST_AMMESSI, request_get=request_get))
                          if f.data >= DATA_INIZIO_ARCHIVIO and f.data[:4] == str(anno)]
            except Exception as exc:
                esito["errori"].append(f"{voce.codice} {anno}: {_messaggio(exc)}")
                esito["completo"] = False
                continue
            finally:
                if pausa:
                    dormi(pausa)
            letti = archivio.fascicoli_letti(voce.codice)
            mancanti = [f for f in elenco if f.chiave not in letti]
            errori = 0
            for fascicolo in mancanti:
                if time.monotonic() >= scadenza:
                    esito["completo"] = False
                    archivio.registra_anno(voce.codice, anno, fascicoli=len(elenco), completo=False, quando=quando)
                    return esito
                try:
                    esito["atti_nuovi"] += _leggi_fascicolo(archivio, voce, fascicolo, request_get=request_get, quando=quando)
                    esito["fascicoli_nuovi"] += 1
                except Exception as exc:
                    errori += 1
                    esito["errori"].append(f"{voce.codice} n. {fascicolo.numero} del {fascicolo.data}: {_messaggio(exc)}")
                if pausa:
                    dormi(pausa)
            completo = bool(elenco) and not errori
            esito["completo"] = esito["completo"] and completo
            archivio.registra_anno(voce.codice, anno, fascicoli=len(elenco), completo=completo, quando=quando)
    return esito


def recupera_testi(
    archivio: ArchivioGazzetta, *, adesso: datetime, scadenza: float, pausa: float,
    sessione_nuova: Callable[[], Any] = _sessione, dormi: Callable[[float], None] = time.sleep, lotto: int = 50,
) -> dict[str, Any]:
    """Testi completi degli atti che ancora non l'hanno, in ordine di priorità."""
    quando = _iso(adesso)
    esito = {"testi_nuovi": 0, "errori": 0, "completo": False}
    while time.monotonic() < scadenza:
        da_leggere = archivio.atti_senza_testo(limite=lotto, tentativi_massimi=TENTATIVI_TESTO)
        if not da_leggere:
            esito["completo"] = True
            break
        for atto in da_leggere:
            if time.monotonic() >= scadenza:
                break
            try:
                testo = leggi_testo(atto["url"], sessione=sessione_nuova())
                archivio.salva_testo(atto["id"], testo=testo.testo, intestazione=testo.intestazione, sha256=testo.sha256,
                                     url_testo=testo.url_testo, articoli=testo.articoli, letto_il=quando)
                esito["testi_nuovi"] += 1
            except Exception as exc:
                esito["errori"] += 1
                archivio.registra_errore_testo(atto["id"], messaggio=_messaggio(exc) if not str(exc) else str(exc), quando=quando)
                logger.info("[gazzetta] testo %s non letto: %s", atto["id"], exc)
            if pausa:
                dormi(pausa)
    return esito


def esegui_tratto(
    archivio: ArchivioGazzetta, *, request_get: RequestGet = requests.get, adesso: datetime | None = None,
    tempo_massimo: float = TEMPO_TRATTO, pausa: float = PAUSA_GENTILE, serie: Iterable[Serie] = SERIE,
    sessione_nuova: Callable[[], Any] = _sessione, dormi: Callable[[float], None] = time.sleep, con_testi: bool = True,
) -> dict[str, Any]:
    """Un tratto del recupero storico: sommari mancanti, poi testi, fino al tempo massimo."""
    adesso = adesso or datetime.now(timezone.utc)
    inizio = time.monotonic()
    scadenza = inizio + tempo_massimo
    # Ai sommari spetta al più una parte del tratto: prima della 2.490.3 li leggeva per tutto il tempo finché non
    # erano completi (migliaia di fascicoli), e i testi degli atti non arrivavano mai (collaudo 21/11/2026:
    # «testi_nuovi» sempre 0). Il tempo che i sommari non usano passa ai testi.
    scadenza_sommari = inizio + tempo_massimo * (QUOTA_SOMMARI if con_testi else 1.0)
    sommari = recupera_sommari(archivio, request_get=request_get, adesso=adesso, scadenza=scadenza_sommari, pausa=pausa,
                               serie=serie, dormi=dormi)
    testi = recupera_testi(archivio, adesso=adesso, scadenza=scadenza, pausa=pausa, sessione_nuova=sessione_nuova,
                           dormi=dormi) if con_testi else {"testi_nuovi": 0, "errori": 0, "completo": False}
    return {"ok": True, "sommari": sommari, "testi": testi, "copertura": archivio.copertura(), "eseguito_il": _iso(adesso)}


__all__ = ["PAUSA_GENTILE", "TEMPO_TRATTO", "anni_da_recuperare", "esegui_tratto", "recupera_sommari", "recupera_testi", "url_anno"]
