"""
pct/tariffario.py - Calcolo compensi forensi DM 55/2014 aggiornato al DM 147/2022.

I valori tabellari ufficiali vengono letti dallo snapshot interno
`pct/data/tariffario_dm147_2022.json`, generato dal riferimento QuickOrganizer
`DM_147_2022.mdb`. Dove l'attuale UI di HACS non distingue ancora tutte le
tabelle ministeriali, il modulo mantiene un fallback esplicito e lo segnala
nelle note del risultato.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple


class Materia(str, Enum):
    CIVILE_COGN = "Civile di cognizione"
    LAVORO = "Controversie di lavoro"
    PREVIDENZA = "Previdenza e assistenza"
    ESEC_IMMO = "Esecuzione immobiliare"
    ESEC_MOB = "Esecuzione mobiliare"
    VOLONTARIA = "Volontaria giurisdizione"
    PENALE = "Penale"
    AMMINISTRATIVO = "Amministrativo / TAR-CdS"
    TRIBUTARIO = "Tributario / CGT"
    STRAGIUD = "Stragiudiziale / Consulenza"
    MEDIAZIONE = "Mediazione (D.Lgs. 28/2010)"
    NEGOZIAZIONE_ASSISTITA = "Negoziazione Assistita (D.L. 132/2014)"


class Grado(str, Enum):
    GIUDICE_DI_PACE = "Giudice di Pace"
    TRIBUNALE = "Tribunale"
    CORTE_APPELLO = "Corte d'Appello"
    CASSAZIONE = "Corte di Cassazione"


class Fase(str, Enum):
    STUDIO = "Studio"
    INTRODUTTIVA = "Introduttiva"
    ISTRUTTORIA = "Istruttoria / Istruzione"
    DECISIONALE = "Decisionale"
    ESECUTIVA = "Esecutiva"
    # Fasi specifiche mediazione / negoziazione assistita (DM 147/2022)
    ATTIVAZIONE = "Fase di attivazione"
    RIVITALIZZAZIONE = "Fase di rivitalizzazione"
    NEGOZIAZIONE_TRATTAZIONE = "Fase di negoziazione"
    CONCILIAZIONE = "Fase di conciliazione"


@dataclass
class ScaglioneFase:
    base: float

    @property
    def minimo(self) -> float:
        return round(self.base * 0.50, 2)

    @property
    def massimo(self) -> float:
        return round(self.base * 1.50, 2)


@dataclass
class Scaglione:
    valore_da: float
    valore_a: float
    label: str
    fasi: Dict[str, ScaglioneFase] = field(default_factory=dict)


@dataclass
class RisultatoCalcolo:
    materia: str
    grado: str
    valore_controversia: float
    scaglione: str
    fasi_selezionate: List[str]
    # dettaglio: fase → (minimo, base, massimo)
    dettaglio: Dict[str, Tuple[float, float, float]]
    totale_minimo: float
    totale_base: float
    totale_massimo: float
    spese_generali: float = 0.0
    perc_spese_generali: float = 0.15
    bonus_telematico: float = 0.0
    totale_con_spese: float = 0.0
    note: str = ""
    # variazioni percentuali applicate per fase (es. {"Fase di attivazione": 1.10})
    variazioni_fasi: Dict[str, float] = field(default_factory=dict)

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
            "spese_generali": self.spese_generali,
            "perc_spese_generali": self.perc_spese_generali,
            "bonus_telematico": self.bonus_telematico,
            "totale_con_spese": self.totale_con_spese,
            "note": self.note,
            "variazioni_fasi": self.variazioni_fasi,
        }


_SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "tariffario_dm147_2022.json"
_LABELS_3 = [
    (0, 1100, "Fino a EUR 1.100"),
    (1100, 5200, "Da EUR 1.100 a EUR 5.200"),
    (5200, float("inf"), "Da EUR 5.200 a EUR 26.000 (limite GdP)"),
]
_LABELS_7 = [
    (0, 1100, "Fino a EUR 1.100 (o indeterminabile)"),
    (1100, 5200, "Da EUR 1.100 a EUR 5.200"),
    (5200, 26000, "Da EUR 5.200 a EUR 26.000"),
    (26000, 52000, "Da EUR 26.000 a EUR 52.000"),
    (52000, 260000, "Da EUR 52.000 a EUR 260.000"),
    (260000, 520000, "Da EUR 260.000 a EUR 520.000"),
    (520000, float("inf"), "Oltre EUR 520.000"),
]
_PHASE_LABELS = {
    "Studio": Fase.STUDIO.value,
    "Introduttiva": Fase.INTRODUTTIVA.value,
    "Istruttoria": Fase.ISTRUTTORIA.value,
    "Decisoria": Fase.DECISIONALE.value,
    "Cautelare": "Cautelare",
    "Unica": "Compenso unico",
}
_GRADO_COEFF_APPROSSIMATI = {
    Grado.GIUDICE_DI_PACE: 1.0,
    Grado.TRIBUNALE: 1.0,
    Grado.CORTE_APPELLO: 1.30,
    Grado.CASSAZIONE: 1.60,
}


def _sc(valore: float) -> ScaglioneFase:
    return ScaglioneFase(base=float(valore))


@lru_cache(maxsize=1)
def _carica_snapshot() -> dict[str, dict[str, list[float | None]]]:
    try:
        raw = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
        tabelle = raw.get("tabelle", {}) if isinstance(raw, dict) else {}
        return tabelle if isinstance(tabelle, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=64)
def _tabella_snapshot(codice: str) -> list[Scaglione]:
    raw = _carica_snapshot().get(codice, {})
    if not raw:
        return []
    max_count = max(
        (sum(1 for value in valori if value is not None) for valori in raw.values()),
        default=0,
    )
    labels = _LABELS_3 if max_count <= 3 else _LABELS_7
    scaglioni: list[Scaglione] = []
    for idx, (valore_da, valore_a, label) in enumerate(labels):
        fasi: Dict[str, ScaglioneFase] = {}
        for fase_raw, valori in raw.items():
            if idx >= len(valori):
                continue
            valore = valori[idx]
            if valore is None:
                continue
            fasi[_PHASE_LABELS.get(fase_raw, fase_raw)] = _sc(float(valore))
        if fasi:
            scaglioni.append(Scaglione(valore_da, valore_a, label, fasi))
    return scaglioni


def _fallback_gdp() -> list[Scaglione]:
    return [
        Scaglione(0, 1100, "Fino a EUR 1.100", {
            Fase.STUDIO.value: _sc(68),
            Fase.INTRODUTTIVA.value: _sc(68),
            Fase.ISTRUTTORIA.value: _sc(68),
            Fase.DECISIONALE.value: _sc(142),
        }),
        Scaglione(1100, 5200, "Da EUR 1.100 a EUR 5.200", {
            Fase.STUDIO.value: _sc(236),
            Fase.INTRODUTTIVA.value: _sc(252),
            Fase.ISTRUTTORIA.value: _sc(352),
            Fase.DECISIONALE.value: _sc(425),
        }),
        Scaglione(5200, float("inf"), "Da EUR 5.200 a EUR 26.000 (limite GdP)", {
            Fase.STUDIO.value: _sc(425),
            Fase.INTRODUTTIVA.value: _sc(352),
            Fase.ISTRUTTORIA.value: _sc(567),
            Fase.DECISIONALE.value: _sc(746),
        }),
    ]


def _fallback_civile() -> list[Scaglione]:
    return [
        Scaglione(0, 1100, "Fino a EUR 1.100 (o indeterminabile)", {
            Fase.STUDIO.value: _sc(131),
            Fase.INTRODUTTIVA.value: _sc(196),
            Fase.ISTRUTTORIA.value: _sc(295),
            Fase.DECISIONALE.value: _sc(413),
        }),
        Scaglione(1100, 5200, "Da EUR 1.100 a EUR 5.200", {
            Fase.STUDIO.value: _sc(425),
            Fase.INTRODUTTIVA.value: _sc(637),
            Fase.ISTRUTTORIA.value: _sc(1063),
            Fase.DECISIONALE.value: _sc(1276),
        }),
        Scaglione(5200, 26000, "Da EUR 5.200 a EUR 26.000", {
            Fase.STUDIO.value: _sc(919),
            Fase.INTRODUTTIVA.value: _sc(1378),
            Fase.ISTRUTTORIA.value: _sc(1837),
            Fase.DECISIONALE.value: _sc(2756),
        }),
        Scaglione(26000, 52000, "Da EUR 26.000 a EUR 52.000", {
            Fase.STUDIO.value: _sc(1701),
            Fase.INTRODUTTIVA.value: _sc(2551),
            Fase.ISTRUTTORIA.value: _sc(3826),
            Fase.DECISIONALE.value: _sc(5103),
        }),
        Scaglione(52000, 260000, "Da EUR 52.000 a EUR 260.000", {
            Fase.STUDIO.value: _sc(2835),
            Fase.INTRODUTTIVA.value: _sc(4252),
            Fase.ISTRUTTORIA.value: _sc(7088),
            Fase.DECISIONALE.value: _sc(8505),
        }),
        Scaglione(260000, float("inf"), "Oltre EUR 260.000", {
            Fase.STUDIO.value: _sc(5670),
            Fase.INTRODUTTIVA.value: _sc(8505),
            Fase.ISTRUTTORIA.value: _sc(14175),
            Fase.DECISIONALE.value: _sc(17010),
        }),
    ]


def _fallback_lavoro() -> list[Scaglione]:
    return [
        Scaglione(0, 1100, "Fino a EUR 1.100 (o indeterminabile)", {
            Fase.STUDIO.value: _sc(105),
            Fase.INTRODUTTIVA.value: _sc(157),
            Fase.ISTRUTTORIA.value: _sc(236),
            Fase.DECISIONALE.value: _sc(331),
        }),
        Scaglione(1100, 5200, "Da EUR 1.100 a EUR 5.200", {
            Fase.STUDIO.value: _sc(340),
            Fase.INTRODUTTIVA.value: _sc(510),
            Fase.ISTRUTTORIA.value: _sc(851),
            Fase.DECISIONALE.value: _sc(1021),
        }),
        Scaglione(5200, 26000, "Da EUR 5.200 a EUR 26.000", {
            Fase.STUDIO.value: _sc(735),
            Fase.INTRODUTTIVA.value: _sc(1102),
            Fase.ISTRUTTORIA.value: _sc(1470),
            Fase.DECISIONALE.value: _sc(2205),
        }),
        Scaglione(26000, 52000, "Da EUR 26.000 a EUR 52.000", {
            Fase.STUDIO.value: _sc(1361),
            Fase.INTRODUTTIVA.value: _sc(2041),
            Fase.ISTRUTTORIA.value: _sc(3061),
            Fase.DECISIONALE.value: _sc(4082),
        }),
        Scaglione(52000, float("inf"), "Oltre EUR 52.000", {
            Fase.STUDIO.value: _sc(2268),
            Fase.INTRODUTTIVA.value: _sc(3402),
            Fase.ISTRUTTORIA.value: _sc(5670),
            Fase.DECISIONALE.value: _sc(6804),
        }),
    ]


def _fallback_penale() -> list[Scaglione]:
    return [
        Scaglione(0, float("inf"), "Penale (valore non applicabile)", {
            Fase.STUDIO.value: _sc(630),
            Fase.INTRODUTTIVA.value: _sc(630),
            Fase.ISTRUTTORIA.value: _sc(945),
            Fase.DECISIONALE.value: _sc(945),
            Fase.ESECUTIVA.value: _sc(630),
        }),
    ]


def _fallback_amministrativo() -> list[Scaglione]:
    return [
        Scaglione(0, 1100, "Fino a EUR 1.100 (o indeterminabile)", {
            Fase.STUDIO.value: _sc(140),
            Fase.INTRODUTTIVA.value: _sc(210),
            Fase.ISTRUTTORIA.value: _sc(315),
            Fase.DECISIONALE.value: _sc(441),
        }),
        Scaglione(1100, 5200, "Da EUR 1.100 a EUR 5.200", {
            Fase.STUDIO.value: _sc(453),
            Fase.INTRODUTTIVA.value: _sc(680),
            Fase.ISTRUTTORIA.value: _sc(1134),
            Fase.DECISIONALE.value: _sc(1361),
        }),
        Scaglione(5200, 26000, "Da EUR 5.200 a EUR 26.000", {
            Fase.STUDIO.value: _sc(980),
            Fase.INTRODUTTIVA.value: _sc(1470),
            Fase.ISTRUTTORIA.value: _sc(1960),
            Fase.DECISIONALE.value: _sc(2940),
        }),
        Scaglione(26000, 52000, "Da EUR 26.000 a EUR 52.000", {
            Fase.STUDIO.value: _sc(1815),
            Fase.INTRODUTTIVA.value: _sc(2722),
            Fase.ISTRUTTORIA.value: _sc(4083),
            Fase.DECISIONALE.value: _sc(5445),
        }),
        Scaglione(52000, 260000, "Da EUR 52.000 a EUR 260.000", {
            Fase.STUDIO.value: _sc(3024),
            Fase.INTRODUTTIVA.value: _sc(4536),
            Fase.ISTRUTTORIA.value: _sc(7560),
            Fase.DECISIONALE.value: _sc(9072),
        }),
        Scaglione(260000, float("inf"), "Oltre EUR 260.000", {
            Fase.STUDIO.value: _sc(6048),
            Fase.INTRODUTTIVA.value: _sc(9072),
            Fase.ISTRUTTORIA.value: _sc(15120),
            Fase.DECISIONALE.value: _sc(18144),
        }),
    ]


def _fallback_tributario() -> list[Scaglione]:
    return _fallback_civile()


def _fallback_stragiudiziale() -> list[Scaglione]:
    return [
        Scaglione(0, 1100, "Fino a EUR 1.100", {"Compenso unico": _sc(216)}),
        Scaglione(1100, 5200, "Da EUR 1.100 a EUR 5.200", {"Compenso unico": _sc(756)}),
        Scaglione(5200, 26000, "Da EUR 5.200 a EUR 26.000", {"Compenso unico": _sc(1836)}),
        Scaglione(26000, 52000, "Da EUR 26.000 a EUR 52.000", {"Compenso unico": _sc(3402)}),
        Scaglione(52000, 260000, "Da EUR 52.000 a EUR 260.000", {"Compenso unico": _sc(5940)}),
        Scaglione(260000, 520000, "Da EUR 260.000 a EUR 520.000", {"Compenso unico": _sc(11340)}),
        Scaglione(520000, float("inf"), "Oltre EUR 520.000", {"Compenso unico": _sc(0)}),
    ]


def _mediazione_scaglioni_snapshot() -> list[float]:
    """Valori 'Unica' A25 da snapshot DM 147/2022 per 7 scaglioni."""
    raw = _carica_snapshot().get("A25", {})
    vals = raw.get("Unica", [])
    # 7 valori attesi; usa fallback se non disponibili
    if len(vals) >= 7 and any(v for v in vals if v):
        return [float(v or 0) for v in vals[:7]]
    # fallback DM 55/2014 originale
    return [216, 756, 1836, 3402, 5940, 11340, 0]


def _fallback_mediazione() -> list[Scaglione]:
    """Tabella mediazione (D.Lgs. 28/2010) — 3 fasi da A25 DM 147/2022.

    Ripartizione percentuale fasi (orientamento CNF):
      Fase di attivazione:      40 %
      Fase di rivitalizzazione: 35 %
      Fase di conciliazione:    25 %  (solo se accordo raggiunto)
    """
    vals = _mediazione_scaglioni_snapshot()
    labels = _LABELS_7
    scaglioni = []
    for idx, (vda, va, label) in enumerate(labels):
        base = vals[idx] if idx < len(vals) else 0.0
        scaglioni.append(Scaglione(vda, va, label, {
            Fase.ATTIVAZIONE.value:    _sc(round(base * 0.40, 2)),
            Fase.RIVITALIZZAZIONE.value: _sc(round(base * 0.35, 2)),
            Fase.CONCILIAZIONE.value:  _sc(round(base * 0.25, 2)),
        }))
    return scaglioni


def _fallback_negoziazione_assistita() -> list[Scaglione]:
    """Tabella negoziazione assistita (D.L. 132/2014) — 3 fasi da A25 DM 147/2022.

    Stesse percentuali della mediazione ma fase intermedia denominata
    'Fase di negoziazione' anziché 'Fase di rivitalizzazione'.
    """
    vals = _mediazione_scaglioni_snapshot()
    labels = _LABELS_7
    scaglioni = []
    for idx, (vda, va, label) in enumerate(labels):
        base = vals[idx] if idx < len(vals) else 0.0
        scaglioni.append(Scaglione(vda, va, label, {
            Fase.ATTIVAZIONE.value:             _sc(round(base * 0.40, 2)),
            Fase.NEGOZIAZIONE_TRATTAZIONE.value: _sc(round(base * 0.35, 2)),
            Fase.CONCILIAZIONE.value:            _sc(round(base * 0.25, 2)),
        }))
    return scaglioni


def _exact_or_fallback(codice: str, fallback_fn) -> tuple[list[Scaglione], bool]:
    exact = _tabella_snapshot(codice)
    if exact:
        return exact, True
    return fallback_fn(), False


def _tabella_per_calcolo(
    materia: Materia,
    grado: Grado,
) -> tuple[list[Scaglione], float, str, bool, list[str]]:
    note: list[str] = []

    if grado == Grado.GIUDICE_DI_PACE:
        tabella, exact = _exact_or_fallback("A1", _fallback_gdp)
        note.append("Tabella 1 (Giudice di Pace).")
        return tabella, 1.0, "A1", exact, note

    if materia == Materia.PENALE:
        note.append("Penale: HACS mantiene una tabella sintetica per assenza di scaglioni di valore nella UI attuale.")
        return _fallback_penale(), 1.0, "PENALE", False, note

    if materia == Materia.AMMINISTRATIVO:
        codice = "A21" if grado == Grado.TRIBUNALE else "A22"
        tabella, exact = _exact_or_fallback(codice, _fallback_amministrativo)
        note.append(f"Tabella {codice[1:]} per giustizia amministrativa.")
        return tabella, 1.0, codice, exact, note

    if materia == Materia.TRIBUTARIO:
        codice = "A23" if grado == Grado.TRIBUNALE else "A24"
        tabella, exact = _exact_or_fallback(codice, _fallback_tributario)
        note.append(f"Tabella {codice[1:]} per giustizia tributaria.")
        return tabella, 1.0, codice, exact, note

    if materia == Materia.STRAGIUD:
        tabella, exact = _exact_or_fallback("A25", _fallback_stragiudiziale)
        note.append("Tabella 25 per prestazioni stragiudiziali.")
        return tabella, 1.0, "A25", exact, note

    if materia == Materia.MEDIAZIONE:
        note.append("Tabella 25 (A25) — mediazione D.Lgs. 28/2010: ripartita in Attivazione (40%), Rivitalizzazione (35%), Conciliazione (25%).")
        note.append("DM 147/2022: variazione +/-50% tassativa per fase.")
        return _fallback_mediazione(), 1.0, "A25-MEDIAZIONE", False, note

    if materia == Materia.NEGOZIAZIONE_ASSISTITA:
        note.append("Tabella 25 (A25) — negoziazione assistita D.L. 132/2014: ripartita in Attivazione (40%), Negoziazione (35%), Conciliazione (25%).")
        note.append("DM 147/2022: variazione +/-50% tassativa per fase.")
        return _fallback_negoziazione_assistita(), 1.0, "A25-NEGOZIAZIONE", False, note

    if materia == Materia.LAVORO:
        tabella, exact = _exact_or_fallback("A3", _fallback_lavoro)
        coeff = 1.0 if grado == Grado.TRIBUNALE else _GRADO_COEFF_APPROSSIMATI[grado]
        if coeff != 1.0:
            note.append(f"Grado {grado.value}: coefficiente ricostruttivo x{coeff:.2f} su tabella lavoro di primo grado.")
        else:
            note.append("Tabella 3 per controversie di lavoro.")
        return tabella, coeff, "A3", exact and coeff == 1.0, note

    if materia == Materia.PREVIDENZA:
        tabella, exact = _exact_or_fallback("A4", _fallback_lavoro)
        coeff = 1.0 if grado == Grado.TRIBUNALE else _GRADO_COEFF_APPROSSIMATI[grado]
        if coeff != 1.0:
            note.append(f"Grado {grado.value}: coefficiente ricostruttivo x{coeff:.2f} su tabella previdenza di primo grado.")
        else:
            note.append("Tabella 4 per previdenza e assistenza.")
        return tabella, coeff, "A4", exact and coeff == 1.0, note

    civile = {Materia.CIVILE_COGN, Materia.ESEC_IMMO, Materia.ESEC_MOB, Materia.VOLONTARIA}
    if materia in civile:
        tabella, exact = _exact_or_fallback("A2", _fallback_civile)
        coeff = 1.0 if grado == Grado.TRIBUNALE else _GRADO_COEFF_APPROSSIMATI[grado]
        if materia == Materia.CIVILE_COGN and coeff == 1.0:
            note.append("Tabella 2 per giudizi civili ordinari di primo grado.")
            return tabella, coeff, "A2", exact, note
        if materia == Materia.CIVILE_COGN:
            note.append(f"Grado {grado.value}: coefficiente ricostruttivo x{coeff:.2f} applicato alla tabella civile di primo grado.")
        else:
            note.append(f"Materia {materia.value}: la UI HACS la ricondduce ancora al profilo civile ordinario.")
            if coeff != 1.0:
                note.append(f"Grado {grado.value}: coefficiente ricostruttivo x{coeff:.2f}.")
        return tabella, coeff, "A2", False, note

    tabella, exact = _exact_or_fallback("A2", _fallback_civile)
    return tabella, 1.0, "A2", exact, note


def calcola_compenso(
    materia: Materia,
    grado: Grado,
    valore: float,
    fasi: List[Fase],
    bonus_telematico: bool = False,
    includi_spese_generali: bool = True,
    perc_spese_generali: float = 0.15,
    variazioni_fasi: Optional[Dict[str, float]] = None,
) -> RisultatoCalcolo:
    """Calcola il compenso forense secondo DM 147/2022.

    Args:
        variazioni_fasi: dict fase_label → moltiplicatore (es. 1.20 = +20%).
            Consentito nell'intervallo [0.50, 1.50] per DM 147/2022 (±50%).
        perc_spese_generali: percentuale spese generali art. 2 DM 55/2014 (default 0.15 = 15%).
    """
    tabella, coeff, tabella_codice, esatto, note_parts = _tabella_per_calcolo(materia, grado)
    _variazioni = variazioni_fasi or {}

    _mediaz = {Materia.MEDIAZIONE, Materia.NEGOZIAZIONE_ASSISTITA}
    if materia == Materia.STRAGIUD:
        fasi_richieste = ["Compenso unico"]
    elif materia in _mediaz:
        # Per mediazione/negoziazione usa tutte le fasi della tabella nell'ordine
        fasi_richieste = list(tabella[0].fasi.keys()) if tabella else []
    else:
        fasi_richieste = [fase.value for fase in fasi]

    sc = tabella[-1]
    for scaglione in tabella:
        if valore <= scaglione.valore_a:
            sc = scaglione
            break

    dettaglio: Dict[str, Tuple[float, float, float]] = {}
    tot_min = tot_base = tot_max = 0.0
    fasi_mancanti: list[str] = []

    for fase in fasi_richieste:
        fase_data = sc.fasi.get(fase)
        if not fase_data:
            fasi_mancanti.append(fase)
            continue
        # Applica variazione per fase (clamp ±50%)
        var = float(_variazioni.get(fase, 1.0))
        var = max(0.50, min(1.50, var))
        vbase_raw = round(fase_data.base * coeff * var, 2)
        vmin = round(fase_data.minimo * coeff, 2)
        vmax = round(fase_data.massimo * coeff, 2)
        # Il base varia, min/max rimangono quelli tabellari (DM ±50% sul tabellare)
        dettaglio[fase] = (vmin, vbase_raw, vmax)
        tot_min += vmin
        tot_base += vbase_raw
        tot_max += vmax

    bonus_tel_importo = round(tot_base * 0.30, 2) if bonus_telematico else 0.0
    if bonus_telematico:
        tot_base = round(tot_base + bonus_tel_importo, 2)

    perc_sg = max(0.0, float(perc_spese_generali))
    spese_gen = round(tot_base * perc_sg, 2) if includi_spese_generali else 0.0
    totale_con_spese = round(tot_base + spese_gen, 2)

    if fasi_mancanti:
        note_parts.append("Fasi non presenti nella tabella selezionata: " + ", ".join(fasi_mancanti) + ".")
    if bonus_telematico:
        note_parts.append("Bonus telematico +30% applicato sul compenso base.")
    if materia == Materia.PENALE:
        note_parts.append("Valore di controversia non applicato al penale.")
    if materia == Materia.STRAGIUD:
        note_parts.append("Compenso unico tabellare: le fasi selezionate in UI sono accorpate automaticamente.")
    if _variazioni:
        note_parts.append("Variazioni per fase applicate (DM 147/2022 ±50%).")
    if includi_spese_generali and perc_sg > 0:
        note_parts.append(f"Spese generali art. 2 DM 55/2014: {int(perc_sg*100)}% sul compenso base.")
    if esatto:
        note_parts.append(
            f"Valori tabellari ufficiali letti dal riferimento DM 147/2022 (snapshot QuickOrganizer, tabella {tabella_codice[1:] if tabella_codice.startswith('A') else tabella_codice})."
        )
    else:
        note_parts.append("Valori non completamente distinguibili con l'attuale UI HACS: applicata ricostruzione esplicita e tracciata nelle note.")
    note_parts.append("DM 147/2022: variazione +/-50% tassativa.")

    return RisultatoCalcolo(
        materia=materia.value,
        grado=grado.value,
        valore_controversia=valore,
        scaglione=sc.label,
        fasi_selezionate=list(dettaglio.keys()),
        dettaglio=dettaglio,
        totale_minimo=round(tot_min, 2),
        totale_base=round(tot_base, 2),
        totale_massimo=round(tot_max, 2),
        spese_generali=spese_gen,
        perc_spese_generali=perc_sg,
        bonus_telematico=bonus_tel_importo,
        totale_con_spese=totale_con_spese,
        note=" ".join(note_parts),
        variazioni_fasi=dict(_variazioni),
    )


def tutte_le_materie() -> List[Materia]:
    return list(Materia)


def tutti_i_gradi() -> List[Grado]:
    return list(Grado)


def tutte_le_fasi() -> List[Fase]:
    return [
        Fase.STUDIO,
        Fase.INTRODUTTIVA,
        Fase.ISTRUTTORIA,
        Fase.DECISIONALE,
        Fase.ESECUTIVA,
    ]


def fasi_mediazione() -> List[Fase]:
    """Fasi per mediazione (D.Lgs. 28/2010)."""
    return [Fase.ATTIVAZIONE, Fase.RIVITALIZZAZIONE, Fase.CONCILIAZIONE]


def fasi_negoziazione_assistita() -> List[Fase]:
    """Fasi per negoziazione assistita (D.L. 132/2014)."""
    return [Fase.ATTIVAZIONE, Fase.NEGOZIAZIONE_TRATTAZIONE, Fase.CONCILIAZIONE]
