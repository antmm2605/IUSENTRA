"""Calcolatori giuridici modulari.

Ogni modulo copre una materia con base normativa dichiarata nel docstring:

- ``interessi_acconti``: imputazione degli acconti ex art. 1194 c.c.
- ``maggior_danno``: maggior danno da svalutazione ex art. 1224, comma 2, c.c.
- ``danno_parentale``: perdita del rapporto parentale (Tabelle Milano 2024).
- ``usufrutto``: usufrutto vitalizio e nuda proprietà (D.P.R. 131/1986).
- ``quote_riserva``: quote di riserva dei legittimari (artt. 536-556 c.c.).
- ``assegno_mantenimento``: stima orientativa dell'assegno (art. 337-ter c.c.,
  art. 5 L. 898/1970).

L'orchestrazione applicativa resta in ``pct.strumenti_legali``.
"""
from pct.calcolatori import (  # noqa: F401
    assegno_mantenimento,
    danno_parentale,
    interessi_acconti,
    maggior_danno,
    quote_riserva,
    usufrutto,
)

__all__ = [
    "assegno_mantenimento",
    "danno_parentale",
    "interessi_acconti",
    "maggior_danno",
    "quote_riserva",
    "usufrutto",
]
