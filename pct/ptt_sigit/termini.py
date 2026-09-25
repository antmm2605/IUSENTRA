"""Termini del processo tributario che il deposito telematico deve rispettare.

Fonti DGT («Termini processuali», «Costituzione in giudizio del ricorrente»,
«Costituzione in giudizio del resistente», «Discussione della causa»):

- costituzione del ricorrente: deposito entro 30 giorni dalla notificazione del
  ricorso, a pena di inammissibilità (art. 22 D.Lgs. 546/1992);
- costituzione del resistente con le controdeduzioni: entro 60 giorni dalla
  notificazione del ricorso (art. 23);
- ricorso: 60 giorni dalla notificazione dell'atto impugnato (art. 21);
- sospensione dei termini dal 1° al 31 agosto (l. 742/1969); il termine che
  scade in giorno festivo o di sabato è prorogato al primo giorno non festivo
  (art. 155 c.p.c.).

Il calcolo usa ``pct.scadenziario.calcola_termine``, lo stesso dello scadenziario.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pct.scadenziario import calcola_termine


def _data(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def termini(procedimento: dict[str, Any], *, oggi: date | None = None) -> list[dict[str, Any]]:
    """Le scadenze che derivano dalle date del procedimento, con il loro fondamento."""
    oggi = oggi or date.today()
    esito = []
    notifica_ricorso = _data(procedimento.get("notificaRicorso"))
    if notifica_ricorso:
        if procedimento.get("posizione", "ricorrente") == "resistente":
            scadenza = calcola_termine(notifica_ricorso, 60)
            esito.append({"id": "controdeduzioni", "titolo": "Costituzione in giudizio con le controdeduzioni",
                          "scadenza": scadenza.isoformat(), "norma": "art. 23 D.Lgs. 546/1992: 60 giorni dalla notifica del ricorso",
                          "perentorio": False})
        else:
            scadenza = calcola_termine(notifica_ricorso, 30)
            esito.append({"id": "costituzione", "titolo": "Costituzione in giudizio: deposito del ricorso nel PTT",
                          "scadenza": scadenza.isoformat(),
                          "norma": "art. 22 D.Lgs. 546/1992: 30 giorni dalla notifica del ricorso, a pena di inammissibilità",
                          "perentorio": True})
    for numero, atto in enumerate(procedimento.get("atti") or [], start=1):
        notifica_atto = _data(atto.get("dataNotifica"))
        if notifica_atto and not notifica_ricorso:
            scadenza = calcola_termine(notifica_atto, 60)
            esito.append({"id": f"ricorso-{numero}", "titolo": f"Notifica del ricorso contro l'atto {atto.get('numero') or numero}",
                          "scadenza": scadenza.isoformat(), "norma": "art. 21 D.Lgs. 546/1992: 60 giorni dalla notifica dell'atto",
                          "perentorio": True})
    for voce in esito:
        voce["giorni"] = (date.fromisoformat(voce["scadenza"]) - oggi).days
    return esito


__all__ = ["termini"]
