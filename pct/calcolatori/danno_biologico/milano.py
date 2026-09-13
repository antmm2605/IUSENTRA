"""Tabelle milanesi del danno non patrimoniale — edizione 2024.

Base giurisprudenziale: Cass. 7 giugno 2011 n. 12408 riconosce alle tabelle
milanesi il valore di parametro nazionale per la liquidazione equitativa ex
art. 1226 c.c.; restano il riferimento per la responsabilita' civile che non
ricade negli artt. 138 e 139 del codice delle assicurazioni private, e per le
macrolesioni da sinistro anteriore all'entrata in vigore della tabella unica
nazionale.

Struttura della tabella pubblicata: per ciascun punto da 1 a 100 sono indicati
il valore del punto a titolo di danno biologico/dinamico-relazionale (A) e a
titolo di sofferenza soggettiva interiore (B), oltre alla percentuale massima
di personalizzazione. Ogni cella della griglia e' il valore del punto
moltiplicato per i punti e per il demoltiplicatore dell'eta'.
"""
from __future__ import annotations

from typing import Any, Dict

from pct.calcolatori.danno_biologico import tabelle

PUNTO_MINIMO = 1
PUNTO_MASSIMO = 100


def _dati() -> Dict[str, Any]:
    return tabelle.carica(tabelle.MILANO_2024)


def riga_punto(punti: int) -> Dict[str, float]:
    """Valori pubblicati per il punto indicato."""
    return {k: float(v) for k, v in _dati()["punti"][str(punti)].items()}


def demoltiplicatore_eta(eta: int) -> float:
    """Demoltiplicatore dell'eta'; la tabella parte dall'eta' di un anno."""
    mappa = tabelle.mappa_numerica(_dati(), "demoltiplicatore_eta")
    if eta <= 1:
        return mappa[1]
    return mappa[min(eta, max(mappa))]


def personalizzazione_massima(punti: int) -> int:
    return int(riga_punto(punti)["personalizzazione_massima_pct"])


def danno_permanente(punti: int, eta: int) -> Dict[str, float]:
    """Cella della griglia: componente biologica, sofferenza e totale."""
    if punti <= 0:
        return {"biologico": 0.0, "sofferenza": 0.0, "totale": 0.0}
    riga = riga_punto(punti)
    coefficiente = demoltiplicatore_eta(eta)
    biologico = round(riga["biologico"] * punti * coefficiente)
    sofferenza = round(riga["sofferenza"] * punti * coefficiente)
    totale = round(riga["totale"] * punti * coefficiente)
    return {"biologico": float(biologico), "sofferenza": float(sofferenza), "totale": float(totale)}


def valore_giorno_inabilita_totale() -> float:
    return float(_dati()["valore_giorno_inabilita_totale"])


def danno_temporaneo(giorni: int, percentuale: float) -> float:
    """Liquidazione pro die, riproporzionata alla percentuale di inabilita'."""
    if giorni <= 0 or percentuale <= 0:
        return 0.0
    return round(giorni * valore_giorno_inabilita_totale() * percentuale / 100.0, 2)
