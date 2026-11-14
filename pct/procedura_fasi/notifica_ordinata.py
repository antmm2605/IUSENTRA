"""La notifica ordinata dal giudice non si «valuta»: si esegue nel termine assegnato.

Nel rito del lavoro il ricorso e il decreto di fissazione dell'udienza sono notificati al convenuto, a cura
dell'attore, entro dieci giorni dalla data di pronuncia del decreto e almeno trenta giorni prima dell'udienza (art.
415, quarto e quinto comma, c.p.c.); in genere, quando un provvedimento del giudice ordina la notificazione a una
parte (art. 137 c.p.c.), la notifica è un adempimento dovuto e non una scelta del difensore. Se lo scadenziario del
fascicolo porta il termine per notificare «ricorso e decreto», la Lettura non chiede di confermare «se la notifica è
necessaria»: indica l'adempimento e il termine.

Collaudo 10/11/2026 (Tribunale di Vicenza, lavoro): «Esamina e conferma se la notifica è necessaria» accanto al
termine «Notifica di ricorso e decreto - almeno 30 giorni prima dell'udienza» dell'08/01/2027.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

_RE_ORDINATA = re.compile(r"\bnotific\w*\s+(?:di\s+|del\s+)?ricorso\s+e\s+(?:del\s+)?decreto|\bnotific\w*\s+.*ordinat\w*\s+dal\s+giudice", re.I)
STATI_DA_VALUTARE = {"DETECTED", "NEEDS_REVIEW"}


def _giorno(valore: Any) -> date | None:
    testo = " ".join(str(valore or "").split())[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    return None


def termine_di_notifica_ordinata(scadenze: Iterable[dict[str, Any]], oggi: date | None = None) -> dict[str, Any] | None:
    """La scadenza aperta (o in bozza) che dice di notificare ricorso e decreto: titolo e data; None se non c'è."""
    candidati = []
    for scadenza in scadenze or ():
        if " ".join(str(scadenza.get("stato") or "").split()).upper() not in {"APERTO", "APERTA", "BOZZA", ""}:
            continue
        if not _RE_ORDINATA.search(str(scadenza.get("titolo") or "")):
            continue
        giorno = _giorno(scadenza.get("data") or scadenza.get("data_scadenza"))
        if giorno and (oggi is None or giorno >= oggi):
            candidati.append((giorno, scadenza))
    if not candidati:
        return None
    giorno, scadenza = min(candidati, key=lambda voce: voce[0])
    return {"data": giorno, "titolo": str(scadenza.get("titolo") or ""), "bozza": str(scadenza.get("stato") or "").upper() == "BOZZA"}


__all__ = ["STATI_DA_VALUTARE", "termine_di_notifica_ordinata"]
