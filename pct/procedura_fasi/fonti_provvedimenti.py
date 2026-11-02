"""Fonti delle regole che leggono i provvedimenti del giudice (``pct/provvedimenti``).

Le voci completano il registro ``fonti.py`` con le norme che fissano, per legge, i
termini e le forme che seguono un provvedimento quando il provvedimento non li
scrive: intimazione dei testimoni, consulenza tecnica, udienza da remoto, rito
della famiglia, appello del lavoro, udienza amministrativa e tributaria, lista
testimoniale nel dibattimento penale.

Ogni estratto riassume fedelmente il testo vigente scaricato da Normattiva in
Akoma Ntoso (``do/atto/caricaAKN`` con dataVigenza 02/11/2026, la stessa via di
``lex/normativa/biblioteca/normattiva_akn.py``) il 02/11/2026. Per il processo
tributario vale il Testo unico D.Lgs. 175/2024 (artt. 79-81, già artt. 31-33
D.Lgs. 546/1992, abrogato dall'art. 130 del Testo unico).
"""

from __future__ import annotations

from typing import Any

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?"
_CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"
_DISP_ATT = "urn:nir:stato:regio.decreto:1941-12-18;1368"
_CPP = "urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447"
_CPA = "urn:nir:stato:decreto.legislativo:2010-07-02;104"
_TU_TRIB = "urn:nir:stato:decreto.legislativo:2024-11-14;175"

VERIFICA_AKN_0211 = "testo vigente scaricato da Normattiva in Akoma Ntoso (vigenza 02/11/2026) e letto il 02/11/2026"


def _voce(norma: str, titolo: str, atto: str, art: str, estratto: str) -> dict[str, Any]:
    return {"norma": norma, "titolo": titolo, "url": f"{_NORMATTIVA}{atto}~art{art}", "verifica": VERIFICA_AKN_0211, "estratto": estratto}


FONTI_PROVVEDIMENTI: dict[str, dict[str, Any]] = {
    "cpc_127bis": _voce("art. 127-bis c.p.c.", "Udienza mediante collegamenti audiovisivi", _CPC, "127bis",
        "Lo svolgimento dell'udienza mediante collegamenti audiovisivi a distanza può essere disposto dal giudice quando non è "
        "richiesta la presenza di soggetti diversi dai difensori, dalle parti, dal pubblico ministero e dagli ausiliari. Il "
        "provvedimento è comunicato alle parti almeno quindici giorni prima dell'udienza; ciascuna parte costituita, entro cinque "
        "giorni dalla comunicazione, può chiedere che l'udienza si svolga in presenza."),
    "cpc_134": _voce("art. 134 c.p.c.", "Forma, contenuto e comunicazione dell'ordinanza", _CPC, "134",
        "L'ordinanza è succintamente motivata; se è pronunciata fuori dell'udienza è redatta su documento separato, con data e "
        "sottoscrizione del giudice, e il cancelliere la comunica alle parti, salvo che la legge ne prescriva la notificazione."),
    "cpc_175": _voce("art. 175 c.p.c.", "Direzione del procedimento", _CPC, "175",
        "Il giudice istruttore esercita tutti i poteri intesi al più sollecito e leale svolgimento del procedimento; egli fissa "
        "le udienze successive e i termini entro i quali le parti debbono compiere gli atti processuali."),
    "cpc_191": _voce("art. 191 c.p.c.", "Nomina del consulente tecnico", _CPC, "191",
        "Il giudice istruttore, con l'ordinanza dell'art. 183, quarto comma, o con altra successiva ordinanza, nomina un "
        "consulente, formula i quesiti e fissa l'udienza nella quale il consulente deve comparire."),
    "cpc_193": _voce("art. 193 c.p.c.", "Giuramento del consulente", _CPC, "193",
        "All'udienza di comparizione il giudice riceve il giuramento del consulente; in luogo dell'udienza può assegnare un "
        "termine per il deposito di una dichiarazione sottoscritta con firma digitale recante il giuramento, fissando con il "
        "medesimo provvedimento i termini dell'art. 195, terzo comma."),
    "cpc_195": _voce("art. 195 c.p.c.", "Processo verbale e relazione", _CPC, "195",
        "La relazione è trasmessa dal consulente alle parti costituite nel termine stabilito dal giudice; con la medesima "
        "ordinanza il giudice fissa il termine per le osservazioni delle parti e il termine, anteriore alla successiva udienza, "
        "per il deposito della relazione, delle osservazioni e di una sintetica valutazione sulle stesse."),
    "cpc_201": _voce("art. 201 c.p.c.", "Consulente tecnico di parte", _CPC, "201",
        "Il giudice istruttore, con l'ordinanza di nomina del consulente, assegna alle parti un termine entro il quale possono "
        "depositare la dichiarazione di nomina di un loro consulente tecnico."),
    "cpc_250": _voce("art. 250 c.p.c.", "Intimazione ai testimoni", _CPC, "250",
        "L'ufficiale giudiziario, su richiesta della parte, intima ai testimoni ammessi di comparire nel luogo, giorno e ora "
        "fissati; l'intimazione al testimone ammesso su richiesta delle parti private può essere effettuata dal difensore con "
        "raccomandata con avviso di ricevimento o PEC, e il difensore deposita copia dell'atto inviato e della ricevuta."),
    "dispatt_103": _voce("art. 103 disp. att. c.p.c.", "Termine per l'intimazione al testimone", _DISP_ATT, "103",
        "L'intimazione di cui all'art. 250 del codice deve essere fatta ai testimoni almeno sette giorni prima dell'udienza in "
        "cui sono chiamati a comparire; con l'autorizzazione del giudice il termine può essere ridotto nei casi d'urgenza."),
    "cpc_434": _voce("art. 434 c.p.c.", "Rito del lavoro: deposito del ricorso in appello", _CPC, "434",
        "Il ricorso in appello deve essere depositato entro trenta giorni dalla notificazione della sentenza, oppure entro "
        "quaranta giorni se la notificazione è stata effettuata all'estero."),
    "cpc_473bis14": _voce("art. 473-bis.14 c.p.c.", "Rito della famiglia: deposito del ricorso e decreto di fissazione", _CPC, "473bis14",
        "Il presidente fissa l'udienza di prima comparizione assegnando il termine per la costituzione del convenuto, che deve "
        "avvenire almeno trenta giorni prima dell'udienza; ricorso e decreto sono notificati al convenuto a cura dell'attore e "
        "tra la notifica e l'udienza deve intercorrere un termine non inferiore a sessanta giorni liberi."),
    "cpc_473bis17": _voce("art. 473-bis.17 c.p.c.", "Rito della famiglia: ulteriori difese", _CPC, "473bis17",
        "Entro venti giorni prima dell'udienza l'attore può depositare memoria; entro dieci giorni prima il convenuto può "
        "depositare un'ulteriore memoria; entro cinque giorni prima l'attore può depositare memoria per le sole indicazioni di "
        "prova contraria."),
    "cpa_71": _voce("art. 71 c.p.a.", "Fissazione dell'udienza", _CPA, "71",
        "Il presidente, decorso il termine per la costituzione delle altre parti, fissa l'udienza di discussione; il decreto di "
        "fissazione è comunicato a cura della segreteria almeno sessanta giorni prima dell'udienza al ricorrente e alle parti "
        "costituite."),
    "cpa_73": _voce("art. 73 c.p.a.", "Udienza di discussione", _CPA, "73",
        "Le parti possono produrre documenti fino a quaranta giorni liberi prima dell'udienza, memorie fino a trenta giorni "
        "liberi e presentare repliche ai nuovi documenti e alle nuove memorie fino a venti giorni liberi."),
    "cpa_92_lungo": _voce("art. 92, comma 3, c.p.a.", "Termine lungo per le impugnazioni", _CPA, "92",
        "In difetto della notificazione della sentenza, l'appello, la revocazione per i nn. 4 e 5 dell'art. 395 c.p.c. e il "
        "ricorso per cassazione devono essere notificati entro sei mesi dalla pubblicazione della sentenza."),
    "tu175_art79": _voce("D.Lgs. 175/2024, art. 79", "Avviso di trattazione (ex art. 31 D.Lgs. 546/1992)", _TU_TRIB, "79",
        "La segreteria dà comunicazione alle parti costituite della data di trattazione almeno trenta giorni liberi prima; "
        "uguale avviso è dato quando la trattazione è rinviata."),
    "tu175_art80": _voce("D.Lgs. 175/2024, art. 80", "Deposito di documenti e di memorie (ex art. 32 D.Lgs. 546/1992)", _TU_TRIB, "80",
        "Le parti possono depositare documenti fino a venti giorni liberi prima della data di trattazione e memorie illustrative "
        "fino a dieci giorni liberi prima; nel solo caso di trattazione in camera di consiglio sono consentite brevi repliche "
        "scritte fino a cinque giorni liberi prima."),
    "tu175_art81": _voce("D.Lgs. 175/2024, art. 81", "Trattazione in camera di consiglio (ex art. 33 D.Lgs. 546/1992)", _TU_TRIB, "81",
        "La controversia è trattata in camera di consiglio salvo che almeno una parte chieda la discussione in pubblica udienza, "
        "in presenza o da remoto, con istanza da notificare alle altre parti costituite entro il termine dell'art. 80, comma 2, "
        "e da depositare in segreteria con la prova della notificazione."),
    "cpp_468": _voce("art. 468 c.p.p.", "Citazione di testimoni, periti e consulenti tecnici", _CPP, "468",
        "Le parti che intendono chiedere l'esame di testimoni, periti o consulenti tecnici devono, a pena di inammissibilità, "
        "depositare in cancelleria, almeno sette giorni prima della data fissata per il dibattimento, la lista con l'indicazione "
        "delle circostanze su cui deve vertere l'esame."),
}

__all__ = ["FONTI_PROVVEDIMENTI", "VERIFICA_AKN_0211"]
