"""Somma equitativa per abuso del processo — art. 96, comma 3, c.p.c.

La somma dell'art. 96, ultimo comma, non e' un danno in senso tecnico: ha
natura insieme indennitaria e sanzionatoria (Corte cost. 23 giugno 2016 n. 152;
Cass. Sez. Un. n. 16601/2017) e va liquidata con il solo criterio equitativo,
"con l'unico limite della ragionevolezza" (Cass. n. 21570/2012).

Criterio orientativo dell'Osservatorio sulla giustizia civile di Milano,
edizione 2024, confermato dall'Assemblea nazionale degli Osservatori (Roma,
maggio 2017) su un campione di novanta provvedimenti: l'importo si determina
con riferimento al compenso defensionale liquidato in causa, in misura
all'incirca pari al compenso, riducibile fino alla meta' e aumentabile della
meta' in ragione delle circostanze specifiche dell'abuso.

Il modulo non valuta i presupposti dell'an: quelli restano al giudice.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import safe_bool, safe_float, safe_int

FONTE = {
    "title": "Osservatorio sulla giustizia civile di Milano — criteri art. 96 comma 3 c.p.c., edizione 2024",
    "url": "https://tribunale-milano.giustizia.it/cmsresources/cms/documents/P._7599_24.pdf",
}

COEFFICIENTE_MINIMO = 0.5
COEFFICIENTE_BASE = 1.0
COEFFICIENTE_MASSIMO = 1.5

# Indici di graduazione elencati dall'Osservatorio: ciascuno sposta la
# liquidazione di un dodicesimo dell'escursione fra minimo e massimo.
_INDICI = (
    ("lt_valore_elevato", "Valore della causa elevato"),
    ("lt_processo_lungo", "Durata del processo protratta"),
    ("lt_piu_parti", "Piu' parti vittoriose subiscono l'abuso"),
    ("lt_dolo", "Elemento soggettivo dell'abusante particolarmente intenso"),
    ("lt_affaticamento", "Affaticamento rilevante della parte abusata"),
)
_PASSO = (COEFFICIENTE_MASSIMO - COEFFICIENTE_MINIMO) / 10.0


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    compenso = safe_float(payload.get("lt_compenso"))
    if compenso <= 0:
        raise ValueError("Indica il compenso defensionale liquidato in causa.")
    parti = max(1, safe_int(payload.get("lt_parti"), 1))

    indici: List[Dict[str, Any]] = []
    coefficiente = COEFFICIENTE_BASE
    for campo, etichetta in _INDICI:
        presente = safe_bool(payload.get(campo))
        indici.append({"label": etichetta, "presente": presente})
        if presente:
            coefficiente += _PASSO
    coefficiente = round(min(coefficiente, COEFFICIENTE_MASSIMO), 4)

    base = round(compenso * COEFFICIENTE_BASE, 2)
    minimo = round(compenso * COEFFICIENTE_MINIMO, 2)
    massimo = round(compenso * COEFFICIENTE_MASSIMO, 2)
    proposto = round(compenso * coefficiente, 2)

    note = [
        "Criterio orientativo dell'Osservatorio di Milano, edizione 2024: importo all'incirca "
        "pari al compenso defensionale liquidato, riducibile fino alla meta' e aumentabile "
        "della meta' secondo le circostanze dell'abuso.",
        "Il parametro e' il solo compenso di avvocato, al netto del rimborso forfettario per "
        "spese generali e degli accessori.",
        "La somma non e' un danno: ha natura indennitaria e sanzionatoria (Corte cost. 152/2016; "
        "Cass. Sez. Un. 16601/2017) e non richiede la prova di un pregiudizio.",
        "Il modulo non valuta i presupposti dell'an debeatur: la malafede o colpa grave "
        "dell'abusante resta accertamento del giudice.",
    ]
    avvisi: List[str] = []
    if parti > 1:
        avvisi.append(
            f"Le parti vittoriose sono {parti}: gli importi indicati valgono per ciascuna parte, "
            "la liquidazione complessiva va rapportata al numero delle parti abusate."
        )

    return {
        "compenso": round(compenso, 2),
        "parti": parti,
        "importo_minimo": minimo,
        "importo_base": base,
        "importo_massimo": massimo,
        "coefficiente": coefficiente,
        "importo_proposto": proposto,
        "totale_per_tutte_le_parti": round(proposto * parti, 2),
        "indici": indici,
        "notes": note,
        "warnings": avvisi,
        "sources": [dict(FONTE)],
    }
