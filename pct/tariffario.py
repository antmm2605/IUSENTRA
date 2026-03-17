"""
pct/tariffario.py — Tariffario forense ex DM 55/2014 e s.m.i.

Implementa le tabelle degli onorari per le prestazioni legali secondo
il Decreto Ministeriale 10 marzo 2014, n. 55 (aggiornato dal DM 37/2018).

Struttura:
  - Scaglioni di valore della controversia
  - Fasi: STUDIO, INTRODUTTIVA, ISTRUTTORIA, DECISIONALE, ESECUTIVA
  - Per ognuna: importo minimo, base, massimo
  - Grado di giudizio: GIUDICE_DI_PACE, TRIBUNALE, CORTE_APPELLO, CASSAZIONE
  - Materie: CIVILE_COGN, LAVORO, PREVIDENZA, ESEC_IMMO, ESEC_MOB, VOLONTARIA, PENALE
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ================================================================ Enumerazioni

class Materia(str, Enum):
    CIVILE_COGN  = "Civile di cognizione"
    LAVORO       = "Controversie di lavoro"
    PREVIDENZA   = "Previdenza e assistenza"
    ESEC_IMMO    = "Esecuzione immobiliare"
    ESEC_MOB     = "Esecuzione mobiliare"
    VOLONTARIA   = "Volontaria giurisdizione"
    PENALE       = "Penale"
    STRAGIUD     = "Stragiudiziale / Consulenza"


class Grado(str, Enum):
    GIUDICE_DI_PACE = "Giudice di Pace"
    TRIBUNALE       = "Tribunale"
    CORTE_APPELLO   = "Corte d'Appello"
    CASSAZIONE      = "Corte di Cassazione"


class Fase(str, Enum):
    STUDIO       = "Studio"
    INTRODUTTIVA = "Introduttiva"
    ISTRUTTORIA  = "Istruttoria / Istruzione"
    DECISIONALE  = "Decisionale"
    ESECUTIVA    = "Esecutiva"


# ================================================================ Strutture dati

@dataclass
class ScaglioneFase:
    """Importi (min, base, max) per una singola fase di uno scaglione."""
    minimo: float
    base:   float
    massimo: float


@dataclass
class Scaglione:
    """Scaglione di valore con importi per le cinque fasi."""
    valore_da:   float          # incluso (0 = senza limite inferiore)
    valore_a:    float          # incluso (float('inf') = senza limite)
    label:       str
    fasi: Dict[Fase, ScaglioneFase] = field(default_factory=dict)


@dataclass
class RisultatoCalcolo:
    """Risultato del calcolo del compenso."""
    materia: str
    grado: str
    valore_controversia: float
    scaglione: str
    fasi_selezionate: List[str]
    # Per ogni fase: (min, base, max)
    dettaglio: Dict[str, Tuple[float, float, float]]
    totale_minimo: float
    totale_base: float
    totale_massimo: float
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "materia": self.materia,
            "grado": self.grado,
            "valore_controversia": self.valore_controversia,
            "scaglione": self.scaglione,
            "fasi_selezionate": self.fasi_selezionate,
            "dettaglio": {k: list(v) for k, v in self.dettaglio.items()},
            "totale_minimo": self.totale_minimo,
            "totale_base": self.totale_base,
            "totale_massimo": self.totale_massimo,
            "note": self.note,
        }


# ================================================================ Tabelle DM 55/2014
# Fonte: Allegato n. 2 — D.M. 10 marzo 2014, n. 55 (mod. D.M. 37/2018)

def _scaglioni_civile_tribunale() -> List[Scaglione]:
    """Tabella per cause civili di cognizione — Tribunale (art. 4 DM 55/2014)."""
    F = Fase
    S = ScaglioneFase
    return [
        Scaglione(0, 1100, "Fino a € 1.100 (o indeterminabile)", {
            F.STUDIO:       S(200,  350,   525),
            F.INTRODUTTIVA: S(200,  350,   525),
            F.ISTRUTTORIA:  S(275,  500,   750),
            F.DECISIONALE:  S(275,  500,   750),
            F.ESECUTIVA:    S(200,  350,   525),
        }),
        Scaglione(1100, 5200, "Da € 1.100 a € 5.200", {
            F.STUDIO:       S(300,  550,   825),
            F.INTRODUTTIVA: S(300,  550,   825),
            F.ISTRUTTORIA:  S(450,  800,  1200),
            F.DECISIONALE:  S(450,  800,  1200),
            F.ESECUTIVA:    S(300,  550,   825),
        }),
        Scaglione(5200, 26000, "Da € 5.200 a € 26.000", {
            F.STUDIO:       S(700,  1300,  1950),
            F.INTRODUTTIVA: S(700,  1300,  1950),
            F.ISTRUTTORIA:  S(1000, 1800,  2700),
            F.DECISIONALE:  S(1000, 1800,  2700),
            F.ESECUTIVA:    S(700,  1300,  1950),
        }),
        Scaglione(26000, 52000, "Da € 26.000 a € 52.000", {
            F.STUDIO:       S(1000, 2000,  3000),
            F.INTRODUTTIVA: S(1000, 2000,  3000),
            F.ISTRUTTORIA:  S(1500, 3000,  4500),
            F.DECISIONALE:  S(1500, 3000,  4500),
            F.ESECUTIVA:    S(1000, 2000,  3000),
        }),
        Scaglione(52000, 260000, "Da € 52.000 a € 260.000", {
            F.STUDIO:       S(2000, 4000,  6000),
            F.INTRODUTTIVA: S(2000, 4000,  6000),
            F.ISTRUTTORIA:  S(3000, 5500,  8250),
            F.DECISIONALE:  S(3000, 5500,  8250),
            F.ESECUTIVA:    S(2000, 4000,  6000),
        }),
        Scaglione(260000, 520000, "Da € 260.000 a € 520.000", {
            F.STUDIO:       S(4000, 7000,  10500),
            F.INTRODUTTIVA: S(4000, 7000,  10500),
            F.ISTRUTTORIA:  S(5000, 9000,  13500),
            F.DECISIONALE:  S(5000, 9000,  13500),
            F.ESECUTIVA:    S(4000, 7000,  10500),
        }),
        Scaglione(520000, float("inf"), "Oltre € 520.000", {
            F.STUDIO:       S(8000,  14000, 21000),
            F.INTRODUTTIVA: S(8000,  14000, 21000),
            F.ISTRUTTORIA:  S(9000,  16000, 24000),
            F.DECISIONALE:  S(9000,  16000, 24000),
            F.ESECUTIVA:    S(8000,  14000, 21000),
        }),
    ]


def _scaglioni_lavoro() -> List[Scaglione]:
    """Controversie di lavoro — coefficienti ridotti (art. 5 DM 55/2014)."""
    # Valori approssimativi: ~80% del civile
    F = Fase
    S = ScaglioneFase
    return [
        Scaglione(0, 1100, "Fino a € 1.100 (o indeterminabile)", {
            F.STUDIO:       S(165,  280,   420),
            F.INTRODUTTIVA: S(165,  280,   420),
            F.ISTRUTTORIA:  S(220,  400,   600),
            F.DECISIONALE:  S(220,  400,   600),
            F.ESECUTIVA:    S(165,  280,   420),
        }),
        Scaglione(1100, 5200, "Da € 1.100 a € 5.200", {
            F.STUDIO:       S(240,  440,   660),
            F.INTRODUTTIVA: S(240,  440,   660),
            F.ISTRUTTORIA:  S(360,  640,   960),
            F.DECISIONALE:  S(360,  640,   960),
            F.ESECUTIVA:    S(240,  440,   660),
        }),
        Scaglione(5200, 26000, "Da € 5.200 a € 26.000", {
            F.STUDIO:       S(560,  1040,  1560),
            F.INTRODUTTIVA: S(560,  1040,  1560),
            F.ISTRUTTORIA:  S(800,  1440,  2160),
            F.DECISIONALE:  S(800,  1440,  2160),
            F.ESECUTIVA:    S(560,  1040,  1560),
        }),
        Scaglione(26000, 52000, "Da € 26.000 a € 52.000", {
            F.STUDIO:       S(800,  1600,  2400),
            F.INTRODUTTIVA: S(800,  1600,  2400),
            F.ISTRUTTORIA:  S(1200, 2400,  3600),
            F.DECISIONALE:  S(1200, 2400,  3600),
            F.ESECUTIVA:    S(800,  1600,  2400),
        }),
        Scaglione(52000, float("inf"), "Oltre € 52.000", {
            F.STUDIO:       S(1600, 3200,  4800),
            F.INTRODUTTIVA: S(1600, 3200,  4800),
            F.ISTRUTTORIA:  S(2400, 4400,  6600),
            F.DECISIONALE:  S(2400, 4400,  6600),
            F.ESECUTIVA:    S(1600, 3200,  4800),
        }),
    ]


def _scaglioni_penale() -> List[Scaglione]:
    """Procedimenti penali — Tabella B DM 55/2014 (semplificata)."""
    # Il penale ha fasi diverse: indagini, udienza preliminare, dibattimento, impugnazione
    # Qui usiamo la struttura a 5 fasi per uniformità
    F = Fase
    S = ScaglioneFase
    return [
        Scaglione(0, float("inf"), "Penale (valore non applicabile)", {
            F.STUDIO:       S(350,  600,   900),      # Indagini preliminari
            F.INTRODUTTIVA: S(350,  600,   900),      # Udienza preliminare / GIP
            F.ISTRUTTORIA:  S(500,  900,  1350),      # Dibattimento
            F.DECISIONALE:  S(500,  900,  1350),      # Sentenza / Discussione
            F.ESECUTIVA:    S(350,  600,   900),      # Esecuzione / Impugnazione
        }),
    ]


# Coefficienti per grado di giudizio rispetto al Tribunale
_COEFF_GRADO = {
    Grado.GIUDICE_DI_PACE: 0.50,
    Grado.TRIBUNALE:       1.00,
    Grado.CORTE_APPELLO:   1.30,
    Grado.CASSAZIONE:      1.60,
}

# Tabelle per materia
_TABELLE: Dict[Materia, List[Scaglione]] = {
    Materia.CIVILE_COGN:  _scaglioni_civile_tribunale(),
    Materia.LAVORO:       _scaglioni_lavoro(),
    Materia.PREVIDENZA:   _scaglioni_lavoro(),      # stessa tabella lavoro
    Materia.ESEC_IMMO:    _scaglioni_civile_tribunale(),
    Materia.ESEC_MOB:     _scaglioni_civile_tribunale(),
    Materia.VOLONTARIA:   _scaglioni_civile_tribunale(),
    Materia.PENALE:       _scaglioni_penale(),
    Materia.STRAGIUD:     _scaglioni_civile_tribunale(),
}


# ================================================================ Calcolatore

def calcola_compenso(
    materia: Materia,
    grado: Grado,
    valore: float,
    fasi: List[Fase],
) -> RisultatoCalcolo:
    """
    Calcola il compenso secondo DM 55/2014.

    Args:
        materia:  Tipo di causa/attività.
        grado:    Grado di giudizio.
        valore:   Valore della controversia in euro (0 = indeterminabile).
        fasi:     Elenco delle fasi da considerare nel calcolo.

    Returns:
        RisultatoCalcolo con importi minimi, base e massimi.
    """
    tabella = _TABELLE.get(materia, _scaglioni_civile_tribunale())
    coeff = _COEFF_GRADO.get(grado, 1.0)

    # Trova scaglione
    sc = tabella[0]
    for scaglione in tabella:
        if valore <= scaglione.valore_a:
            sc = scaglione
            break

    dettaglio: Dict[str, Tuple[float, float, float]] = {}
    tot_min = tot_base = tot_max = 0.0

    for fase in fasi:
        sf = sc.fasi.get(fase)
        if not sf:
            continue
        vmin  = round(sf.minimo  * coeff, 2)
        vbase = round(sf.base    * coeff, 2)
        vmax  = round(sf.massimo * coeff, 2)
        dettaglio[fase.value] = (vmin, vbase, vmax)
        tot_min  += vmin
        tot_base += vbase
        tot_max  += vmax

    note = ""
    if materia == Materia.PENALE:
        note = ("Valori indicativi. Il penale non ha scaglioni di valore; "
                "adeguare alle specificità del caso concreto.")
    elif grado != Grado.TRIBUNALE:
        note = (f"Valori calcolati applicando il coefficiente {coeff:.2f} "
                f"per il grado '{grado.value}' rispetto alla tabella Tribunale.")

    return RisultatoCalcolo(
        materia=materia.value,
        grado=grado.value,
        valore_controversia=valore,
        scaglione=sc.label,
        fasi_selezionate=[f.value for f in fasi],
        dettaglio=dettaglio,
        totale_minimo=round(tot_min, 2),
        totale_base=round(tot_base, 2),
        totale_massimo=round(tot_max, 2),
        note=note,
    )


def tutte_le_materie() -> List[Materia]:
    return list(Materia)


def tutti_i_gradi() -> List[Grado]:
    return list(Grado)


def tutte_le_fasi() -> List[Fase]:
    return list(Fase)
