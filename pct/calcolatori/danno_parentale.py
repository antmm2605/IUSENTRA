"""Danno da perdita del rapporto parentale — Tabelle Milano 2024 a punti.

Base normativa e giurisprudenziale:
- Artt. 2043 e 2059 c.c.; art. 8 CEDU (tutela della vita familiare).
- Cass. 21/04/2021 n. 10579 e Cass. 29/09/2021 n. 26300: necessità di una
  tabella a punti con i cinque parametri rilevanti.
- Tabelle del Tribunale di Milano, edizione 2024 (tabella a punti per il
  danno da perdita del rapporto parentale).

Come per il danno biologico già presente nel progetto, i valori sono una
approssimazione operativa dichiarata della griglia ufficiale: il risultato va
sempre verificato sulla tabella pubblicata dal Tribunale di Milano.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_bool, safe_int

# Valori punto edizione Milano 2024 (approssimazione operativa dichiarata).
_CATEGORIE = {
    "nucleo_primario": {
        "label": "Genitore, figlio o coniuge/unito civilmente (nucleo primario)",
        "valore_punto": 3911.64,
        "punti_max": 118,
    },
    "altri_congiunti": {
        "label": "Fratello, sorella, nonno o nipote",
        "valore_punto": 1461.20,
        "punti_max": 116,
    },
}

_QUALITA_RELAZIONE = {
    "eccezionale": (30, "Relazione di intensità eccezionale documentata"),
    "intensa": (24, "Relazione intensa e continuativa"),
    "ordinaria": (16, "Relazione ordinaria per il vincolo di parentela"),
    "ridotta": (8, "Relazione ridotta o saltuaria"),
    "assente": (0, "Relazione assente o conflittuale"),
}


def _punti_eta_vittima(eta: int) -> int:
    """Punti decrescenti per decade di età della vittima primaria (max 30)."""
    if eta <= 30:
        return 30
    if eta <= 40:
        return 26
    if eta <= 50:
        return 22
    if eta <= 60:
        return 16
    if eta <= 70:
        return 12
    if eta <= 80:
        return 8
    return 4


def _punti_eta_congiunto(eta: int) -> int:
    """Punti decrescenti per decade di età del congiunto superstite (max 28)."""
    if eta <= 30:
        return 28
    if eta <= 40:
        return 24
    if eta <= 50:
        return 20
    if eta <= 60:
        return 14
    if eta <= 70:
        return 10
    if eta <= 80:
        return 6
    return 2


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    categoria = clean_text(payload.get("dp_categoria")) or "nucleo_primario"
    if categoria not in _CATEGORIE:
        raise ValueError("Categoria di rapporto parentale non riconosciuta.")
    eta_vittima = safe_int(payload.get("dp_eta_vittima"))
    eta_congiunto = safe_int(payload.get("dp_eta_congiunto"))
    convivenza = safe_bool(payload.get("dp_convivenza"))
    unico_superstite = safe_bool(payload.get("dp_unico_superstite"))
    qualita = clean_text(payload.get("dp_qualita_relazione")) or "ordinaria"
    if qualita not in _QUALITA_RELAZIONE:
        raise ValueError("Qualità della relazione non riconosciuta.")

    if not (0 < eta_vittima <= 120):
        raise ValueError("Indica l'età della vittima primaria al momento del fatto.")
    if not (0 < eta_congiunto <= 120):
        raise ValueError("Indica l'età del congiunto superstite al momento del fatto.")

    config = _CATEGORIE[categoria]
    punti_qualita, label_qualita = _QUALITA_RELAZIONE[qualita]

    parametri: List[Dict[str, Any]] = [
        {"label": "Età della vittima primaria", "detail": f"{eta_vittima} anni", "punti": _punti_eta_vittima(eta_vittima), "max": 30},
        {"label": "Età del congiunto superstite", "detail": f"{eta_congiunto} anni", "punti": _punti_eta_congiunto(eta_congiunto), "max": 28},
        {"label": "Convivenza con la vittima", "detail": "Sì" if convivenza else "No", "punti": 16 if convivenza else 0, "max": 16},
        {"label": "Assenza di altri congiunti del nucleo", "detail": "Unico superstite" if unico_superstite else "Altri congiunti presenti", "punti": 20 if unico_superstite else 0, "max": 20},
        {"label": "Qualità e intensità della relazione", "detail": label_qualita, "punti": punti_qualita, "max": 30},
    ]

    punti_totali = sum(int(riga["punti"]) for riga in parametri)
    punti_liquidati = min(punti_totali, int(config["punti_max"]))
    importo = round(punti_liquidati * float(config["valore_punto"]), 2)
    cap = round(int(config["punti_max"]) * float(config["valore_punto"]), 2)

    warnings: List[str] = []
    if punti_totali > punti_liquidati:
        warnings.append(
            f"I punti calcolati ({punti_totali}) superano il massimo tabellare ({config['punti_max']}): "
            "l'importo è liquidato al tetto massimo della categoria."
        )
    warnings.append(
        "Approssimazione operativa della tabella a punti di Milano 2024: verificare sempre "
        "la griglia ufficiale pubblicata dal Tribunale di Milano prima dell'uso in atti."
    )

    return {
        "categoria": categoria,
        "categoria_label": config["label"],
        "valore_punto": config["valore_punto"],
        "punti_max": config["punti_max"],
        "parametri": parametri,
        "punti_totali": punti_totali,
        "punti_liquidati": punti_liquidati,
        "importo": importo,
        "massimale_categoria": cap,
        "notes": [
            "Tabella a punti Milano 2024 con i cinque parametri indicati dalla Cassazione "
            "(Cass. 10579/2021 e 26300/2021): età della vittima, età del congiunto, convivenza, "
            "sopravvivenza di altri congiunti, qualità della relazione.",
            "La liquidazione resta equitativa: il giudice può discostarsi motivando sulle circostanze concrete.",
        ],
        "warnings": warnings,
        "sources": [
            {"title": "Tabelle Milano 2024", "url": "https://www.tribunale.milano.it/tabelle-di-liquidazione-del-danno"},
            {"title": "Cass. 26300/2021", "url": "https://www.italgiure.giustizia.it"},
        ],
    }
