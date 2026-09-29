"""Conteggio del credito alla data: capitale, interessi, indennizzo forfettario.

- Transazioni commerciali (D.Lgs. 231/2002): interessi moratori al tasso BCE + 8 punti (art. 5), dal giorno
  successivo alla scadenza (art. 4); indennizzo di 40 euro per ogni credito (art. 6 c. 2).
- Altri crediti: interessi legali (art. 1284 c.c.) dalla mora.
- Gli acconti riducono il capitale dei documenti più vecchi; per l'imputazione prima agli interessi
  (art. 1194 c.c.) si usa lo strumento «Interessi con acconti».
I tassi sono quelli versionati nelle tabelle normative (strumento «Interessi legali e moratori»).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

INDENNIZZO_FORFETTARIO = 40.0


def conteggio(posizione: Any, al: date, calcola_interessi: Callable[[dict], dict]) -> dict[str, Any]:
    righe = []
    residuo_acconti = float(posizione.acconti or 0)
    totale_capitale = totale_interessi = 0.0
    modo = "moratori" if posizione.commerciale else "legali"
    for doc in sorted(posizione.documenti, key=lambda d: d.scadenza or d.data or ""):
        capitale = float(doc.importo)
        scalato = min(capitale, residuo_acconti)
        residuo_acconti -= scalato
        capitale = round(capitale - scalato, 2)
        dal = doc.decorrenza_interessi()
        interessi = 0.0
        if capitale > 0 and dal and dal <= al:
            esito = calcola_interessi({"int_tipo": modo, "int_capitale": capitale, "int_data_inizio": dal.isoformat(),
                                       "int_data_fine": al.isoformat()})
            interessi = float(esito.get("total_interest") or 0)
        totale_capitale += capitale
        totale_interessi += interessi
        righe.append({"documento": doc.numero or doc.data, "capitale": capitale, "dal": dal.isoformat() if dal else "",
                      "interessi": round(interessi, 2)})
    indennizzo = INDENNIZZO_FORFETTARIO * len(posizione.documenti) if posizione.commerciale else 0.0
    return {
        "al": al.isoformat(), "tipo_interessi": "moratori D.Lgs. 231/2002" if posizione.commerciale else "legali art. 1284 c.c.",
        "righe": righe, "capitale": round(totale_capitale, 2), "interessi": round(totale_interessi, 2),
        "indennizzo_forfettario": round(indennizzo, 2),
        "totale": round(totale_capitale + totale_interessi + indennizzo, 2),
    }


__all__ = ["INDENNIZZO_FORFETTARIO", "conteggio"]
