"""Fonti dei riti speciali che la Lettura riconosce dal codice oggetto e dagli atti: monitorio, esecuzione, volontaria.

Testo vigente letto il 10/11/2026 dall'archivio Normattiva del software (R.D. 1443/1940, c.p.c.), comando
``norma.sh "art. N r.d. 1443/1940"``. Ogni estratto riassume fedelmente l'articolo; le voci già presenti nel
registro ``fonti.py`` non vengono sostituite.
"""

from __future__ import annotations

from typing import Any

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?"
_CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"
VERIFICA_ARCHIVIO_1011 = "testo vigente letto nell'archivio Normattiva del software il 10/11/2026"


def _voce(norma: str, titolo: str, art: str, estratto: str) -> dict[str, Any]:
    return {"norma": norma, "titolo": titolo, "url": f"{_NORMATTIVA}{_CPC}~art{art}", "verifica": VERIFICA_ARCHIVIO_1011,
            "estratto": estratto}


FONTI_RITI_SPECIALI: dict[str, dict[str, Any]] = {
    "cpc_633": _voce("art. 633 c.p.c.", "Procedimento d'ingiunzione: condizioni di ammissibilità", "633",
        "Su domanda di chi è creditore di una somma liquida di danaro, di una quantità di cose fungibili o della consegna di una "
        "cosa mobile determinata, il giudice pronuncia ingiunzione se del diritto si dà prova scritta (e negli altri casi dell'articolo). "
        "Il procedimento si svolge senza udienza: il decreto è pronunciato sul ricorso."),
    "cpc_645": _voce("art. 645 c.p.c.", "Opposizione al decreto ingiuntivo", "645",
        "L'opposizione si propone davanti all'ufficio giudiziario del giudice che ha emesso il decreto; l'atto è notificato al "
        "ricorrente e in seguito all'opposizione il giudizio si svolge secondo le norme del processo di cognizione."),
    "cpc_654": _voce("art. 654 c.p.c.", "Dichiarazione di esecutorietà ed esecuzione del decreto ingiuntivo", "654",
        "L'esecutorietà non disposta è conferita con decreto del giudice che ha pronunciato l'ingiunzione. Ai fini dell'esecuzione "
        "non occorre una nuova notificazione del decreto esecutivo, ma nel precetto deve farsi menzione del provvedimento che ha "
        "disposto l'esecutorietà."),
    "cpc_474": _voce("art. 474 c.p.c.", "Titolo esecutivo", "474",
        "L'esecuzione forzata non può avere luogo che in virtù di un titolo esecutivo per un diritto certo, liquido ed esigibile; "
        "sono titoli esecutivi le sentenze, i provvedimenti e gli altri atti ai quali la legge attribuisce efficacia esecutiva."),
    "cpc_547": _voce("art. 547 c.p.c.", "Espropriazione presso terzi: dichiarazione del terzo", "547",
        "Con raccomandata o PEC al creditore procedente il terzo deve specificare di quali cose o somme è debitore o si trova in "
        "possesso e quando ne deve eseguire il pagamento o la consegna."),
    "cpc_548": _voce("art. 548 c.p.c.", "Espropriazione presso terzi: mancata dichiarazione del terzo", "548",
        "Se all'udienza il creditore dichiara di non aver ricevuto la dichiarazione, il giudice fissa un'udienza successiva con "
        "ordinanza notificata al terzo almeno dieci giorni prima; se il terzo non compare o rifiuta la dichiarazione, il credito "
        "si considera non contestato e il giudice provvede all'assegnazione (artt. 552-553)."),
    "cpc_631": _voce("art. 631 c.p.c.", "Processo esecutivo: mancata comparizione all'udienza", "631",
        "Se nel corso del processo esecutivo nessuna delle parti si presenta all'udienza (salvo quella della vendita), il giudice "
        "dell'esecuzione fissa un'udienza successiva comunicata dal cancelliere; se nessuna parte si presenta alla nuova udienza, "
        "il giudice dichiara con ordinanza l'estinzione del processo esecutivo."),
    "cpc_737":_voce("art. 737 c.p.c.", "Procedimenti in camera di consiglio: forma della domanda e del provvedimento", "737",
        "I provvedimenti che debbono essere pronunciati in camera di consiglio si chiedono con ricorso al giudice competente e "
        "hanno forma di decreto motivato, salvo che la legge disponga altrimenti."),
    "cpc_739": _voce("art. 739 c.p.c.", "Procedimenti in camera di consiglio: reclamo", "739",
        "Contro i decreti del giudice tutelare si può proporre reclamo al tribunale e contro i decreti del tribunale in camera di "
        "consiglio alla corte d'appello, nel termine perentorio di dieci giorni dalla comunicazione del decreto (se dato in "
        "confronto di una sola parte) o dalla notificazione (se dato in confronto di più parti)."),
    "cpc_742": _voce("art. 742 c.p.c.", "Procedimenti in camera di consiglio: revocabilità", "742",
        "I decreti possono essere in ogni tempo modificati o revocati, salvi i diritti acquistati in buona fede dai terzi."),
}

__all__ = ["FONTI_RITI_SPECIALI", "VERIFICA_ARCHIVIO_1011"]
