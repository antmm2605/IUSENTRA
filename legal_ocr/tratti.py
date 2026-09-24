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

#: Cio' che un tratto dichiara. Il carattere resta del capoverso; il corpo no:
#: le intestazioni mettono nello stesso blocco righe di corpi diversi («TRIBUNALE
#: DI PALMI» a 16 punti, «Memoria ex art. 183» a 14), e gli apici dei rimandi
#: alle note sono piu' piccoli del testo.
CHIAVI_TRATTO = ("grassetto", "corsivo", "sottolineato", "barrato", "colore", "corpo")

_RE_PEZZI = re.compile(r"\S+|\s+")
_RE_PAROLE = re.compile(r"\S+")


def _stile(parola: dict[str, Any]) -> tuple:
    return (
        bool(parola.get("grassetto")),
        bool(parola.get("corsivo")),
        bool(parola.get("sottolineato")),
        bool(parola.get("barrato")),
        str(parola.get("colore") or ""),
        # il corpo in mezzi punti: le intestazioni mescolano righe di corpi diversi
        round(float(parola.get("corpo") or 0) * 2) / 2,
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
        min(prima[5], dopo[5]),
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


def _righe_visive(parole: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Le parole divise nelle righe come si vedono sulla pagina, dall'alto.

    Non si usano le righe dichiarate dal PDF: Word scrive il trattino di un
    elenco come una riga a parte, alla stessa altezza del testo che apre. Due
    parole stanno sulla stessa riga quando i loro centri distano meno di meta'
    della piu' bassa: una riga in corpo grande sotto una piccola resta sua.
    """
    def centro(parola: dict[str, Any]) -> float:
        return float(parola.get("top") or 0) + float(parola.get("height") or 0) / 2

    ordinate = sorted(parole, key=lambda parola: (centro(parola), float(parola.get("left") or 0)))
    righe: list[list[dict[str, Any]]] = []
    for parola in ordinate:
        if righe:
            riferimento = righe[-1]
            centro_riga = sum(centro(voce) for voce in riferimento) / len(riferimento)
            bassa = min([float(parola.get("height") or 0) or 1.0] + [float(voce.get("height") or 0) or 1.0 for voce in riferimento])
            if abs(centro(parola) - centro_riga) < bassa * 0.5:
                riferimento.append(parola)
                continue
        righe.append([parola])
    return [sorted(riga, key=lambda parola: float(parola.get("left") or 0)) for riga in righe]


def a_capo_del_testo(testo: str, parole: Sequence[dict[str, Any]]) -> list[int]:
    """Dove, nel testo del blocco, comincia ogni riga della pagina dopo la prima.

    Sono gli «a capo» del documento: il foglio della revisione li rispetta, e
    le righe cadono dove cadevano sull'originale anche quando il carattere del
    browser non e' identico a quello del PDF. Le parole si abbinano al testo
    come per i tratti; una riga che comincia con la coda di una parola
    sillabata (ricomposta nel testo) non da' un a capo.
    """
    if not testo or not parole:
        return []
    righe = _righe_visive(parole)
    if len(righe) < 2:
        return []
    sequenza = [parola for riga in righe for parola in riga]
    inizi_riga: set[int] = set()
    posizione = 0
    for riga in righe[:-1]:
        posizione += len(riga)
        inizi_riga.add(posizione)
    pezzi = [(corrispondenza.start(), corrispondenza.group()) for corrispondenza in _RE_PAROLE.finditer(testo)]
    confronto = SequenceMatcher(
        None,
        [_normale(pezzo) for _, pezzo in pezzi],
        [_normale(str(parola.get("text") or "")) for parola in sequenza],
        autojunk=False,
    )
    a_capo: list[int] = []
    for blocco in confronto.get_matching_blocks():
        for scarto in range(blocco.size):
            if blocco.b + scarto in inizi_riga and blocco.a + scarto > 0:
                a_capo.append(pezzi[blocco.a + scarto][0])
    return sorted(set(a_capo))


def con_tratti(blocchi: Sequence[dict[str, Any]], parole: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """I blocchi della pagina, ciascuno con i propri tratti quando ne ha.

    Le tabelle restano fuori: le loro celle si correggono una per una e il
    formato dentro la cella non passa dalla revisione.
    """
    # Il bordo destro della colonna: dove arrivano le righe piene dei capoversi
    # giustificati. Il massimo di tutta la pagina no: un timbro di firma a
    # destra, fuori dalla colonna, lo sposterebbe.
    def destra_di(blocco: dict[str, Any]) -> float:
        return float(blocco["riquadro"][2])

    testuali = [blocco for blocco in blocchi if blocco.get("tipo") != "tabella" and len(blocco.get("riquadro") or []) == 4]
    giustificati = sorted(destra_di(blocco) for blocco in testuali if (blocco.get("formato") or {}).get("allineamento") == "giustificato")
    if giustificati:
        colonna_destra = giustificati[len(giustificati) // 2]
    else:
        colonna_destra = max((destra_di(blocco) for blocco in testuali), default=0.0)
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
            a_capo = a_capo_del_testo(testo, proprie)
            if a_capo:
                voce["a_capo"] = a_capo
                # Le righe che arrivano al margine destro sono piene: si
                # giustificano (anche l'ultima, quando il capoverso continua
                # nella pagina dopo); le altre restano come sono.
                piene = []
                for riga in _righe_visive(proprie):
                    destra = max(float(parola.get("left") or 0) + float(parola.get("width") or 0) for parola in riga)
                    altezza = max(float(parola.get("height") or 0) for parola in riga)
                    piene.append(bool(colonna_destra) and colonna_destra - destra <= altezza * 0.6)
                if len(piene) == len(a_capo) + 1 and any(piene):
                    voce["righe_piene"] = piene
        fuori.append(voce)
    return fuori


__all__ = ["CHIAVI_TRATTO", "a_capo_del_testo", "con_tratti", "tratti_del_testo"]
