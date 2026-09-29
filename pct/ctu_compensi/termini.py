"""Termini della liquidazione dell'ausiliario del magistrato.

- Art. 71 D.P.R. 115/2002: la domanda di liquidazione di onorari e spese è presentata, a pena di
  decadenza, entro cento giorni dal compimento delle operazioni (per il CTU: deposito della relazione
  o dell'ultima integrazione richiesta dal giudice).
- Art. 170 D.P.R. 115/2002 e art. 15 D.Lgs. 150/2011: opposizione al decreto di pagamento entro
  trenta giorni dalla comunicazione.

Le date sono prudenziali: nessuna sospensione feriale e nessuno slittamento al primo giorno non
festivo, così la scadenza proposta non è mai successiva a quella di legge. Nascono in bozza e
l'avvocato le conferma nello scadenziario.
"""

from __future__ import annotations

from datetime import date, timedelta

GIORNI_ISTANZA = 100
GIORNI_OPPOSIZIONE = 30
NOTA_PRUDENZIALE = "Termine prudenziale: non considera la sospensione feriale né lo slittamento al primo giorno non festivo."


def _data(valore: str) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def termine_istanza(data_operazioni: str) -> dict[str, str] | None:
    inizio = _data(data_operazioni)
    if inizio is None:
        return None
    return {"chiave": "istanza_liquidazione", "data": (inizio + timedelta(days=GIORNI_ISTANZA)).isoformat(),
            "titolo": "Istanza di liquidazione del compenso (a pena di decadenza)",
            "norma": "art. 71 D.P.R. 115/2002: 100 giorni dal compimento delle operazioni", "nota": NOTA_PRUDENZIALE}


def termine_opposizione(data_comunicazione: str) -> dict[str, str] | None:
    inizio = _data(data_comunicazione)
    if inizio is None:
        return None
    return {"chiave": "opposizione_decreto", "data": (inizio + timedelta(days=GIORNI_OPPOSIZIONE)).isoformat(),
            "titolo": "Opposizione al decreto di liquidazione del compenso",
            "norma": "art. 170 D.P.R. 115/2002 e art. 15 D.Lgs. 150/2011: 30 giorni dalla comunicazione", "nota": NOTA_PRUDENZIALE}


__all__ = ["GIORNI_ISTANZA", "GIORNI_OPPOSIZIONE", "NOTA_PRUDENZIALE", "termine_istanza", "termine_opposizione"]
