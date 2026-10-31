"""Mantenimento: tre percorsi distinti, ciascuno una stima motivata (richiesta dell'avvocato del 31/10/2026).

- figli: art. 337-ter c.c. (``pct.calcolatori.stime.mantenimento_figli``);
- separazione: art. 156 c.c.;
- divorzio: art. 5, comma 6, L. 898/1970 e Cass. SS.UU. 18287/2018
  (``pct.calcolatori.stime.mantenimento_coniuge``).

La legge non fissa una formula per nessuno dei tre: il modulo precedente applicava percentuali di prassi
(25% del reddito per un figlio, riduzioni del 40% e del 10%, 25% del divario fra i coniugi) che non hanno
fonte e sono state eliminate. Ora il codice esegue solo i conti verificabili sui dati e sulle ipotesi
dichiarate; presupposti e valutazioni discrezionali restano scritti e visibili.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from pct.calcolatori._base import clean_text
from pct.calcolatori.stime import mantenimento_coniuge, mantenimento_figli

PERCORSI = {
    "figli": "Mantenimento dei figli (art. 337-ter c.c.)",
    "separazione": "Mantenimento del coniuge nella separazione (art. 156 c.c.)",
    "divorzio": "Assegno divorzile (art. 5, c. 6, L. 898/1970)",
}


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    percorso = clean_text(payload.get("man_percorso")) or "figli"
    if percorso not in PERCORSI:
        raise ValueError("Percorso non riconosciuto: scegli figli, separazione o divorzio.")
    if percorso == "figli":
        return mantenimento_figli.calcola(payload)
    return mantenimento_coniuge.calcola(payload, divorzio=percorso == "divorzio")


__all__ = ["PERCORSI", "calcola"]
