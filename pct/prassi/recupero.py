"""Recupero della prassi a tratti, con ripresa: prima gli elenchi (pagine non ancora lette), poi i testi.

Agenzia delle Entrate: le pagine d'archivio di un anno passato si leggono una volta sola; quelle dell'anno in corso
e le pagine iniziali a ogni tratto. INPS: l'elenco si scorre dalla prima pagina finché una pagina intera è già in
archivio (aggiornamento) o fino alla fine (prima volta). I testi: dal più recente, alternando i due enti.
"""
from __future__ import annotations

import json
import time
from datetime import date
from typing import Any, Callable

from pct.prassi import fonti
from pct.prassi.archivio import ArchivioPrassi
from pct.riprove_rete import ReteNonDisponibile, scarica_con_riprove

PAUSA = 2.0


_MESI = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"


def _da_rileggere(url: str) -> bool:
    """Le pagine di un mese passato non cambiano: si leggono una volta. Indici e anno in corso: sempre."""
    import re

    mese = re.search(rf"/(?:{_MESI})-(\d{{4}})", url)
    return not mese or int(mese.group(1)) >= date.today().year


def elenchi_ade(archivio: ArchivioPrassi, scarica: Callable[[str], Any], *, fine: float, pausa: float, dormi=time.sleep) -> int:
    da_visitare, visti, nuovi = list(fonti.ADE_PARTENZE), set(), 0
    while da_visitare and time.monotonic() < fine:
        url = da_visitare.pop(0)
        if url in visti:
            continue
        visti.add(url)
        if archivio.elenco_letto(url) and not _da_rileggere(url):
            continue
        try:
            risposta = scarica_con_riprove(scarica, url, dormi=dormi)
        except ReteNonDisponibile:
            continue  # pagina non registrata: si rilegge al giro successivo
        finally:
            if pausa:
                dormi(pausa)
        if int(getattr(risposta, "status_code", 200)) != 200:
            continue
        pagina = risposta.content.decode("utf-8", errors="replace")
        documenti = fonti.ade_documenti(pagina, url)
        nuovi += archivio.aggiungi(documenti)
        archivio.registra_elenco(url, len(documenti))
        da_visitare += [u for u in fonti.ade_collegamenti(pagina) if u not in visti]
    return nuovi


def elenchi_inps(archivio: ArchivioPrassi, scarica: Callable[[str], Any], *, fine: float, pausa: float, dormi=time.sleep) -> int:
    nuovi = 0
    completo = archivio.elenco_letto("inps:completo")
    pagina = 0 if completo else int(_stato(archivio, "inps:pagina") or 0)
    while time.monotonic() < fine:
        try:
            risposta = scarica_con_riprove(scarica, fonti.inps_url_elenco(pagina), dormi=dormi)
            voci = fonti.inps_documenti(json.loads(risposta.content))
        except (ReteNonDisponibile, ValueError):
            break  # la pagina resta da leggere: il giro passa ai testi, l'elenco riprende da qui al giro dopo
        finally:
            if pausa:
                dormi(pausa)
        if not voci:
            archivio.registra_elenco("inps:completo", pagina)
            break
        aggiunti = archivio.aggiungi(voci)
        nuovi += aggiunti
        if completo and not aggiunti:
            break  # aggiornamento: questa pagina era già tutta in archivio
        pagina += 1
        if not completo:
            archivio.registra_elenco(f"inps:pagina={pagina}", len(voci))
    return nuovi


def _stato(archivio: ArchivioPrassi, prefisso: str) -> str:
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(str(archivio.percorso))) as conn:
        righe = [r[0] for r in conn.execute("SELECT chiave FROM elenchi WHERE chiave LIKE ?", (prefisso + "=%",))]
    return str(max((int(r.split("=")[1]) for r in righe), default=0))


def testi(archivio: ArchivioPrassi, scarica: Callable[[str], Any], *, fine: float, pausa: float, dormi=time.sleep) -> dict[str, int]:
    esito = {"testi_nuovi": 0, "errori": 0, "da_ritentare": 0}
    rinviati: set[str] = set()
    while time.monotonic() < fine:
        coda = (archivio.da_leggere("Agenzia delle Entrate", 5, esclusi=rinviati)
                + archivio.da_leggere("INPS", 5, esclusi=rinviati))
        if not coda:
            break
        for doc in coda:
            if time.monotonic() >= fine:
                break
            try:
                risposta = scarica_con_riprove(scarica, doc["url_testo"], dormi=dormi)
                codice = int(getattr(risposta, "status_code", 200))
                if codice == 404:
                    archivio.errore(doc["id"], "documento non trovato (404)", definitivo=True)
                    esito["errori"] += 1
                    continue
                if codice != 200:
                    raise ValueError(f"risposta {codice}")
                if doc["ente"] == "INPS":
                    testo = fonti.inps_testo(json.loads(risposta.content),
                                             lambda url: scarica_con_riprove(scarica, url, dormi=dormi))
                else:
                    testo = fonti.testo_pdf(risposta.content)
                if len(testo) < 100:
                    archivio.errore(doc["id"], "testo non leggibile dalla fonte (PDF a immagini o scheda vuota)")
                    esito["errori"] += 1
                else:
                    archivio.salva_testo(doc["id"], testo)
                    esito["testi_nuovi"] += 1
            except ReteNonDisponibile as exc:
                # Fonte lenta o irraggiungibile: la voce resta da ritentare, il giro passa alla successiva.
                archivio.rinvia(doc["id"], str(exc))
                rinviati.add(doc["id"])
                esito["da_ritentare"] += 1
            except Exception as exc:
                archivio.errore(doc["id"], f"{type(exc).__name__}: {exc}")
                esito["errori"] += 1
            finally:
                if pausa:
                    dormi(pausa)
    return esito


def esegui_tratto(archivio: ArchivioPrassi, scarica: Callable[[str], Any], *, tempo_massimo: float = 1800,
                  pausa: float = PAUSA, dormi=time.sleep) -> dict[str, Any]:
    inizio = time.monotonic()
    meta = inizio + tempo_massimo * 0.4
    nuovi_ade = elenchi_ade(archivio, scarica, fine=inizio + tempo_massimo * 0.2, pausa=pausa, dormi=dormi)
    nuovi_inps = elenchi_inps(archivio, scarica, fine=meta, pausa=pausa, dormi=dormi)
    esito = testi(archivio, scarica, fine=inizio + tempo_massimo, pausa=pausa, dormi=dormi)
    return {"elenchi": {"agenzia_entrate": nuovi_ade, "inps": nuovi_inps}, **esito, "archivio": archivio.conteggi()}


__all__ = ["esegui_tratto"]
