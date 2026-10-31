"""Stime motivate: calcoli riproducibili su ipotesi dichiarate, non importi imposti dalla legge.

Per gli istituti in cui la legge indica criteri ma non una formula (mantenimento dei figli e del
coniuge, assegno divorzile, somma dell'art. 96, comma 3, c.p.c.) il software separa sempre:

- i presupposti giuridici, che verifica e dichiara ma non decide;
- il calcolo economico, eseguito dal codice e ripetibile con gli stessi dati;
- le valutazioni discrezionali, che restano all'avvocato e devono essere scritte.

Ogni risultato porta la sua scheda di calcolo (metodo e versione, dati, ipotesi, fonti, campi
mancanti, valutazioni) e uno di tre stati: dati insufficienti, stima da verificare, proposta
validata dallo studio. Richiesta dell'avvocato del 31/10/2026.
"""
from __future__ import annotations

from pct.calcolatori.stime.scheda import (
    STATO_DATI_INSUFFICIENTI,
    STATO_DA_VERIFICARE,
    STATO_VALIDATA,
    SchedaDiCalcolo,
    importo_o_intervallo,
    righe_testo,
)

__all__ = [
    "STATO_DATI_INSUFFICIENTI",
    "STATO_DA_VERIFICARE",
    "STATO_VALIDATA",
    "SchedaDiCalcolo",
    "importo_o_intervallo",
    "righe_testo",
]
