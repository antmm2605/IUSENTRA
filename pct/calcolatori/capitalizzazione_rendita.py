"""Attualizzazione (capitalizzazione) di una rendita — Milano 2024.

Il danno patrimoniale da perdita di capacita' lavorativa, o da perdita del
sostegno economico, si liquida con una somma una tantum che attualizza la
rendita perduta negli anni futuri. La Cassazione impone da tempo coefficienti
aggiornati in luogo di quelli del r.d. 9 ottobre 1922 n. 1403 (Cass. n.
4186/2004, n. 20615/2015, n. 9002/2022).

Le tabelle dell'Osservatorio di Milano, edizione 2024, sono costruite sulle
tavole di mortalita' ISTAT (mortalita' 2022), sui tassi EIOPA al 30 novembre
2023 e sulla svalutazione attesa nel triennio secondo il documento previsionale
MEF 2023. Il coefficiente si legge incrociando l'eta' del danneggiato con il
numero di anni per cui il reddito verra' perso, su tabelle distinte per sesso.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from pct.calcolatori._base import clean_text, safe_float, safe_int
from pct.calcolatori.danno_biologico import tabelle

TABELLA = tabelle.MILANO_2024_CAPITALIZZAZIONE
SESSI = {"maschi": "Maschi", "femmine": "Femmine"}
_SINGOLARE = {"maschi": "uomo", "femmine": "donna"}
_ARTICOLO = {"maschi": "un", "femmine": "una"}
ETA_MASSIMA = 100


def _coefficienti(sesso: str) -> Dict[int, Dict[int, float]]:
    grezzi = tabelle.carica(TABELLA)["coefficienti"][sesso]
    return {int(eta): {int(a): float(v) for a, v in riga.items()} for eta, riga in grezzi.items()}


def orizzonte_massimo(sesso: str, eta: int) -> Optional[int]:
    """Ultimo numero di anni per cui la tabella espone un coefficiente."""
    riga = _coefficienti(sesso).get(eta)
    return max(riga) if riga else None


def coefficiente(sesso: str, eta: int, anni: int) -> Optional[float]:
    riga = _coefficienti(sesso).get(eta)
    if not riga:
        return None
    return riga.get(anni)


def _durata(payload: Mapping[str, Any], eta: int) -> tuple:
    anni = safe_int(payload.get("cr_anni"))
    if anni > 0:
        return anni, f"{anni} anni indicati"
    eta_finale = safe_int(payload.get("cr_eta_finale"))
    if eta_finale > eta:
        return eta_finale - eta, f"dai {eta} ai {eta_finale} anni"
    raise ValueError(
        "Indica per quanti anni la rendita andra' perduta, oppure l'eta' finale del periodo "
        "(per esempio l'eta' pensionabile o quella della presumibile indipendenza economica)."
    )


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    sesso = clean_text(payload.get("cr_sesso")).lower() or "maschi"
    if sesso not in SESSI:
        raise ValueError("Indica il sesso del danneggiato: la tabella e' distinta perche' cambia la sopravvivenza attesa.")

    eta = safe_int(payload.get("cr_eta"), -1)
    if not 0 <= eta <= ETA_MASSIMA:
        raise ValueError(f"L'eta' del danneggiato deve essere compresa tra 0 e {ETA_MASSIMA} anni.")

    reddito = safe_float(payload.get("cr_reddito"))
    if reddito <= 0:
        raise ValueError("Indica il reddito annuo perduto.")

    anni, dettaglio_durata = _durata(payload, eta)
    if anni <= 0:
        raise ValueError("La durata della perdita deve essere di almeno un anno.")

    massimo = orizzonte_massimo(sesso, eta)
    avvisi: List[str] = []
    anni_usati = anni
    if massimo is not None and anni > massimo:
        anni_usati = massimo
        avvisi.append(
            f"La tabella si ferma a {massimo} anni per {_ARTICOLO[sesso]} {_SINGOLARE[sesso]} "
            f"di {eta} anni: "
            "oltre quell'orizzonte la sopravvivenza attesa non giustifica un coefficiente. "
            f"Il calcolo usa {massimo} anni."
        )

    coef = coefficiente(sesso, eta, anni_usati)
    if coef is None:
        raise ValueError(
            f"Coefficiente non disponibile per {SESSI[sesso].lower()} di {eta} anni e {anni_usati} anni di perdita."
        )

    capitale = round(reddito * coef, 2)
    quota = safe_float(payload.get("cr_quota_perc"), 100.0)
    quota = max(0.0, min(quota, 100.0))
    capitale_quota = round(capitale * quota / 100.0, 2)

    dati = tabelle.carica(TABELLA)
    note = [
        f"Coefficiente {coef} letto sulla tabella {SESSI[sesso]} all'incrocio fra l'eta' di "
        f"{eta} anni e {anni_usati} anni di perdita ({dettaglio_durata}).",
        f"Attualizzazione: {reddito:.2f} € di reddito annuo x {coef} = {capitale:.2f} €.",
        "Basi di calcolo: " + "; ".join(dati["basi_di_calcolo"]) + ".",
        "La Cassazione esclude i coefficienti del r.d. 1403/1922, ormai disallineati dalla "
        "sopravvivenza reale (Cass. n. 4186/2004, n. 20615/2015, n. 9002/2022).",
        str(dati["nota_esempi_documento"]),
    ]
    if quota < 100.0:
        note.append(
            f"Il capitale e' ridotto alla quota del {quota:.0f} per cento indicata "
            "(percentuale di invalidita' lavorativa o quota di sostegno perduta)."
        )

    fonte = tabelle.fonte(TABELLA)
    return {
        "sesso": sesso,
        "sesso_label": SESSI[sesso],
        "eta": eta,
        "anni_richiesti": anni,
        "anni_applicati": anni_usati,
        "orizzonte_massimo": massimo,
        "periodo": dettaglio_durata,
        "reddito_annuo": round(reddito, 2),
        "coefficiente": coef,
        "capitale": capitale,
        "quota_perc": quota,
        "capitale_quota": capitale_quota,
        "tabelle_applicate": [fonte.come_dizionario()],
        "notes": note,
        "warnings": avvisi,
        "sources": [fonte.come_sorgente()],
    }
