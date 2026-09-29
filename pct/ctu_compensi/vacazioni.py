"""Onorari a tempo (vacazioni) degli ausiliari del magistrato.

Art. 4 L. 319/1980 (richiamato dall'art. 50 D.P.R. 115/2002) con gli importi del D.M. 30/05/2002:
- la vacazione è di due ore;
- l'onorario della vacazione si divide solo per metà: trascorsa un'ora e un quarto è dovuto per intero;
- non si liquidano più di quattro vacazioni al giorno per ciascun incarico, salvo le attività svolte
  alla presenza dell'autorità giudiziaria (il numero risulta dal verbale);
- l'onorario può essere raddoppiato se per le operazioni è fissato un termine non superiore a cinque
  giorni, aumentato fino alla metà se il termine non supera i quindici giorni.

Corte cost. 16/2025 (dep. 10/02/2025) ha dichiarato illegittimo l'art. 4, secondo comma, L. 319/1980
nella parte in cui liquida le vacazioni successive alla prima con un onorario inferiore: ogni vacazione
vale quindi quanto la prima (14,68 euro), non più 8,15 euro.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from pct.ctu_compensi.tabella_dm_2002 import VACAZIONE_EURO

DURATA_MINUTI = 120
SOGLIA_INTERA_MINUTI = 75
MASSIMO_GIORNALIERO = 4.0


def vacazioni_da_minuti(minuti: int) -> float:
    """Vacazioni per una durata: blocchi interi di due ore, resto a metà o per intero oltre 1h15'."""

    minuti = max(int(minuti or 0), 0)
    intere, resto = divmod(minuti, DURATA_MINUTI)
    if resto > SOGLIA_INTERA_MINUTI:
        return float(intere + 1)
    if resto > 0:
        return intere + 0.5
    return float(intere)


def conteggio_giornaliero(attivita: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Vacazioni per giorno con il tetto di quattro (escluse le attività alla presenza del giudice)."""

    minuti_ordinari: dict[str, int] = defaultdict(int)
    minuti_udienza: dict[str, int] = defaultdict(int)
    for voce in attivita:
        giorno = str(voce.get("data") or "")[:10]
        if not giorno:
            continue
        minuti = max(int(voce.get("minuti") or 0), 0)
        (minuti_udienza if voce.get("presenza_giudice") else minuti_ordinari)[giorno] += minuti
    giorni = []
    for giorno in sorted(set(minuti_ordinari) | set(minuti_udienza)):
        ordinarie = vacazioni_da_minuti(minuti_ordinari[giorno])
        riconosciute = min(ordinarie, MASSIMO_GIORNALIERO)
        udienza = vacazioni_da_minuti(minuti_udienza[giorno])
        giorni.append({"data": giorno, "minuti": minuti_ordinari[giorno] + minuti_udienza[giorno],
                       "vacazioni": riconosciute + udienza, "oltre_tetto": round(ordinarie - riconosciute, 1)})
    return {"giorni": giorni, "vacazioni": sum(g["vacazioni"] for g in giorni),
            "escluse_per_tetto": round(sum(g["oltre_tetto"] for g in giorni), 1)}


def fattore_urgenza(termine_giorni: int | None, aumento_scelto: float | None = None) -> tuple[float, str]:
    """Maggiorazione per termine breve: doppio fino a 5 giorni, fino alla metà fino a 15 giorni."""

    if not termine_giorni or termine_giorni <= 0:
        return 1.0, ""
    if termine_giorni <= 5:
        return 2.0, "Onorario raddoppiato: termine per le operazioni non superiore a cinque giorni (art. 4 L. 319/1980)."
    if termine_giorni <= 15:
        fattore = 1.5 if aumento_scelto is None else min(max(float(aumento_scelto), 1.0), 1.5)
        return fattore, "Aumento fino alla metà: termine per le operazioni non superiore a quindici giorni (art. 4 L. 319/1980)."
    return 1.0, ""


def onorario_vacazioni(vacazioni: float, *, termine_giorni: int | None = None, aumento_urgenza: float | None = None) -> dict[str, Any]:
    fattore, nota = fattore_urgenza(termine_giorni, aumento_urgenza)
    base = round(float(vacazioni) * VACAZIONE_EURO, 2)
    return {"vacazioni": float(vacazioni), "importo_vacazione": VACAZIONE_EURO, "base": base, "fattore_urgenza": fattore,
            "onorario": round(base * fattore, 2), "note": [n for n in (nota,) if n]}


__all__ = ["DURATA_MINUTI", "MASSIMO_GIORNALIERO", "conteggio_giornaliero", "fattore_urgenza", "onorario_vacazioni",
           "vacazioni_da_minuti"]
