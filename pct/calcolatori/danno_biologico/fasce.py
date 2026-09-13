"""Fasce di gravita' con importo minimo e massimo, comuni a piu' tabelle.

Le tabelle milanesi del consenso informato e della diffamazione non danno un
valore puntuale ma una fascia di liquidazione per ciascun livello di gravita',
con l'elenco delle circostanze che collocano il caso in quella fascia. Il
modulo tiene la lettura dei dati e il posizionamento dentro la fascia; la
scelta della fascia resta dell'avvocato o del giudice.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pct.calcolatori.danno_biologico import tabelle


def fasce(identificativo: str) -> List[Dict[str, Any]]:
    return list(tabelle.carica(identificativo)["fasce"])


def fascia(identificativo: str, nome: str) -> Dict[str, Any]:
    for voce in fasce(identificativo):
        if voce["id"] == nome:
            return dict(voce)
    raise ValueError("Fascia di gravita' non riconosciuta.")


def opzioni(identificativo: str) -> List[tuple]:
    return [(voce["id"], voce["label"]) for voce in fasce(identificativo)]


def posiziona(voce: Dict[str, Any], posizione: float, oltre_massimo: Optional[float] = None) -> Dict[str, Any]:
    """Colloca l'importo nella fascia: 0 sul minimo, 100 sul massimo.

    L'ultima fascia e' aperta verso l'alto: la tabella indica solo la soglia,
    e l'importo va motivato caso per caso. Qui si restituisce la soglia, con
    l'eventuale valore proposto dall'utente.
    """
    minimo = float(voce["minimo"])
    massimo = voce.get("massimo")
    if massimo is None:
        proposto = float(oltre_massimo) if oltre_massimo else minimo
        return {
            "minimo": minimo,
            "massimo": None,
            "proposto": round(max(proposto, minimo), 2),
            "aperta": True,
        }
    massimo = float(massimo)
    quota = max(0.0, min(float(posizione), 100.0)) / 100.0
    return {
        "minimo": minimo,
        "massimo": massimo,
        "proposto": round(minimo + (massimo - minimo) * quota, 2),
        "aperta": False,
    }
