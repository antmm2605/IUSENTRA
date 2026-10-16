"""Periodi delle consultazioni: riuso del parser date, nessuna lettura o scrittura."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from lex.risposte_certe import analizza_date_domanda


@dataclass(frozen=True)
class QueryDates:
    ranges: tuple[tuple[date, date], ...] = ()
    error: str = ""


def resolve_query_dates(question: str, *, today: date) -> QueryDates:
    """Restituisce solo periodi dimostrati dalle parole della domanda.

    Il chiamante fornisce il giorno civile Europe/Rome. Una data impossibile o
    un intervallo invertito blocca la selezione, invece di ampliarla.
    """
    text = " ".join(question.casefold().split())
    dates, invalid = analizza_date_domanda(text)
    if invalid:
        return QueryDates(error="Data non valida: " + ", ".join(invalid))
    relative = {"oggi": 0, "ieri": -1, "domani": 1, "dopodomani": 2,
                "l'altro ieri": -2, "avantieri": -2}
    text = text.replace("’", "'")
    for match in re.finditer(r"\b(l'altro ieri|avantieri|dopodomani|oggi|ieri|domani)\b", text):
        dates.append(today + timedelta(days=relative[match.group()]))
    if re.search(r"\b(?:dal|dalla)\s+(?:\d|oggi\b|ieri\b|domani\b)", text) and not re.search(r"\b(?:al|alla)\b", text):
        return QueryDates(error="Indica anche la data finale dell’intervallo.")
    if re.search(r"\b(?:dal|dalla)\b", text) and re.search(r"\b(?:al|alla)\b", text):
        if len(dates) != 2:
            return QueryDates(error="Indica le due date complete dell’intervallo.")
        if dates[1] < dates[0]:
            return QueryDates(error="La data finale precede quella iniziale.")
        return QueryDates(ranges=((dates[0], dates[1]),))
    if re.search(r"\bquesta settimana\b", text):
        if dates:
            return QueryDates(error="La domanda indica sia una settimana sia giorni specifici.")
        start = today - timedelta(days=today.weekday())
        return QueryDates(ranges=((start, start + timedelta(days=6)),))
    if not dates and re.search(r"\b\d{1,2}(?:[./-]|\s+)\d{1,2}\b|\b(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b", text):
        return QueryDates(error="Indica una data completa con giorno, mese e anno, oppure un intervallo.")
    return QueryDates(ranges=tuple((value, value) for value in sorted(set(dates))))
