"""Usufrutto vitalizio e nuda proprietà — coefficienti fiscali.

Base normativa:
- Art. 48 D.P.R. 131/1986 (T.U. imposta di registro) e prospetto dei
  coefficienti allegato, aggiornato annualmente con decreto MEF in funzione
  del tasso legale di interesse (art. 1284 c.c.).
- Artt. 978 ss. c.c. (usufrutto).

Le percentuali per fascia d'età del prospetto ministeriale sono stabili nel
tempo; il coefficiente moltiplicatore annuale è per costruzione pari a
percentuale/tasso legale. Il tasso legale corrente proviene dalle tabelle
normative versionate del progetto (fail-closed se assente).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import safe_float, safe_int

# Prospetto allegato al D.P.R. 131/1986: (età massima inclusa, % usufrutto).
_FASCE_USUFRUTTO: List[tuple[int, float]] = [
    (20, 95.0),
    (30, 90.0),
    (40, 85.0),
    (45, 80.0),
    (50, 75.0),
    (53, 70.0),
    (56, 65.0),
    (60, 60.0),
    (63, 55.0),
    (66, 50.0),
    (69, 45.0),
    (72, 40.0),
    (75, 35.0),
    (78, 30.0),
    (82, 25.0),
    (86, 20.0),
    (92, 15.0),
    (99, 10.0),
]


def _percentuale_per_eta(eta: int) -> float:
    for eta_max, percentuale in _FASCE_USUFRUTTO:
        if eta <= eta_max:
            return percentuale
    return 5.0  # Oltre 99 anni il prospetto ministeriale non scende sotto questa soglia operativa.


def _tasso_legale_corrente(norme: Any) -> tuple[float, Dict[str, str]]:
    periods = norme.interest_periods("legali")
    oggi = date.today()
    corrente = None
    for period in periods:
        if period.start <= oggi <= period.end:
            corrente = period
    if corrente is None and periods:
        corrente = sorted(periods, key=lambda p: p.end)[-1]
    if corrente is None:
        raise ValueError("Tasso legale non disponibile nelle tabelle normative caricate.")
    return float(corrente.rate), corrente.source.to_dict()


def calcola(payload: Mapping[str, Any], norme: Any) -> Dict[str, Any]:
    valore_piena = safe_float(payload.get("usu_valore_piena"))
    eta = safe_int(payload.get("usu_eta"))
    quota_perc = safe_float(payload.get("usu_quota_perc"), 100.0)

    if valore_piena <= 0:
        raise ValueError("Inserisci il valore della piena proprietà.")
    if not (0 < eta <= 120):
        raise ValueError("Indica l'età dell'usufruttuario al momento dell'atto.")
    if not (0 < quota_perc <= 100):
        raise ValueError("La quota deve essere compresa tra 1 e 100.")

    tasso_legale, fonte_tasso = _tasso_legale_corrente(norme)
    percentuale = _percentuale_per_eta(eta)
    coefficiente = round(percentuale / tasso_legale, 2) if tasso_legale else 0.0

    base = round(valore_piena * quota_perc / 100.0, 2)
    valore_usufrutto = round(base * percentuale / 100.0, 2)
    valore_nuda = round(base - valore_usufrutto, 2)

    warnings: List[str] = []
    if eta > 99:
        warnings.append(
            "Oltre i 99 anni il prospetto ministeriale non prevede una fascia dedicata: "
            "è applicata la percentuale operativa minima, da verificare sul decreto vigente."
        )

    return {
        "valore_piena": round(valore_piena, 2),
        "quota_perc": quota_perc,
        "base_calcolo": base,
        "eta": eta,
        "percentuale_usufrutto": percentuale,
        "percentuale_nuda": round(100.0 - percentuale, 2),
        "coefficiente": coefficiente,
        "tasso_legale": tasso_legale,
        "valore_usufrutto": valore_usufrutto,
        "valore_nuda_proprieta": valore_nuda,
        "notes": [
            "Valore fiscale dell'usufrutto vitalizio: base imponibile per la percentuale della fascia "
            "d'età dell'usufruttuario (prospetto allegato al D.P.R. 131/1986).",
            f"Coefficiente annuale = percentuale/tasso legale ({percentuale:.0f}% / {tasso_legale}% = {coefficiente}).",
            "L'età rilevante è quella compiuta dall'usufruttuario alla data dell'atto.",
        ],
        "warnings": warnings,
        "sources": [
            {"title": "D.P.R. 131/1986 art. 48 e prospetto allegato (Normattiva)", "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986-04-26;131"},
            fonte_tasso,
        ],
    }
