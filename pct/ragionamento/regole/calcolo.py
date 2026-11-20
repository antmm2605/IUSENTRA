"""Siamo nei termini? Il computo secondo la norma, con il motore dei termini del software.

Riusa `pct.termini_processuali.ItalianDeadlineCalculator` (art. 155 c.p.c.: escluso il giorno iniziale,
proroga del termine che scade di sabato o festivo; L. 742/1969: sospensione feriale dal 1° al 31 agosto,
esclusa per le controversie di lavoro, art. 3). Per un termine scaduto dice le conseguenze e i rimedi:
il termine perentorio non si proroga (art. 153, primo comma, c.p.c.) e si chiede la rimessione in termini
solo provando la causa non imputabile (art. 153, secondo comma); il termine ordinatorio si può prorogare
solo prima della scadenza (art. 154 c.p.c.).
"""

from __future__ import annotations

from datetime import date

from pct.termini_processuali import ItalianDeadlineCalculator

from ..modello import Rito, Termine
from ..testo import data_it, giorno

_CALCOLATORE = ItalianDeadlineCalculator()


def _feriale(rito: Rito) -> str:
    if rito.sospensione_feriale:
        return "si applica (art. 1 L. 742/1969, dal 1° al 31 agosto)"
    return "non si applica (controversia di lavoro, art. 3 L. 742/1969)"


def esito(scadenza: date | None, *, oggi: date, perentorio: bool | None, decorrenza: str = "", evento: str = "",
          computo: str = "", rito: Rito | None = None, conseguenze: str = "", natura: str = "") -> Termine:
    """Il termine completo: giorni residui, scaduto, conseguenze e rimedi."""
    termine = Termine(
        scadenza=scadenza.isoformat() if scadenza else "", decorrenza=decorrenza, evento_decorrenza=evento,
        computo=computo, sospensione_feriale=_feriale(rito) if rito else "", perentorio=perentorio, conseguenze=conseguenze, natura=natura,
    )
    if scadenza is None:
        return termine
    termine.giorni_residui = (scadenza - oggi).days
    termine.scaduto = scadenza < oggi
    if termine.scaduto and perentorio is not None:
        termine.rimedi = (
            "termine perentorio scaduto: non si proroga (art. 153, primo comma, c.p.c.); si può chiedere la rimessione "
            "in termini solo provando di essere incorsi nella decadenza per causa non imputabile (art. 153, secondo comma, c.p.c.)"
            if perentorio else
            "termine ordinatorio scaduto: la proroga si poteva chiedere solo prima della scadenza (art. 154 c.p.c.); se il "
            "ritardo dipende da causa non imputabile si chiede la rimessione in termini (art. 153, secondo comma, c.p.c.); "
            "altrimenti il giudice decide sulle prove in atti (art. 2697 c.c.)"
        )
    return termine


def in_avanti(base: date, giorni: int, *, rito: Rito, oggi: date, perentorio: bool | None, evento: str,
              norma: str, conseguenze: str = "", feriale: bool | None = None) -> Termine:
    """N giorni da un evento (notifica, comunicazione, pronuncia), contati secondo l'art. 155 c.p.c."""
    sospende = rito.sospensione_feriale if feriale is None else feriale
    calcolo = _CALCOLATORE.calculate(
        base, giorni, direction="forward", period_type="days", suspend_august=sospende,
        ferial_suspension_policy="applies" if sospende else "not_applicable", reference_law=norma,
    )
    scadenza = giorno(calcolo.get("deadline"))
    computo = (f"{giorni} giorni dal {data_it(base)} ({evento}), escluso il giorno iniziale; proroga al primo giorno non "
               f"festivo se la scadenza cade di sabato o festivo (art. 155 c.p.c.)")
    termine = esito(scadenza, oggi=oggi, perentorio=perentorio, decorrenza=base.isoformat(), evento=evento,
                    computo=computo, rito=rito, conseguenze=conseguenze)
    if feriale is not None and not feriale:
        termine.sospensione_feriale = "non si applica (termine di adempimento, non processuale)"
    return termine


def a_ritroso(udienza: date, giorni: int, *, rito: Rito, oggi: date, perentorio: bool | None, evento: str,
              norma: str, conseguenze: str = "", prudenziale: bool = True) -> Termine:
    """«Almeno N giorni prima dell'udienza»: si conta all'indietro e la scadenza che cade di festivo si anticipa.

    Regola unica dello studio per i termini a ritroso (decisione dell'avvocato del 29/10/2026, la stessa dello
    scadenziario e delle proposte dalla PEC, ``pct.termini_processuali.LETTURA_PRUDENZIALE``): la data da rispettare è
    quella a giorni liberi (esclusi il giorno dell'udienza e quello della scadenza); accanto, la scadenza di legge
    a giorni pieni. Un deposito alla data prudenziale non è tardivo sotto nessuna delle due letture.
    """
    opzioni = dict(direction="backward", period_type="days", suspend_august=rito.sospensione_feriale,
                   ferial_suspension_policy="applies" if rito.sospensione_feriale else "not_applicable", reference_law=norma)
    di_legge = giorno(_CALCOLATORE.calculate(udienza, giorni, **opzioni).get("deadline"))
    if not prudenziale:
        computo = (f"{giorni} giorni prima dell'udienza del {data_it(udienza)}, contati a ritroso a giorni pieni; se "
                   f"l'ultimo giorno utile è sabato o festivo si anticipa al giorno non festivo precedente (art. 155 c.p.c.)")
        return esito(di_legge, oggi=oggi, perentorio=perentorio, decorrenza=udienza.isoformat(), evento=evento,
                     computo=computo, rito=rito, conseguenze=conseguenze)
    scadenza = giorno(_CALCOLATORE.calculate(udienza, giorni, free_term=True, **opzioni).get("deadline"))
    computo = (f"{giorni} giorni prima dell'udienza del {data_it(udienza)}, contati a ritroso a giorni liberi (data da "
               f"rispettare, lettura prudenziale dello studio); se l'ultimo giorno utile è sabato o festivo si anticipa "
               f"al giorno non festivo precedente (art. 155 c.p.c.)")
    if di_legge and scadenza and di_legge != scadenza:
        computo += f"; scadenza di legge secondo la lettura a giorni pieni: {data_it(di_legge)}"
    return esito(scadenza, oggi=oggi, perentorio=perentorio, decorrenza=udienza.isoformat(), evento=evento,
                 computo=computo, rito=rito, conseguenze=conseguenze)


__all__ = ["a_ritroso", "esito", "in_avanti"]
