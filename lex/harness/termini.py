"""Calcolo delle date con il motore dei termini di IUSENTRA (pct/termini_processuali.py).

Il motore esclude il giorno iniziale, applica la sospensione feriale dal 1° al 31 agosto quando richiesta
(art. 1 l. 742/1969) e proroga al primo giorno non festivo (art. 155 c.p.c.).
"""
from __future__ import annotations

from datetime import date


def _calcola(dal: date, quanti: int, tipo: str, sospensione_feriale: bool) -> date:
    from pct.termini_processuali import ItalianDeadlineCalculator

    esito = ItalianDeadlineCalculator().calculate(dal, quanti, period_type=tipo, suspend_august=sospensione_feriale,
                                                  template_code="LEX_HARNESS", reference_law="")
    return date.fromisoformat(esito["deadline"])


def termine_giorni(dal: date, giorni: int, *, sospensione_feriale: bool = True) -> date:
    return _calcola(dal, giorni, "days", sospensione_feriale)


def termine_mesi(dal: date, mesi: int, *, sospensione_feriale: bool = True) -> date:
    return _calcola(dal, mesi, "months", sospensione_feriale)


_GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


def data_breve(d: date) -> str:
    return f"{_GIORNI[d.weekday()]} {d.strftime('%d/%m/%Y')}"
