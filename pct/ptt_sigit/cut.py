"""Contributo unificato tributario (CUT) e valore della lite.

Art. 13, comma 6-quater, d.P.R. 115/2002 (testo vigente su Normattiva al
25/09/2026; stessi importi nella pagina DGT «Contributo unificato»):

- fino a 2.582,28 €: 30 €; fino a 5.000 €: 60 €; fino a 25.000 € e per le
  liti di valore indeterminabile: 120 €; fino a 75.000 €: 250 €; fino a
  200.000 €: 500 €; oltre 200.000 €: 1.500 €;
- art. 12, comma 2, D.Lgs. 546/1992: il valore è l'importo del tributo al
  netto di interessi e sanzioni; se la lite riguarda solo sanzioni, la loro
  somma;
- art. 14, comma 3-bis, D.Lgs. 546/1992 e art. 13 c. 6-quater: se il valore
  non è dichiarato nelle conclusioni il CUT è dovuto nella misura massima;
- con più atti impugnati il CUT è la somma dei contributi di ciascun atto
  (DGT, «Calcolare e pagare il contributo unificato tributario»);
- art. 13, comma 3-bis: aumento della metà se il difensore non indica la PEC o
  la parte il codice fiscale.

Esenzione con prenotazione a debito per le amministrazioni e gli ammessi al
patrocinio a spese dello Stato (art. 11 e 158 d.P.R. 115/2002).
"""

from __future__ import annotations

from typing import Any, Iterable

SCAGLIONI = ((2582.28, 30), (5000.00, 60), (25000.00, 120), (75000.00, 250), (200000.00, 500))
MASSIMO = 1500
INDETERMINABILE = 120


def _numero(valore: Any) -> float | None:
    if valore in (None, ""):
        return None
    if isinstance(valore, (int, float)):
        return float(valore)
    testo = str(valore).strip().replace("€", "").replace(" ", "")
    if "," in testo:
        testo = testo.replace(".", "").replace(",", ".")
    try:
        return float(testo)
    except ValueError:
        return None


def valore_lite(tributo: Any = None, sanzioni: Any = None) -> float | None:
    """Tributo al netto di interessi e sanzioni; solo sanzioni se il tributo non è in contestazione."""
    importo = _numero(tributo)
    if importo:
        return round(importo, 2)
    solo_sanzioni = _numero(sanzioni)
    return round(solo_sanzioni, 2) if solo_sanzioni else None


def per_atto(valore: Any, indeterminabile: bool = False) -> int:
    if indeterminabile:
        return INDETERMINABILE
    importo = _numero(valore)
    if importo is None:
        return MASSIMO
    return next((cut for soglia, cut in SCAGLIONI if importo <= soglia), MASSIMO)


def calcola(atti: Iterable[dict[str, Any]], *, pec_difensore: bool = True, codice_fiscale_parte: bool = True,
            esenzione: str = "") -> dict[str, Any]:
    """Il CUT del deposito: somma per atto, aumento del 50% se mancano PEC o codice fiscale."""
    righe = []
    for numero, atto in enumerate(atti, start=1):
        indeterminabile = bool(atto.get("indeterminabile"))
        valore = None if indeterminabile else valore_lite(atto.get("tributo"), atto.get("sanzioni"))
        righe.append({"atto": numero, "valore": valore, "indeterminabile": indeterminabile, "cut": per_atto(valore, indeterminabile),
                      "nota": "" if valore is not None or indeterminabile else "Valore non dichiarato: CUT nella misura massima."})
    if esenzione in {"Prenotazione a debito", "Patrocinio a spese dello Stato"}:
        return {"righe": righe, "base": 0, "maggiorazione": 0, "totale": 0, "nota": f"{esenzione}: nessun versamento."}
    base = sum(r["cut"] for r in righe)
    maggiorazione = round(base * 0.5, 2) if base and not (pec_difensore and codice_fiscale_parte) else 0
    nota = "Aumento della metà: manca la PEC del difensore o il codice fiscale della parte (art. 13 c. 3-bis)." if maggiorazione else ""
    return {"righe": righe, "base": base, "maggiorazione": maggiorazione, "totale": base + maggiorazione, "nota": nota}


__all__ = ["INDETERMINABILE", "MASSIMO", "SCAGLIONI", "calcola", "per_atto", "valore_lite"]
