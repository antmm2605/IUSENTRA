"""Il decreto di trattazione scritta (art. 127-ter c.p.c.) come caso dello strato generico.

Il decreto che sostituisce «l'udienza già fissata» senza scriverne la data è già letto da
``pct/note_127_ter`` (udienza del fascicolo, bozza alle 09:30, checklist delle note,
equivalenze nello scadenziario): qui il suo esito si traduce in voci, con gli stessi
identificativi di regola usati dai passaggi (``127ter.*``), senza ricalcolare nulla.

Il decreto con una data propria («termine sino al 15/01/2027») è letto dai capi del
dispositivo; qui gli si dà il codice del termine per le note (``NOTE_127_TER``) e si
controlla il termine minimo di quindici giorni dalla comunicazione (art. 127-ter,
comma 1, c.p.c.), abbreviabile solo per urgenza dichiarata.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from typing import Any

from pct.note_127_ter import riconosci_decreto
from pct.note_127_ter.esame_pec import EsitoDecretoNote, esamina_decreto_pec
from pct.note_127_ter.proposta import CODICE_NOTE_127_TER, TITOLO_NOTE_127_TER

from .modello import Voce

_PROVA_SENZA_DATA = "assegna alle parti termine perentorio sino alla data della predetta udienza"


def _voci_da_esito(esito: EsitoDecretoNote) -> list[Voce]:
    voci: list[Voce] = []
    udienza = esito.udienza
    if udienza is not None and udienza.giorno is not None:
        voci.append(Voce("127ter.udienza_cartolare", "udienza", f"Udienza del {udienza.giorno:%d/%m/%Y} sostituita da note scritte",
                         norme=("cpc_127ter",), prova=_PROVA_SENZA_DATA, giorno=udienza.giorno, modalita="cartolare",
                         dati=(("Udienza", f"{udienza.giorno:%d/%m/%Y}", "agenda e scadenziario del fascicolo"),),
                         confidenza=0.9, id_appuntamento=udienza.id_appuntamento))
    for proposta in esito.proposte:
        giorno = date.fromisoformat(proposta.due_date)
        voci.append(Voce("127ter.termine_note", "termine", TITOLO_NOTE_127_TER, norme=("cpc_127ter", "dispatt_196sexies"),
                         prova=_PROVA_SENZA_DATA, giorno=giorno, ora=proposta.ora, perentorio=True, chi="parti",
                         nota=proposta.note, codice=CODICE_NOTE_127_TER, tipo_termine=proposta.tipo_termine,
                         dies_a_quo=date.fromisoformat(proposta.dies_a_quo), scadenziario=True, confidenza=0.9,
                         id_appuntamento=proposta.id_appuntamento, campi_scadenza=dict(proposta.campi_scadenza)))
    if esito.equivalente_id:
        voci.append(Voce("127ter.termine_equivalente", "verifica", "Termine per le note già presente nello scadenziario",
                         norme=("cpc_127ter",), prova=_PROVA_SENZA_DATA, confidenza=0.9,
                         dati=(("Scadenza esistente", esito.equivalente_id, "scadenziario"),)))
    if esito.da_verificare:
        voci.append(Voce("127ter.udienza_sostituita", "da_verificare", "Quale udienza sostituisce il decreto di trattazione scritta",
                         norme=("cpc_127ter",), prova=_PROVA_SENZA_DATA, domanda=esito.da_verificare, confidenza=0.5))
    for voce in esito.adempimenti:
        voci.append(Voce(f"127ter.adempimento.{voce.codice}", "attesa" if voce.codice == "decisione" else "adempimento",
                         voce.testo, norme=voce.fonti, prova=voce.dettaglio[:300], confidenza=0.85))
    return voci


def esamina_127_ter_senza_data(
    testo: str, *, oggi: date, comunicata_il: date | None, fascicolo_id: str, rg: str, ufficio: str, giudice: str,
    prossima_udienza: Any, appuntamenti: Iterable[Any], scadenze: Iterable[Any], opposizione_proposta: bool,
) -> tuple[list[Voce], EsitoDecretoNote | None]:
    """Le voci del decreto senza data propria, oppure ([], None) se il decreto ha la sua data."""
    esito = esamina_decreto_pec(
        testo, oggi=oggi, comunicata_il=comunicata_il, fascicolo_id=fascicolo_id, rg=rg, ufficio=ufficio, giudice=giudice,
        prossima_udienza=prossima_udienza, appuntamenti=appuntamenti, scadenze=scadenze, opposizione_proposta=opposizione_proposta,
    )
    if esito is None:
        return [], None
    return _voci_da_esito(esito), esito


def adatta_note_con_data(voci: list[Voce], *, testo: str, comunicata_il: date | None) -> list[Voce]:
    """Il termine per le note scritto dal giudice diventa ``NOTE_127_TER``; termine minimo di 15 giorni."""
    decreto = riconosci_decreto(testo)
    if decreto is None:
        return voci
    adattate: list[Voce] = []
    for voce in voci:
        if voce.regola_id == "giudice.note" and voce.genere == "termine" and voce.giorno is not None:
            ora = decreto.ora_limite or voce.ora or "23:59"
            voce = replace(voce, regola_id="127ter.termine_note", titolo=TITOLO_NOTE_127_TER, codice=CODICE_NOTE_127_TER,
                           tipo_termine="TERMINE_PERENTORIO", perentorio=True, norme=("cpc_127ter", "dispatt_196sexies"), ora=ora,
                           campi_scadenza={"operational_due_at": f"{voce.giorno.isoformat()}T{ora}:00", "hearing_mode": "note_scritte",
                                           "hearing_mode_source": "decreto ex art. 127-ter c.p.c."})
            if comunicata_il is not None and (voce.giorno - comunicata_il).days < 15:
                adattate.append(Voce("127ter.termine_minimo", "verifica",
                                     f"Termine per le note inferiore a quindici giorni dalla comunicazione ({comunicata_il:%d/%m/%Y}): "
                                     "verificare se il decreto dichiara ragioni di urgenza",
                                     norme=("cpc_127ter",), prova=voce.prova, confidenza=0.8, giorno=voce.giorno))
        adattate.append(voce)
    return adattate


__all__ = ["adatta_note_con_data", "esamina_127_ter_senza_data"]
