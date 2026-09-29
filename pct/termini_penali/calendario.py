"""Computo dei termini penali (art. 172 c.p.p.) e sospensione feriale (L. 742/1969).

- Art. 172 c.p.p.: termini a ore, giorni, mesi o anni secondo il calendario comune (c. 2);
  non si computa il giorno di decorrenza, si computa l'ultimo (c. 4); il termine *a giorni*
  che scade in giorno festivo è prorogato di diritto al giorno successivo non festivo (c. 3);
  il deposito telematico è tempestivo se accettato entro le ore 24 dell'ultimo giorno (c. 6-bis).
- Nel processo penale il sabato non è giorno festivo: la proroga del c. 3 riguarda domeniche e
  festività nazionali (L. 260/1949 e successive), non il sabato (diversamente dall'art. 155 c.p.c.).
- Art. 1 L. 7 ottobre 1969, n. 742: il decorso dei termini processuali è sospeso di diritto dal
  1° al 31 agosto e riprende alla fine del periodo; se il decorso ha inizio durante il periodo,
  l'inizio è differito alla fine di esso. Art. 2 (sostituito dall'art. 240-bis disp. att. c.p.p.):
  in materia penale la sospensione, compresi i termini delle indagini preliminari, non opera per
  gli imputati in custodia cautelare che vi rinunzino (personalmente o tramite il difensore), nei
  procedimenti per reati di criminalità organizzata e quando il giudice dichiara l'urgenza.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pct.termini_processuali import national_holidays


ROMA = ZoneInfo("Europe/Rome")


def oggi() -> date:
    """Il giorno italiano (il server gira in UTC)."""
    return datetime.now(ROMA).date()


def fmt(giorno: date | None) -> str:
    return giorno.strftime("%d/%m/%Y") if giorno else ""


def festivo(giorno: date) -> bool:
    """Domenica o festività nazionale (il sabato non è festivo nel processo penale)."""
    return giorno.weekday() == 6 or giorno in national_holidays(giorno.year)


def feriale(giorno: date) -> bool:
    return giorno.month == 8


def aggiungi_mesi(giorno: date, mesi: int) -> date:
    totale = (giorno.month - 1) + mesi
    anno = giorno.year + totale // 12
    mese = totale % 12 + 1
    return date(anno, mese, min(giorno.day, calendar.monthrange(anno, mese)[1]))


@dataclass
class Sospensione:
    """Se e perché la sospensione feriale si applica al termine."""

    applica: bool = True
    motivo: str = "Sospensione feriale dal 1° al 31 agosto (art. 1 L. 742/1969)."


@dataclass
class Computo:
    scadenza: date
    grezza: date
    passi: list[dict[str, str]] = field(default_factory=list)

    def riga(self, etichetta: str) -> dict[str, str]:
        return {"passaggio": etichetta, "data": fmt(self.scadenza)}


def sospensione_feriale(*, detenuto_con_rinuncia: bool = False, criminalita_organizzata: bool = False,
                        urgenza_dichiarata: bool = False, non_processuale: bool = False) -> Sospensione:
    if non_processuale:
        return Sospensione(False, "La sospensione feriale riguarda i termini processuali, non questo termine.")
    if detenuto_con_rinuncia:
        return Sospensione(False, "Imputato in custodia cautelare che rinuncia alla sospensione (art. 2 L. 742/1969; "
                                  "art. 240-bis disp. att. c.p.p.).")
    if criminalita_organizzata:
        return Sospensione(False, "Procedimento per reati di criminalità organizzata: la sospensione feriale non opera "
                                  "(art. 2 L. 742/1969).")
    if urgenza_dichiarata:
        return Sospensione(False, "Urgenza dichiarata dal giudice con ordinanza motivata (art. 2 L. 742/1969).")
    return Sospensione()


def termine_giorni(decorrenza: date, giorni: int, sospensione: Sospensione, etichetta: str = "") -> Computo:
    """Termine a giorni: escluso il giorno di decorrenza, agosto non computato, proroga se festivo."""
    passi = [{"passaggio": f"Decorrenza{': ' + etichetta if etichetta else ''} (giorno non computato, art. 172 c. 4)",
              "data": fmt(decorrenza)}]
    cursore = decorrenza
    contati = 0
    saltati = 0
    while contati < giorni:
        cursore += timedelta(days=1)
        if sospensione.applica and feriale(cursore):
            saltati += 1
            continue
        contati += 1
    if saltati:
        passi.append({"passaggio": f"Esclusi {saltati} giorni di sospensione feriale (1-31 agosto)", "data": ""})
    grezza = cursore
    passi.append({"passaggio": f"Ultimo giorno del termine di {giorni} giorni", "data": fmt(grezza)})
    while festivo(cursore):
        cursore += timedelta(days=1)
    if cursore != grezza:
        passi.append({"passaggio": "Scade in giorno festivo: prorogato al primo giorno non festivo (art. 172 c. 3)",
                      "data": fmt(cursore)})
    return Computo(cursore, grezza, passi)


def termine_mesi(decorrenza: date, mesi: int, sospensione: Sospensione, etichetta: str = "") -> Computo:
    """Termine a mesi o anni secondo il calendario comune; con la sospensione feriale si aggiungono
    i giorni di agosto compresi nel periodo (ripetendo finché il periodo non ne comprende altri).

    La proroga dell'art. 172 c. 3 riguarda i termini a giorni: per i termini a mesi la data resta
    quella di calendario e il passaggio lo segnala.
    """
    passi = [{"passaggio": f"Decorrenza{': ' + etichetta if etichetta else ''}", "data": fmt(decorrenza)}]
    fine = aggiungi_mesi(decorrenza, mesi)
    passi.append({"passaggio": f"Termine di {mesi} mesi secondo il calendario comune (art. 172 c. 2)", "data": fmt(fine)})
    if sospensione.applica:
        aggiunti = 0
        while True:
            dovuti = sum(1 for n in range(1, (fine - decorrenza).days + 1)
                         if feriale(decorrenza + timedelta(days=n))) - aggiunti
            if dovuti <= 0:
                break
            fine += timedelta(days=dovuti)
            aggiunti += dovuti
        if aggiunti:
            passi.append({"passaggio": f"Aggiunti {aggiunti} giorni di sospensione feriale", "data": fmt(fine)})
    if festivo(fine):
        passi.append({"passaggio": "Cade in giorno festivo: la proroga dell'art. 172 c. 3 è prevista per i termini a "
                                   "giorni, verificare l'orientamento applicabile", "data": fmt(fine)})
    return Computo(fine, fine, passi)


__all__ = ["Computo", "oggi", "Sospensione", "aggiungi_mesi", "festivo", "fmt", "sospensione_feriale", "termine_giorni",
           "termine_mesi"]
