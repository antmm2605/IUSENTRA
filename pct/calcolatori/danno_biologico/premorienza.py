"""Danno da lesione del bene salute definito da premorienza — Milano 2024.

Il caso e' quello del danneggiato che, subita una menomazione permanente,
muore prima della liquidazione per una causa esterna e indipendente dalla
lesione: il pregiudizio si e' prodotto in un intervallo chiuso, fra l'illecito
e la morte, e va liquidato per quell'intervallo.

Fonte: Osservatorio sulla giustizia civile di Milano, edizione 2024, criterio
approvato dall'Assemblea nazionale degli Osservatori (Roma, maggio 2017), nel
solco di Cass. civ. n. 679/2016 e n. 10897/2016. La tabella pubblica, per
ciascun punto di invalidita', tre colonne: il primo anno, il primo e il secondo
anno insieme, e ogni ulteriore anno a partire dal terzo.
"""
from __future__ import annotations

from typing import Any, Dict

from pct.calcolatori.danno_biologico import tabelle

PUNTO_MINIMO = 1
PUNTO_MASSIMO = 100


def _dati() -> Dict[str, Any]:
    return tabelle.carica(tabelle.MILANO_2024_PREMORIENZA)


def riga_punto(punti: int) -> Dict[str, Dict[str, int]]:
    """Le tre colonne pubblicate per il punto indicato."""
    return _dati()["punti"][str(punti)]


def personalizzazione_massima() -> int:
    return int(_dati()["personalizzazione_massima_pct"])


def liquida(punti: int, anni: int) -> Dict[str, float]:
    """Risarcimento per una sopravvivenza di ``anni`` anni dall'evento lesivo.

    Un anno usa la prima colonna, due anni la seconda (che gia' comprende il
    primo), da tre anni in su si aggiunge la terza colonna per ogni anno
    successivo al secondo.
    """
    if punti <= 0 or anni <= 0:
        return {"biologico": 0.0, "sofferenza": 0.0, "totale": 0.0, "anni_ulteriori": 0}
    riga = riga_punto(punti)
    if anni == 1:
        base, ulteriori = riga["primo_anno"], 0
    else:
        base, ulteriori = riga["primo_e_secondo_anno"], anni - 2
    successivo = riga["anno_successivo"]
    biologico = base["biologico"] + successivo["biologico"] * ulteriori
    sofferenza = base["sofferenza"] + successivo["sofferenza"] * ulteriori
    return {
        "biologico": float(biologico),
        "sofferenza": float(sofferenza),
        "totale": float(biologico + sofferenza),
        "anni_ulteriori": ulteriori,
    }
