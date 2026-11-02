"""Fonti del rito del lavoro che completano il registro ``fonti.py``: udienza, decisione, appello, Stato.

Ogni estratto riassume fedelmente il testo vigente scaricato da Normattiva in
Akoma Ntoso (``do/atto/caricaAKN`` con dataVigenza 02/11/2026, la stessa via di
``lex/normativa/biblioteca/normattiva_akn.py``) il 02/11/2026: c.p.c. (R.D.
1443/1940), R.D. 1611/1933 (testo unico sull'Avvocatura dello Stato).
"""

from __future__ import annotations

from typing import Any

from pct.procedura_fasi.fonti_provvedimenti import VERIFICA_AKN_0211

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?"
_CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"
_RD1611 = "urn:nir:stato:regio.decreto:1933-10-30;1611"


def _voce(norma: str, titolo: str, atto: str, art: str, estratto: str) -> dict[str, Any]:
    return {"norma": norma, "titolo": titolo, "url": f"{_NORMATTIVA}{atto}~art{art}", "verifica": VERIFICA_AKN_0211, "estratto": estratto}


FONTI_LAVORO: dict[str, dict[str, Any]] = {
    "cpc_417bis": _voce("art. 417-bis c.p.c.", "Rito del lavoro: difesa delle pubbliche amministrazioni", _CPC, "417bis",
        "Nelle controversie di lavoro dei dipendenti delle pubbliche amministrazioni (art. 413, quinto comma), limitatamente al "
        "giudizio di primo grado le amministrazioni possono stare in giudizio avvalendosi direttamente di propri dipendenti; per le "
        "amministrazioni statali ciò vale salvo che l'Avvocatura dello Stato competente per territorio assuma direttamente la trattazione."),
    "cpc_420": _voce("art. 420 c.p.c.", "Rito del lavoro: udienza di discussione della causa", _CPC, "420",
        "Nell'udienza fissata per la discussione il giudice interroga liberamente le parti presenti, tenta la conciliazione e formula "
        "una proposta transattiva o conciliativa; la mancata comparizione personale o il rifiuto della proposta senza giustificato "
        "motivo sono valutabili ai fini del giudizio. Se la causa è matura il giudice invita alla discussione e pronuncia sentenza; "
        "altrimenti ammette i mezzi di prova e ne dispone l'immediata assunzione."),
    "cpc_430": _voce("art. 430 c.p.c.", "Rito del lavoro: deposito della sentenza", _CPC, "430",
        "Quando la sentenza è depositata fuori udienza, il cancelliere ne dà immediata comunicazione alle parti."),
    "cpc_433": _voce("art. 433 c.p.c.", "Rito del lavoro: giudice d'appello", _CPC, "433",
        "L'appello contro le sentenze pronunciate nelle controversie dell'art. 409 si propone con ricorso davanti alla corte di "
        "appello territorialmente competente in funzione di giudice del lavoro."),
    "rd1611_art11": _voce("R.D. 1611/1933, art. 11", "Notificazioni alle amministrazioni dello Stato", _RD1611, "11",
        "Le citazioni, i ricorsi e ogni atto istitutivo di giudizio devono essere notificati alle amministrazioni dello Stato presso "
        "l'ufficio dell'Avvocatura dello Stato nel cui distretto ha sede l'autorità giudiziaria adita, nella persona del Ministro "
        "competente; gli altri atti giudiziali e le sentenze presso l'Avvocatura del distretto in cui pende la causa o che ha "
        "pronunciato la sentenza, a pena di nullità rilevabile d'ufficio."),
}

__all__ = ["FONTI_LAVORO"]
