"""I tratti di un capoverso: dove, dentro la riga, il formato cambia.

Il formato del blocco dice com'e' scritto il capoverso nel suo insieme. Ma in
un atto il formato che conta sta spesso *dentro* la frase: il nome della parte
in neretto, il «rigetta» sottolineato, l'articolo di legge in corsivo, il
passaggio barrato in una bozza, l'indirizzo PEC in blu. Ridotto al formato del
blocco tutto questo sparisce, e l'avvocato lo deve rimettere a mano.

Un tratto e' un pezzo del testo del blocco con un formato uniforme. I tratti,
messi in fila, ridanno esattamente il testo del blocco — spazi compresi — e
quando il testo cambia (le correzioni forensi, la revisione) i tratti si
riallineano sulle parole, non sulle posizioni.

Si costruiscono solo dove il formato e' dichiarato dal documento: il testo
vero di un PDF dichiara stile e colore di ogni parola, e le sottolineature
sono linee disegnate che si possono misurare. Da una scansione il formato di
una singola parola non si legge con sicurezza — un neretto stimato parola per
parola sarebbe rumore — e li' resta il formato del blocco.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

#: Cio' che un tratto dichiara. Carattere e corpo restano del capoverso: dentro
#: una riga cambiano quasi mai, e quando cambiano e' un'altra riga.
CHIAVI_TRATTO = ("grassetto", "corsivo", "sottolineato", "barrato", "colore")

_RE_PEZZI = re.compile(r"\S+|\s+")


def _stile(parola: dict[str, Any]) -> tuple:
    return (
        bool(parola.get("grassetto")),
        bool(parola.get("corsivo")),
        bool(parola.get("sottolineato")),
        bool(parola.get("barrato")),
        str(parola.get("colore") or ""),
    )


def _comune(prima: tuple, dopo: tuple) -> tuple:
    """Lo stile dello spazio fra due parole diverse: solo quello che hanno in comune.

    Lo spazio fra una parola sottolineata e una no non e' sottolineato: in
    Word si vedrebbe la riga sporgere nel vuoto.
    """
    return (
        prima[0] and dopo[0],
        prima[1] and dopo[1],
        prima[2] and dopo[2],
        prima[3] and dopo[3],
        prima[4] if prima[4] == dopo[4] else "",
    )


def _dentro(parola: dict[str, Any], riquadro: Sequence[float]) -> bool:
    sinistra, alto, destra, basso = (float(valore) for valore in riquadro)
    x = float(parola.get("left") or 0) + float(parola.get("width") or 0) / 2
    y = float(parola.get("top") or 0) + float(parola.get("height") or 0) / 2
    return sinistra <= x <= destra and alto <= y <= basso


def _normale(testo: str) -> str:
    return re.sub(r"\W+", "", testo.lower())


def tratti_del_testo(testo: str, parole: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """I tratti di `testo`, con lo stile delle parole da cui viene.

    Le parole si abbinano al testo con un confronto di sequenze, non per
    posizione: le correzioni forensi possono aver unito «art . 183» in «art.
    183», il marcatore di un elenco puo' essere stato tolto, una parola
    spezzata a fine riga ricomposta. Una parola del testo che non trova la sua
    prende lo stile di quella prima.

    Ritorna una lista vuota quando il formato e' uniforme: basta quello del
    blocco, e il documento non si riempie di etichette che non dicono niente.
    """
    if not testo or not parole:
        return []
    ordinate = sorted(parole, key=lambda parola: int(parola.get("word") or 0))
    pezzi = _RE_PEZZI.findall(testo)
    indici_parole = [indice for indice, pezzo in enumerate(pezzi) if not pezzo.isspace()]
    stili: list[tuple | None] = [None] * len(pezzi)

    confronto = SequenceMatcher(
        None,
        [_normale(pezzi[indice]) for indice in indici_parole],
        [_normale(str(parola.get("text") or "")) for parola in ordinate],
        autojunk=False,
    )
    for blocco in confronto.get_matching_blocks():
        for scarto in range(blocco.size):
            stili[indici_parole[blocco.a + scarto]] = _stile(ordinate[blocco.b + scarto])

    # chi non ha trovato la propria parola prende lo stile di quella prima
    # (o della prima abbinata, se e' in testa al blocco)
    abbinati = [stili[indice] for indice in indici_parole if stili[indice] is not None]
    if not abbinati:
        return []
    precedente = abbinati[0]
    for indice in indici_parole:
        if stili[indice] is None:
            stili[indice] = precedente
        precedente = stili[indice]

    # gli spazi prendono quello che le due parole accanto hanno in comune
    for indice, pezzo in enumerate(pezzi):
        if not pezzo.isspace():
            continue
        prima = next((stili[i] for i in range(indice - 1, -1, -1) if stili[i] is not None and not pezzi[i].isspace()), None)
        dopo = next((stili[i] for i in range(indice + 1, len(pezzi)) if stili[i] is not None and not pezzi[i].isspace()), None)
        stili[indice] = _comune(prima or dopo, dopo or prima)  # type: ignore[arg-type]

    tratti: list[dict[str, Any]] = []
    for pezzo, stile in zip(pezzi, stili):
        if tratti and tuple(tratti[-1][chiave] for chiave in CHIAVI_TRATTO) == stile:
            tratti[-1]["testo"] += pezzo
            continue
        tratti.append({"testo": pezzo, **dict(zip(CHIAVI_TRATTO, stile))})  # type: ignore[arg-type]
    return tratti if len(tratti) > 1 else []


def con_tratti(blocchi: Sequence[dict[str, Any]], parole: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """I blocchi della pagina, ciascuno con i propri tratti quando ne ha.

    Le tabelle restano fuori: le loro celle si correggono una per una e il
    formato dentro la cella non passa dalla revisione.
    """
    fuori: list[dict[str, Any]] = []
    for blocco in blocchi:
        voce = dict(blocco)
        testo = str(voce.get("testo") or "")
        riquadro = voce.get("riquadro")
        if voce.get("tipo") != "tabella" and testo and riquadro and len(riquadro) == 4:
            proprie = [parola for parola in parole if _dentro(parola, riquadro)]
            tratti = tratti_del_testo(testo, proprie)
            if tratti:
                voce["tratti"] = tratti
        fuori.append(voce)
    return fuori


__all__ = ["CHIAVI_TRATTO", "con_tratti", "tratti_del_testo"]
