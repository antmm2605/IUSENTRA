"""Lesioni di lieve entita' — art. 139 D.Lgs. 209/2005 (1-9 punti).

Base normativa:
- Art. 139, comma 1, lettera a): importo crescente in misura piu' che
  proporzionale, calcolato applicando a ciascun punto il coefficiente del
  comma 6; l'importo si riduce dello 0,5 per cento per ogni anno di eta' a
  partire dall'undicesimo.
- Art. 139, comma 1, lettera b): danno biologico temporaneo, importo per ogni
  giorno di inabilita' assoluta, riproporzionato alla percentuale di inabilita'
  riconosciuta per ciascun giorno.
- Art. 139, comma 3: aumento fino al 20 per cento; l'ammontare complessivo e'
  esaustivo del danno non patrimoniale conseguente a lesioni fisiche.
- Art. 139, comma 5: aggiornamento annuale degli importi con decreto
  ministeriale, secondo l'indice ISTAT FOI.
- Art. 7, comma 4, L. 8 marzo 2017 n. 24: estensione alla responsabilita'
  sanitaria.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from pct.calcolatori._base import parse_date
from pct.calcolatori.danno_biologico import tabelle

PUNTO_MASSIMO = 9


def decreto_vigente(alla_data: date) -> Dict[str, Any]:
    """Ultimo decreto di aggiornamento con decorrenza non successiva alla data.

    Ogni decreto resta in vigore finche' non interviene il successivo: la
    ricerca dell'ultimo decreto utile e' quindi la regola corretta anche per le
    annualita' in cui nessun decreto e' stato adottato.
    """
    dati = tabelle.carica(tabelle.ART_139)
    scelto: Optional[Dict[str, Any]] = None
    for decreto in dati["decreti_aggiornamento"]:
        decorrenza = parse_date(decreto["decorrenza"])
        if decorrenza is not None and decorrenza <= alla_data:
            scelto = decreto
    return scelto or dati["decreti_aggiornamento"][0]


def coefficiente_eta(eta: int) -> float:
    """Riduzione dello 0,5 per cento per ogni anno a partire dall'undicesimo."""
    dati = tabelle.carica(tabelle.ART_139)
    primo_anno = int(dati["riduzione_eta_dal_anno"])
    passo = float(dati["riduzione_eta_pct_annua"]) / 100.0
    if eta < primo_anno:
        return 1.0
    return max(0.0, 1.0 - passo * (eta - primo_anno + 1))


def coefficiente_punto(punti: int) -> float:
    """Coefficiente moltiplicatore del comma 6 per il punto indicato."""
    dati = tabelle.carica(tabelle.ART_139)
    return float(dati["coefficiente_moltiplicatore"][str(punti)])


def danno_permanente(punti: int, eta: int, primo_punto: float) -> float:
    """Danno biologico permanente per postumi da 1 a 9 punti."""
    if punti <= 0:
        return 0.0
    return round(primo_punto * coefficiente_punto(punti) * punti * coefficiente_eta(eta), 2)


def danno_temporaneo(giorni: int, percentuale: float, valore_giorno: float) -> float:
    """Danno biologico temporaneo per giorni e percentuale di inabilita'."""
    if giorni <= 0 or percentuale <= 0:
        return 0.0
    return round(giorni * valore_giorno * percentuale / 100.0, 2)


def personalizzazione_massima() -> int:
    return int(tabelle.carica(tabelle.ART_139)["personalizzazione_massima_pct"])
