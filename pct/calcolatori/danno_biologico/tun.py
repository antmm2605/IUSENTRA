"""Macrolesioni — tabella unica nazionale del D.P.R. 13 gennaio 2025 n. 12.

Base normativa:
- Art. 138 D.Lgs. 209/2005: tabella unica su tutto il territorio nazionale per
  le menomazioni comprese fra dieci e cento punti; comma 3, aumento fino al
  30 per cento; comma 4, esaustivita' del risarcimento.
- D.P.R. 12/2025, allegato I: tavola 1.A (coefficiente moltiplicatore biologico
  del punto), tavola 1.B (coefficiente di riduzione per l'eta'), tavola 2
  (coefficiente moltiplicatore per il danno morale, valori minimo, medio e
  massimo).
- D.P.R. 12/2025, art. 2: il valore del primo punto e' quello dell'art. 139.
- D.P.R. 12/2025, art. 3: il danno biologico temporaneo si liquida secondo
  l'art. 139, con incremento per danno morale fra il 30 e il 60 per cento.
- D.P.R. 12/2025, art. 5: si applica ai sinistri verificatisi dopo l'entrata in
  vigore, cioe' dal 5 marzo 2025.
- Art. 7, comma 4, L. 24/2017: estensione alla responsabilita' sanitaria.

La griglia dell'allegato II e' interamente riproducibile con le tavole
dell'allegato I: il modulo calcola dai coefficienti invece di duplicare
diecimila celle, e il test di regressione confronta il risultato con i valori
pubblicati.
"""
from __future__ import annotations

from typing import Dict, Tuple

from pct.calcolatori.danno_biologico import tabelle

PUNTO_MINIMO = 10
PUNTO_MASSIMO = 100
LIVELLI_MORALE = ("minimo", "medio", "massimo")
_INDICE_MORALE = {"minimo": 0, "medio": 1, "massimo": 2}

PERSONALIZZAZIONE_MASSIMA_PCT = 30
MORALE_TEMPORANEO_MINIMO_PCT = 30
MORALE_TEMPORANEO_MASSIMO_PCT = 60


def coefficiente_biologico(punti: int) -> float:
    """Coefficiente moltiplicatore biologico del punto (tavola 1.A)."""
    return tabelle.mappa_numerica(tabelle.carica(tabelle.TUN_2025), "coefficiente_moltiplicatore_biologico")[punti]


def coefficiente_eta(eta: int) -> float:
    """Coefficiente di riduzione per l'eta' (tavola 1.B).

    La tavola parte dall'eta' di un anno; per l'eta' zero, che la tavola lascia
    priva di valore, si applica il coefficiente pieno dell'eta' di un anno.
    """
    mappa = tabelle.mappa_numerica(tabelle.carica(tabelle.TUN_2025), "coefficiente_riduzione_eta")
    if eta <= 1:
        return mappa[1]
    return mappa[min(eta, max(mappa))]


def coefficienti_morale(punti: int) -> Tuple[float, float, float]:
    """Coefficienti moltiplicatori del danno morale, minimo, medio e massimo."""
    return tabelle.mappa_terne(tabelle.carica(tabelle.TUN_2025), "coefficiente_moltiplicatore_morale")[punti]


def coefficiente_morale(punti: int, livello: str) -> float:
    return coefficienti_morale(punti)[_INDICE_MORALE[livello]]


def valore_punto(punti: int, primo_punto: float) -> float:
    """Valore pecuniario del punto: primo punto per coefficiente della tavola 1.A."""
    return round(primo_punto * coefficiente_biologico(punti), 2)


def valore_punto_morale(punti: int, primo_punto: float, livello: str) -> float:
    """Quota di danno morale per punto, arrotondata come nell'allegato II."""
    return round(valore_punto(punti, primo_punto) * coefficiente_morale(punti, livello), 2)


def danno_biologico(punti: int, eta: int, primo_punto: float) -> float:
    """Risarcimento del solo danno biologico (allegato II, tabella 1).

    L'allegato II moltiplica il valore del punto gia' arrotondato ai centesimi
    per i punti e per il coefficiente di riduzione dell'eta': arrotondare prima
    o dopo cambia il risultato di qualche euro, e la regola qui e' quella che
    riproduce esattamente le celle pubblicate in Gazzetta.
    """
    return float(round(valore_punto(punti, primo_punto) * punti * coefficiente_eta(eta)))


def danno_morale(punti: int, eta: int, primo_punto: float, livello: str) -> float:
    """Incremento per danno morale sul biologico (allegato II, tabelle 2.A-2.C)."""
    if livello not in _INDICE_MORALE:
        return 0.0
    return float(round(valore_punto_morale(punti, primo_punto, livello) * punti * coefficiente_eta(eta)))


def griglia_pubblicata(punti: int, eta: int, primo_punto: float, livello: str | None = None) -> Dict[str, float]:
    """Cella dell'allegato II per punto ed eta', come pubblicata in Gazzetta."""
    biologico = danno_biologico(punti, eta, primo_punto)
    if livello is None:
        return {"biologico": biologico}
    morale = danno_morale(punti, eta, primo_punto, livello)
    return {"biologico": biologico, "morale": morale, "totale": biologico + morale}
