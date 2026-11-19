"""Calcolo delle date con il motore dei termini di IUSENTRA (pct/termini_processuali.py).

Termini processuali: si esclude il giorno iniziale, si sospende dal 1° al 31 agosto quando la legge lo prevede
(art. 1 l. 742/1969) e la scadenza di sabato o festiva è prorogata al primo giorno non festivo (art. 155, commi 4 e 5,
c.p.c.). Termini sostanziali (decadenze, prescrizioni, termini di pagamento): niente sospensione feriale e niente
proroga del sabato, che vale solo per gli atti processuali; resta la proroga del giorno festivo (art. 2963, comma 3, c.c.).
"""
from __future__ import annotations

from datetime import date


def _calcola(dal: date, quanti: int, tipo: str, sospensione_feriale: bool, sostanziale: bool) -> date:
    from pct.termini_processuali import ItalianDeadlineCalculator

    esito = ItalianDeadlineCalculator().calculate(dal, quanti, period_type=tipo, suspend_august=sospensione_feriale,
                                                  extend_saturday=not sostanziale, template_code="LEX_HARNESS",
                                                  reference_law="")
    return date.fromisoformat(esito["deadline"])


def termine_giorni(dal: date, giorni: int, *, sospensione_feriale: bool = True, sostanziale: bool = False) -> date:
    return _calcola(dal, giorni, "days", sospensione_feriale and not sostanziale, sostanziale)


def termine_mesi(dal: date, mesi: int, *, sospensione_feriale: bool = True, sostanziale: bool = False) -> date:
    return _calcola(dal, mesi, "months", sospensione_feriale and not sostanziale, sostanziale)


def termine_anni(dal: date, anni: int, *, sostanziale: bool = True) -> date:
    return _calcola(dal, anni * 12, "months", False, sostanziale)


_GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


def data_breve(d: date) -> str:
    return f"{_GIORNI[d.weekday()]} {d.strftime('%d/%m/%Y')}"
