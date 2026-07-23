"""Quote di riserva dei legittimari — successione necessaria.

Base normativa (c.c., Libro II, Titolo I, Capo X):
- Art. 536 c.c.: legittimari (coniuge/unito civilmente, figli, ascendenti).
- Art. 537 c.c.: riserva a favore dei figli (1/2 se unico, 2/3 se più figli).
- Art. 538 c.c.: riserva a favore degli ascendenti (1/3 in assenza di figli).
- Art. 540 c.c.: riserva del coniuge (1/2, oltre i diritti di abitazione e uso).
- Art. 542 c.c.: concorso coniuge-figli (1/3 + 1/3 con un figlio;
  1/4 + 1/2 con più figli).
- Art. 544 c.c.: concorso coniuge-ascendenti (1/2 + 1/4).
- Art. 556 c.c.: riunione fittizia (relictum − debiti + donatum).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import safe_bool, safe_float, safe_int


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    relictum = safe_float(payload.get("ris_patrimonio"))
    debiti = max(0.0, safe_float(payload.get("ris_debiti")))
    donatum = max(0.0, safe_float(payload.get("ris_donazioni")))
    coniuge = safe_bool(payload.get("ris_coniuge"))
    figli = max(0, safe_int(payload.get("ris_figli")))
    ascendenti = safe_bool(payload.get("ris_ascendenti"))

    if relictum <= 0 and donatum <= 0:
        raise ValueError("Inserisci il patrimonio relitto o le donazioni da riunire.")
    massa = round(relictum - debiti + donatum, 2)
    if massa <= 0:
        raise ValueError("La massa di calcolo (relictum − debiti + donatum) deve essere positiva.")
    if not coniuge and figli == 0 and not ascendenti:
        raise ValueError("Indica almeno un legittimario (coniuge, figli o ascendenti).")

    rows: List[Dict[str, Any]] = []
    notes: List[str] = []

    def _riserva(label: str, quota: float, count: int = 1, riferimento: str = "") -> None:
        importo = round(massa * quota, 2)
        rows.append(
            {
                "label": label,
                "quota_percent": round(quota * 100, 2),
                "importo": importo,
                "count": count,
                "per_testa": round(importo / count, 2) if count else importo,
                "riferimento": riferimento,
            }
        )

    if coniuge and figli == 0 and not ascendenti:
        _riserva("Coniuge", 1 / 2, 1, "Art. 540 c.c.")
    elif not coniuge and figli == 1:
        _riserva("Figlio unico", 1 / 2, 1, "Art. 537, comma 1, c.c.")
    elif not coniuge and figli > 1:
        _riserva("Figli", 2 / 3, figli, "Art. 537, comma 2, c.c.")
    elif coniuge and figli == 1:
        _riserva("Coniuge", 1 / 3, 1, "Art. 542, comma 1, c.c.")
        _riserva("Figlio unico", 1 / 3, 1, "Art. 542, comma 1, c.c.")
    elif coniuge and figli > 1:
        _riserva("Coniuge", 1 / 4, 1, "Art. 542, comma 2, c.c.")
        _riserva("Figli", 1 / 2, figli, "Art. 542, comma 2, c.c.")
    elif coniuge and ascendenti:
        _riserva("Coniuge", 1 / 2, 1, "Art. 544 c.c.")
        _riserva("Ascendenti", 1 / 4, 1, "Art. 544 c.c.")
    elif ascendenti:
        _riserva("Ascendenti", 1 / 3, 1, "Art. 538 c.c.")

    if figli > 0 and ascendenti:
        notes.append("In presenza di figli gli ascendenti non sono legittimari (art. 538 c.c.): la loro riserva non è calcolata.")

    quota_riservata = round(sum(row["quota_percent"] for row in rows), 2)
    disponibile_perc = round(100.0 - quota_riservata, 2)
    disponibile = round(massa * disponibile_perc / 100.0, 2)

    if coniuge:
        notes.append(
            "Al coniuge spettano inoltre i diritti di abitazione sulla casa familiare e di uso dei mobili "
            "(art. 540, comma 2, c.c.), che gravano sulla disponibile."
        )
    notes.append(
        "Massa calcolata con riunione fittizia ex art. 556 c.c.: relictum − debiti + donatum. "
        "La lesione di legittima si fa valere con l'azione di riduzione (artt. 553 ss. c.c.)."
    )

    return {
        "relictum": round(relictum, 2),
        "debiti": round(debiti, 2),
        "donatum": round(donatum, 2),
        "massa": massa,
        "rows": rows,
        "quota_riservata_percent": quota_riservata,
        "disponibile_percent": disponibile_perc,
        "disponibile": disponibile,
        "notes": notes,
        "warnings": [],
        "sources": [
            {"title": "Codice civile, artt. 536-556 (Normattiva)", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262"},
        ],
    }
