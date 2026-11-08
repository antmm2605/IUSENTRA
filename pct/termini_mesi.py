"""Termini a mesi e ad anni con la sospensione feriale: regola unica per i tre motori dei termini.

Base normativa (testo vigente verificato su Normattiva l'08/11/2026):

- art. 155, secondo comma, c.p.c.: «Per il computo dei termini a mesi o ad anni, si osserva il calendario comune»
  (https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art155);
- art. 1 L. 7 ottobre 1969, n. 742: il decorso dei termini processuali è sospeso dal 1° al 31 agosto e riprende
  alla fine del periodo; «Ove il decorso abbia inizio durante il periodo di sospensione, l'inizio stesso è
  differito alla fine di detto periodo»
  (https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1969-10-07;742~art1);
- art. 3 L. 742/1969: la sospensione non si applica alle controversie di lavoro e previdenza (artt. 429 e 459
  c.p.c. nel testo originario, oggi artt. 409 e 442) né alle cause dell'art. 92 ord. giud.: chi chiama decide
  `sospensione=False` per quelle materie;
- Cass. SS.UU. n. 21197/2009 (dies a quo della sentenza depositata nel periodo feriale differito alla fine del
  periodo).

Calcolo: se l'evento cade in un giorno sospeso, la decorrenza si sposta all'ultimo giorno del periodo di
sospensione (31 agosto); i mesi si contano a calendario comune da quella decorrenza; poi si aggiungono i giorni
sospesi attraversati dopo la decorrenza (es. un agosto successivo), ripetendo finché il numero si stabilizza.
Esempio: sentenza depositata il 10/08/2026 (art. 327 c.p.c.) -> decorrenza 31/08/2026 -> sei mesi 28/02/2027;
la proroga del giorno festivo (domenica -> 01/03/2027) resta al chiamante.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

GiornoSospeso = Callable[[date], bool]


def agosto(giorno: date) -> bool:
    """Periodo di sospensione dell'art. 1 L. 742/1969: dal 1° al 31 agosto."""
    return giorno.month == 8


def aggiungi_mesi(giorno: date, mesi: int) -> date:
    """Calendario comune (art. 155 c.p.c.): stesso giorno del mese, o l'ultimo se il mese è più corto."""
    totale = (giorno.month - 1) + mesi
    anno = giorno.year + totale // 12
    mese = totale % 12 + 1
    return date(anno, mese, min(giorno.day, calendar.monthrange(anno, mese)[1]))


def decorrenza_differita(evento: date, sospeso: GiornoSospeso = agosto) -> date:
    """Art. 1 L. 742/1969: se il decorso inizia in un giorno sospeso, l'inizio va alla fine del periodo."""
    if not sospeso(evento):
        return evento
    giorno = evento
    while sospeso(giorno + timedelta(days=1)):
        giorno += timedelta(days=1)
    return giorno


@dataclass(frozen=True)
class EsitoMesi:
    decorrenza: date
    base: date
    giorni_sospesi: int
    scadenza: date
    # True quando l'evento cade nel periodo sospeso e la decorrenza è spostata alla sua fine.
    differita: bool = False


def scadenza_a_mesi(evento: date, mesi: int, *, sospensione: bool, sospeso: GiornoSospeso = agosto) -> EsitoMesi:
    """Scadenza «grezza» (prima della proroga del festivo) di un termine a mesi in avanti."""
    if not sospensione:
        base = aggiungi_mesi(evento, mesi)
        return EsitoMesi(evento, base, 0, base)
    decorrenza = decorrenza_differita(evento, sospeso)
    base = aggiungi_mesi(decorrenza, mesi)
    scadenza, giorni = base, -1
    while True:
        conteggio = sum(1 for n in range((scadenza - decorrenza).days) if sospeso(decorrenza + timedelta(days=n + 1)))
        if conteggio == giorni:
            return EsitoMesi(decorrenza, base, giorni, scadenza, differita=decorrenza != evento)
        giorni = conteggio
        scadenza = base + timedelta(days=giorni)


__all__ = ["EsitoMesi", "aggiungi_mesi", "agosto", "decorrenza_differita", "scadenza_a_mesi"]
