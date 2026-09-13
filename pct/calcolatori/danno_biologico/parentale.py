"""Perdita del rapporto parentale — tabelle integrate a punti Milano 2024.

Base giurisprudenziale: Cass. civ. 21 aprile 2021 n. 10579 impone, per la
liquidazione equitativa di questo danno, una tabella a punti che elenchi le
circostanze rilevanti e i relativi punteggi, indefettibilmente l'eta' della
vittima, l'eta' del superstite, il grado di parentela e la convivenza; nello
stesso senso Cass. 29 settembre 2021 n. 26300.

L'Osservatorio milanese ha licenziato due tabelle, una per il nucleo primario
(genitore, figlio, coniuge e assimilati) e una per fratelli e nipoti, ciascuna
con il proprio valore punto, il proprio numero di punti attribuibili e il
proprio tetto monetario. I punti attribuibili superano cento apposta: il tetto
non e' raggiungibile in un solo caso ma in piu' ipotesi.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pct.calcolatori.danno_biologico import tabelle

NUCLEO_PRIMARIO = "nucleo_primario"
FRATELLO_NIPOTE = "fratello_nipote"


def _dati() -> Dict[str, Any]:
    return tabelle.carica(tabelle.MILANO_2024_PARENTALE)


def categorie() -> Dict[str, Dict[str, Any]]:
    return _dati()["categorie"]


def categoria(nome: str) -> Dict[str, Any]:
    voci = categorie()
    if nome not in voci:
        raise ValueError("Categoria di rapporto parentale non riconosciuta.")
    return voci[nome]


def _punti_per_fascia(fasce: List[Tuple[int, int]], eta: int) -> int:
    for limite, punti in fasce:
        if eta <= limite:
            return int(punti)
    return int(fasce[-1][1])


def punti_eta_vittima_primaria(nome: str, eta: int) -> int:
    return _punti_per_fascia(categoria(nome)["fasce_eta_vittima_primaria"], eta)


def punti_eta_vittima_secondaria(nome: str, eta: int) -> int:
    return _punti_per_fascia(categoria(nome)["fasce_eta_vittima_secondaria"], eta)


def opzioni_convivenza(nome: str) -> Dict[str, int]:
    return {k: int(v) for k, v in categoria(nome)["punti_convivenza"].items()}


def punti_convivenza(nome: str, scelta: str) -> int:
    return opzioni_convivenza(nome).get(scelta, 0)


def punti_superstiti(nome: str, superstiti: int) -> int:
    """Punti del parametro D; oltre i superstiti tabellati il parametro non da' punti.

    La tabella arriva a tre superstiti. Gli esempi di calcolo pubblicati
    dall'Osservatorio nell'allegato 1 attribuiscono zero punti quando i
    superstiti sono di piu' (casi con cinque superstiti), non il punteggio del
    terzo: la funzione segue quegli esempi.
    """
    mappa = categoria(nome)["punti_superstiti"]
    chiavi = sorted(int(k) for k in mappa)
    if superstiti > chiavi[-1]:
        return 0
    return int(mappa[str(max(superstiti, chiavi[0]))])


def punti_massimi_relazione(nome: str) -> int:
    return int(categoria(nome)["punti_massimi_relazione"])


def importo(nome: str, punti: int) -> float:
    """Importo per i punti attribuiti, non oltre il tetto della categoria."""
    voce = categoria(nome)
    grezzo = punti * float(voce["valore_punto"])
    return round(min(grezzo, float(voce["cap"])), 2)
