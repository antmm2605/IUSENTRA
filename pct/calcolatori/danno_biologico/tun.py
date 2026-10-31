"""Macrolesioni — tabella unica nazionale del D.P.R. 13 gennaio 2025 n. 12.

Base normativa:
- Art. 138 D.Lgs. 209/2005: tabella unica su tutto il territorio nazionale per
  le menomazioni comprese fra dieci e cento punti; comma 3, aumento fino al
  30 per cento; comma 4, esaustivita' del risarcimento.
- D.P.R. 12/2025, allegato I: tavola 1.A (coefficiente moltiplicatore biologico
  del punto), tavola 1.B (coefficiente di riduzione per l'eta'), tavola 2
  (coefficiente moltiplicatore per il danno morale, valori minimo, medio e
  massimo).
- D.P.R. 12/2025, art. 1, comma 2, e art. 138, comma 5, D.Lgs. 209/2005: la
  tavola 1.B si aggiorna con decreto MIMIT; aggiornata dal D.M. 10 dicembre
  2025 (G.U. n. 299 del 27/12/2025, S.O. n. 41, 25A06873) dal mese di aprile
  2025 e dal D.M. 28 settembre 2026 (G.U. n. 235 del 09/10/2026, S.O. n. 41,
  26A05220) dal mese di aprile 2026. Si applica la versione vigente alla data
  di liquidazione, come per i decreti dell'art. 139.
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

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Dict, Optional, Tuple

from pct.calcolatori._base import parse_date

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


def versioni_tavola_eta() -> list[Dict[str, Any]]:
    """Versioni della tavola 1.B in ordine di decorrenza, dal testo originario.

    Ogni versione porta decreto, Gazzetta, URL ufficiale e i coefficienti per
    eta' trascritti dal PDF pubblicato.
    """
    dati = tabelle.carica(tabelle.TUN_2025)
    originaria = {
        "decorrenza": str(dati["decorrenza_testo_originario"]),
        "decreto": "D.P.R. 13 gennaio 2025 n. 12 (testo originario)",
        "gazzetta": str(dati["pubblicazione"]),
        "url_ufficiale": str(dati["url_ufficiale"]),
        "primo_punto_allegato_ii": float(dati["primo_punto_allegato_ii"]),
        "coefficiente_riduzione_eta": dati["coefficiente_riduzione_eta"],
    }
    return [originaria, *dati.get("aggiornamenti_tavola_1b", [])]


def versione_tavola_eta(alla_data: Optional[date] = None) -> Dict[str, Any]:
    """Versione della tavola 1.B vigente alla data (l'ultima con decorrenza utile).

    Senza data si usa il testo originario del D.P.R. 12/2025, che e' anche la
    versione applicata alle date anteriori al primo aggiornamento.
    """
    versioni = versioni_tavola_eta()
    if alla_data is None:
        return versioni[0]
    scelta = versioni[0]
    for versione in versioni:
        decorrenza = parse_date(versione["decorrenza"])
        if decorrenza is not None and decorrenza <= alla_data:
            scelta = versione
    return scelta


def coefficiente_eta(eta: int, alla_data: Optional[date] = None) -> float:
    """Coefficiente di riduzione per l'eta' (tavola 1.B vigente alla data).

    La tavola parte dall'eta' di un anno; per l'eta' zero, che la tavola lascia
    priva di valore, si applica il coefficiente pieno dell'eta' di un anno.
    """
    mappa = tabelle.mappa_numerica(versione_tavola_eta(alla_data), "coefficiente_riduzione_eta")
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
    """Quota di danno morale per punto (colonna B dell'allegato II).

    Valore del punto per coefficiente della tavola 2, arrotondato ai centesimi
    con arrotondamento al pari sul valore decimale esatto: e' la regola che
    riproduce la colonna B pubblicata anche nei casi di mezzo centesimo esatto
    (per esempio 1.598,585 € pubblicato 1.598,58 per 23 punti, livello medio,
    nel testo originario del D.P.R. 12/2025).
    """
    prodotto = Decimal(str(valore_punto(punti, primo_punto))) * Decimal(str(coefficiente_morale(punti, livello)))
    return float(prodotto.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


# Metodo dell'allegato II, ricostruito sulla griglia integrale pubblicata
# (91 punti x 100 eta', tabella 1 e tabelle 2.A-2.C) del testo originario del
# D.P.R. 12/2025 e dei D.M. MIMIT 10/12/2025 e 28/09/2026: le celle sono
# calcolate in virgola mobile binaria e arrotondate all'euro con la regola
# del pari. Nei rari casi in cui il prodotto esatto termina in 0,50 € il
# risultato pubblicato dipende dall'ordine delle moltiplicazioni; l'ordine
# usato qui riproduce tutte le 109.200 celle verificate, compresi 173.695 €
# (44 punti, 90 anni, D.M. 28/09/2026) e 7.001 € di danno morale (12 punti,
# 73 anni, livello medio, D.M. 10/12/2025).


def danno_biologico(punti: int, eta: int, primo_punto: float, alla_data: Optional[date] = None) -> float:
    """Risarcimento del solo danno biologico (allegato II, tabella 1).

    L'allegato II moltiplica il valore del punto gia' arrotondato ai centesimi
    per il coefficiente di riduzione dell'eta' e poi per i punti, e arrotonda
    all'euro. ``alla_data`` sceglie la tavola 1.B vigente (data di
    liquidazione); senza data si usa il testo originario.
    """
    valore = valore_punto(punti, primo_punto) * coefficiente_eta(eta, alla_data)
    return float(round(valore * punti))


def danno_morale(
    punti: int, eta: int, primo_punto: float, livello: str, alla_data: Optional[date] = None
) -> float:
    """Incremento per danno morale sul biologico (allegato II, tabelle 2.A-2.C).

    Quota morale per punto (colonna B) per il prodotto di punti e coefficiente
    dell'eta', arrotondata all'euro.
    """
    if livello not in _INDICE_MORALE:
        return 0.0
    fattore = punti * coefficiente_eta(eta, alla_data)
    return float(round(valore_punto_morale(punti, primo_punto, livello) * fattore))


def griglia_pubblicata(
    punti: int, eta: int, primo_punto: float, livello: str | None = None, alla_data: Optional[date] = None
) -> Dict[str, float]:
    """Cella dell'allegato II per punto ed eta', come pubblicata in Gazzetta."""
    biologico = danno_biologico(punti, eta, primo_punto, alla_data)
    if livello is None:
        return {"biologico": biologico}
    morale = danno_morale(punti, eta, primo_punto, livello, alla_data)
    return {"biologico": biologico, "morale": morale, "totale": biologico + morale}
