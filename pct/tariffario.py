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
    ARBITRATO = "Arbitrato"


class Grado(str, Enum):
    GIUDICE_DI_PACE = "Giudice di Pace"
    TRIBUNALE = "Tribunale"
    GIP_GUP = "GIP / GUP"
    TRIBUNALE_MONOCRATICO = "Tribunale monocratico"
    TRIBUNALE_COLLEGIALE = "Tribunale collegiale"
    CORTE_ASSISE = "Corte d'Assise"
    CORTE_APPELLO = "Corte d'Appello"
    CORTE_APPELLO_PENALE = "Corte d'Appello penale"
    CORTE_ASSISE_APPELLO = "Corte d'Assise d'Appello"
    CASSAZIONE = "Corte di Cassazione"
    TRIBUNALE_SORVEGLIANZA = "Tribunale di Sorveglianza"
    TAR = "TAR"
    CONSIGLIO_DI_STATO = "Consiglio di Stato"
    CGT_PRIMO_GRADO = "CGT di primo grado"
    CGT_SECONDO_GRADO = "CGT di secondo grado"
    FUORI_GIUDIZIO = "Fuori giudizio"
    PROCEDURA_ADR = "Procedura ADR"


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


class LivelloCompenso(str, Enum):
    MINIMO = "minimo"
    BASE = "base"
    MASSIMO = "massimo"


class ComplessitaStimata(str, Enum):
    BASSA = "bassa"
    MEDIA = "media"
    ALTA = "alta"


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
    bonus_telematico_attivo: bool = False
    includi_spese_generali: bool = True
    valore_input: float = 0.0
    valore_calcolo: float = 0.0
    complessita_stimata: str = ""

    def _indice_livello(self, livello: LivelloCompenso | str) -> int:
        value = livello.value if isinstance(livello, LivelloCompenso) else str(livello or LivelloCompenso.BASE.value)
        mapping = {
            LivelloCompenso.MINIMO.value: 0,
            LivelloCompenso.BASE.value: 1,
            LivelloCompenso.MASSIMO.value: 2,
        }
        return mapping.get(value, 1)

    def dettaglio_livello(self, livello: LivelloCompenso | str) -> Dict[str, float]:
        idx = self._indice_livello(livello)
        return {fase: float(valori[idx]) for fase, valori in self.dettaglio.items()}

    def subtotale_livello(self, livello: LivelloCompenso | str) -> float:
        return round(sum(self.dettaglio_livello(livello).values()), 2)

    def bonus_telematico_livello(self, livello: LivelloCompenso | str) -> float:
        if not self.bonus_telematico_attivo:
            return 0.0
        return round(self.subtotale_livello(livello) * 0.30, 2)

    def spese_generali_livello(self, livello: LivelloCompenso | str) -> float:
        if not self.includi_spese_generali or self.perc_spese_generali <= 0:
            return 0.0
        imponibile = self.subtotale_livello(livello) + self.bonus_telematico_livello(livello)
        return round(imponibile * self.perc_spese_generali, 2)

    def totale_compenso_livello(self, livello: LivelloCompenso | str) -> float:
        imponibile = self.subtotale_livello(livello) + self.bonus_telematico_livello(livello)
        return round(imponibile + self.spese_generali_livello(livello), 2)

    def riepilogo_livello(self, livello: LivelloCompenso | str) -> dict:
        livello_value = livello.value if isinstance(livello, LivelloCompenso) else str(livello or LivelloCompenso.BASE.value)
        return {
            "livello": livello_value,
            "subtotale": self.subtotale_livello(livello_value),
            "bonus_telematico": self.bonus_telematico_livello(livello_value),
            "spese_generali": self.spese_generali_livello(livello_value),
            "totale_compenso": self.totale_compenso_livello(livello_value),
            "dettaglio": self.dettaglio_livello(livello_value),
        }

    def to_dict(self) -> dict:
        return {
            "materia": self.materia,
            "grado": self.grado,
            "valore_controversia": self.valore_controversia,
            "valore_input": self.valore_input,
            "valore_calcolo": self.valore_calcolo,
            "complessita_stimata": self.complessita_stimata,
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
            "bonus_telematico_attivo": self.bonus_telematico_attivo,
            "includi_spese_generali": self.includi_spese_generali,
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
    Grado.GIP_GUP: 1.0,
    Grado.TRIBUNALE_MONOCRATICO: 1.0,
    Grado.TRIBUNALE_COLLEGIALE: 1.0,
    Grado.CORTE_ASSISE: 1.0,
    Grado.CORTE_APPELLO: 1.30,
    Grado.CORTE_APPELLO_PENALE: 1.0,
    Grado.CORTE_ASSISE_APPELLO: 1.0,
    Grado.CASSAZIONE: 1.60,
    Grado.TRIBUNALE_SORVEGLIANZA: 1.0,
    Grado.TAR: 1.0,
    Grado.CONSIGLIO_DI_STATO: 1.0,
    Grado.CGT_PRIMO_GRADO: 1.0,
    Grado.CGT_SECONDO_GRADO: 1.0,
    Grado.FUORI_GIUDIZIO: 1.0,
    Grado.PROCEDURA_ADR: 1.0,
}


def _sc(valore: float) -> ScaglioneFase:
    return ScaglioneFase(base=float(valore))


_COMPLESSITA_VIRTUAL_VALUE = {
    ComplessitaStimata.BASSA: 39000.0,
    ComplessitaStimata.MEDIA: 156000.0,
    ComplessitaStimata.ALTA: 390000.0,
}


def _parse_complessita(value: ComplessitaStimata | str | None) -> ComplessitaStimata | None:
    if isinstance(value, ComplessitaStimata):
        return value
    if value in (None, ""):
        return None
    try:
        return ComplessitaStimata(str(value).strip().lower())
    except ValueError:
        return None


def valore_virtuale_indeterminabile(
    complessita: ComplessitaStimata | str | None,
) -> tuple[float, ComplessitaStimata | None]:
    complessita_norm = _parse_complessita(complessita)
    if not complessita_norm:
        return 0.0, None
    return _COMPLESSITA_VIRTUAL_VALUE[complessita_norm], complessita_norm


@lru_cache(maxsize=1)
def _carica_snapshot() -> dict[str, dict[str, list[float | None]]]:
    try:
        raw = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
        tabelle = raw.get("tabelle", {}) if isinstance(raw, dict) else {}
        return tabelle if isinstance(tabelle, dict) else {}
    except Exception:
        return {}


def _snapshot_table(
    codice: str,
    *,
    phase_aliases: Optional[dict[str, str]] = None,
    single_label: str | None = None,
) -> list[Scaglione]:
    raw = _carica_snapshot().get(codice, {})
    if not raw:
        return []
    alias_map = phase_aliases or {}
    if single_label:
        fasi: Dict[str, ScaglioneFase] = {}
        for fase_raw, valori in raw.items():
            valore = next((item for item in valori if item is not None), None)
            if valore is None:
                continue
            fase_label = alias_map.get(fase_raw, _PHASE_LABELS.get(fase_raw, fase_raw))
            fasi[fase_label] = _sc(float(valore))
        if not fasi:
            return []
        return [Scaglione(0.0, float("inf"), single_label, fasi)]

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
            fase_label = alias_map.get(fase_raw, _PHASE_LABELS.get(fase_raw, fase_raw))
            fasi[fase_label] = _sc(float(valore))
        if fasi:
            scaglioni.append(Scaglione(valore_da, valore_a, label, fasi))
    return scaglioni


@lru_cache(maxsize=64)
def _tabella_snapshot(codice: str) -> list[Scaglione]:
    return _snapshot_table(codice)


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


_PROFILE_TABLE_OVERRIDES: Dict[str, Dict[str, object]] = {
    "civile_appello_tribunale": {
        "table_code": "A2",
        "note": "Tabella 2 per appello civile devoluto al Tribunale ex art. 341 c.p.c.",
    },
    "civile_monitorio_gdp": {
        "table_code": "A8",
        "note": "Tabella 8 per procedimenti monitori davanti al Giudice di Pace.",
        "force_compenso_unico": True,
    },
    "civile_monitorio": {
        "table_code": "A8",
        "note": "Tabella 8 per procedimenti monitori.",
        "force_compenso_unico": True,
    },
    "civile_convalida_locatizia": {
        "table_code": "A5",
        "note": "Tabella 5 per procedimenti per convalida locatizia.",
    },
    "esecuzione_precetto": {
        "table_code": "A6",
        "note": "Tabella 6 per atto di precetto.",
        "force_compenso_unico": True,
    },
    "volontaria": {
        "table_code": "A7",
        "note": "Tabella 7 per procedimenti di volontaria giurisdizione.",
        "force_compenso_unico": True,
    },
    "esecuzione_mobiliare": {
        "table_code": "A16",
        "note": "Tabella 16 per procedure esecutive mobiliari.",
        "phase_aliases": {"Istruttoria": Fase.ESECUTIVA.value},
    },
    "esecuzione_presso_terzi": {
        "table_code": "A17",
        "note": "Tabella 17 per esecuzioni presso terzi, per consegna e rilascio, in forma specifica.",
        "phase_aliases": {"Istruttoria": Fase.ESECUTIVA.value},
    },
    "esecuzione_immobiliare": {
        "table_code": "A18",
        "note": "Tabella 18 per procedure esecutive immobiliari.",
        "phase_aliases": {"Istruttoria": Fase.ESECUTIVA.value},
    },
    "penale_indagini_preliminari": {
        "table_code": "A15-2",
        "note": "Tabella 15, colonna indagini preliminari.",
        "single_label": "Penale - indagini preliminari",
    },
    "penale_udienza_preliminare": {
        "table_code": "A15-6",
        "note": "Tabella 15, colonna GIP/GUP.",
        "single_label": "Penale - GIP/GUP",
    },
    "penale_monocratico": {
        "table_code": "A15-7",
        "note": "Tabella 15, colonna Tribunale monocratico.",
        "single_label": "Penale - Tribunale monocratico",
    },
    "penale_collegiale": {
        "table_code": "A15-8",
        "note": "Tabella 15, colonna Tribunale collegiale.",
        "single_label": "Penale - Tribunale collegiale",
    },
    "penale_assise": {
        "table_code": "A15-9",
        "note": "Tabella 15, colonna Corte d'Assise.",
        "single_label": "Penale - Corte d'Assise",
    },
    "penale_appello": {
        "table_code": "A15-10",
        "note": "Tabella 15, colonna Corte d'Appello penale.",
        "single_label": "Penale - Corte d'Appello",
    },
    "penale_sorveglianza": {
        "table_code": "A15-11",
        "note": "Tabella 15, colonna Tribunale di sorveglianza.",
        "single_label": "Penale - Tribunale di sorveglianza",
    },
    "penale_assise_appello": {
        "table_code": "A15-12",
        "note": "Tabella 15, colonna Corte d'Assise d'Appello.",
        "single_label": "Penale - Corte d'Assise d'Appello",
    },
    "penale_cassazione": {
        "table_code": "A15-13",
        "note": "Tabella 15, colonna Corte di Cassazione penale / magistrature superiori.",
        "single_label": "Penale - Cassazione e magistrature superiori",
    },
    "arbitrato": {
        "table_code": "A26",
        "note": "Tabella 26 per arbitrato.",
        "force_compenso_unico": True,
    },
}


def _tabella_per_calcolo(
    materia: Materia,
    grado: Grado,
    profile_code: str = "",
) -> tuple[list[Scaglione], float, str, bool, list[str]]:
    note: list[str] = []

    override = _PROFILE_TABLE_OVERRIDES.get(profile_code or "")
    if override:
        table_code = str(override.get("table_code", "") or "")
        tabella = _snapshot_table(
            table_code,
            phase_aliases=override.get("phase_aliases"),  # type: ignore[arg-type]
            single_label=override.get("single_label"),  # type: ignore[arg-type]
        )
        if tabella:
            note_text = str(override.get("note", "") or "").strip()
            if note_text:
                note.append(note_text)
            return tabella, 1.0, table_code, True, note

    if grado == Grado.GIUDICE_DI_PACE:
        tabella, exact = _exact_or_fallback("A1", _fallback_gdp)
        note.append("Tabella 1 (Giudice di Pace).")
        return tabella, 1.0, "A1", exact, note

    if materia == Materia.PENALE:
        penal_map = {
            Grado.FUORI_GIUDIZIO: ("A15-2", "Penale - indagini preliminari", "Tabella 15 per indagini preliminari."),
            Grado.GIP_GUP: ("A15-6", "Penale - GIP/GUP", "Tabella 15 per udienza preliminare e attivita GIP/GUP."),
            Grado.TRIBUNALE: ("A15-7", "Penale - Tribunale monocratico", "Tabella 15, profilo base penale davanti al Tribunale monocratico."),
            Grado.TRIBUNALE_MONOCRATICO: ("A15-7", "Penale - Tribunale monocratico", "Tabella 15 per dibattimento penale monocratico."),
            Grado.TRIBUNALE_COLLEGIALE: ("A15-8", "Penale - Tribunale collegiale", "Tabella 15 per dibattimento penale collegiale."),
            Grado.CORTE_ASSISE: ("A15-9", "Penale - Corte d'Assise", "Tabella 15 per Corte d'Assise."),
            Grado.CORTE_APPELLO: ("A15-10", "Penale - Corte d'Appello", "Tabella 15 per appello penale."),
            Grado.CORTE_APPELLO_PENALE: ("A15-10", "Penale - Corte d'Appello", "Tabella 15 per appello penale."),
            Grado.TRIBUNALE_SORVEGLIANZA: ("A15-11", "Penale - Tribunale di sorveglianza", "Tabella 15 per Tribunale di Sorveglianza."),
            Grado.CORTE_ASSISE_APPELLO: ("A15-12", "Penale - Corte d'Assise d'Appello", "Tabella 15 per Corte d'Assise d'Appello."),
            Grado.CASSAZIONE: ("A15-13", "Penale - Cassazione e magistrature superiori", "Tabella 15 per Corte di Cassazione penale e magistrature superiori."),
        }
        penal_profile = penal_map.get(grado)
        if penal_profile:
            codice, label, note_text = penal_profile
            tabella = _snapshot_table(codice, single_label=label)
            if tabella:
                note.append(note_text)
                return tabella, 1.0, codice, True, note
        note.append("Penale: fallback sintetico usato solo in assenza di profilo o snapshot esatto.")
        return _fallback_penale(), 1.0, "PENALE", False, note

    if materia == Materia.AMMINISTRATIVO:
        codice = "A21" if grado in {Grado.TRIBUNALE, Grado.TAR} else "A22"
        tabella, exact = _exact_or_fallback(codice, _fallback_amministrativo)
        note.append(f"Tabella {codice[1:]} per giustizia amministrativa.")
        return tabella, 1.0, codice, exact, note

    if materia == Materia.TRIBUTARIO:
        if grado == Grado.CASSAZIONE:
            tabella = _tabella_snapshot("A13")
            if tabella:
                note.append("Tabella 13 per giudizi di legittimita in Cassazione, applicabile anche al tributario.")
                return tabella, 1.0, "A13", True, note
        codice = "A23" if grado in {Grado.TRIBUNALE, Grado.CGT_PRIMO_GRADO} else "A24"
        tabella, exact = _exact_or_fallback(codice, _fallback_tributario)
        note.append(f"Tabella {codice[1:]} per giustizia tributaria.")
        return tabella, 1.0, codice, exact, note

    if materia == Materia.STRAGIUD:
        tabella, exact = _exact_or_fallback("A25", _fallback_stragiudiziale)
        note.append("Tabella 25 per prestazioni stragiudiziali.")
        return tabella, 1.0, "A25", exact, note

    if materia == Materia.ARBITRATO:
        tabella = _tabella_snapshot("A26")
        if tabella:
            note.append("Tabella 26 per arbitrato.")
            return tabella, 1.0, "A26", True, note
        note.append("Tabella 26 non disponibile in snapshot: fallback civile analogico.")
        tabella, exact = _exact_or_fallback("A2", _fallback_civile)
        return tabella, 1.0, "A2", exact, note

    if materia == Materia.MEDIAZIONE:
        tabella = _snapshot_table(
            "A27",
            phase_aliases={
                "Introduttiva": Fase.ATTIVAZIONE.value,
                "Istruttoria": Fase.RIVITALIZZAZIONE.value,
                "Decisoria": Fase.CONCILIAZIONE.value,
            },
        )
        if tabella:
            note.append("Tabella 27 per mediazione civile e commerciale.")
            return tabella, 1.0, "A27", True, note
        note.append("Tabella 27 non disponibile in snapshot: usata ricostruzione ADR di fallback.")
        return _fallback_mediazione(), 1.0, "A27", False, note

    if materia == Materia.NEGOZIAZIONE_ASSISTITA:
        tabella = _snapshot_table(
            "A27",
            phase_aliases={
                "Introduttiva": Fase.ATTIVAZIONE.value,
                "Istruttoria": Fase.NEGOZIAZIONE_TRATTAZIONE.value,
                "Decisoria": Fase.CONCILIAZIONE.value,
            },
        )
        if tabella:
            note.append("Tabella 27 per procedura di negoziazione assistita.")
            return tabella, 1.0, "A27", True, note
        note.append("Tabella 27 non disponibile in snapshot: usata ricostruzione ADR di fallback.")
        return _fallback_negoziazione_assistita(), 1.0, "A27", False, note

    if materia == Materia.LAVORO:
        if grado == Grado.CORTE_APPELLO:
            tabella = _tabella_snapshot("A12")
            if tabella:
                note.append("Tabella 12 per giudizi innanzi alla Corte d'Appello, applicabile alle controversie di lavoro.")
                return tabella, 1.0, "A12", True, note
        if grado == Grado.CASSAZIONE:
            tabella = _tabella_snapshot("A13")
            if tabella:
                note.append("Tabella 13 per giudizi in Cassazione, applicabile alle controversie di lavoro.")
                return tabella, 1.0, "A13", True, note
        tabella, exact = _exact_or_fallback("A3", _fallback_lavoro)
        note.append("Tabella 3 per controversie di lavoro.")
        return tabella, 1.0, "A3", exact, note

    if materia == Materia.PREVIDENZA:
        if grado == Grado.CORTE_APPELLO:
            tabella = _tabella_snapshot("A12")
            if tabella:
                note.append("Tabella 12 per giudizi innanzi alla Corte d'Appello, applicabile alla previdenza e assistenza.")
                return tabella, 1.0, "A12", True, note
        if grado == Grado.CASSAZIONE:
            tabella = _tabella_snapshot("A13")
            if tabella:
                note.append("Tabella 13 per giudizi in Cassazione, applicabile alla previdenza e assistenza.")
                return tabella, 1.0, "A13", True, note
        tabella, exact = _exact_or_fallback("A4", _fallback_lavoro)
        note.append("Tabella 4 per previdenza e assistenza.")
        return tabella, 1.0, "A4", exact, note

    if materia == Materia.ESEC_IMMO:
        tabella = _snapshot_table("A18", phase_aliases={"Istruttoria": Fase.ESECUTIVA.value})
        if tabella:
            note.append("Tabella 18 per procedure esecutive immobiliari.")
            return tabella, 1.0, "A18", True, note
        note.append("Tabella 18 non disponibile in snapshot: fallback civile esecutivo.")
        tabella, exact = _exact_or_fallback("A2", _fallback_civile)
        return tabella, 1.0, "A2", exact, note

    if materia == Materia.ESEC_MOB:
        tabella = _snapshot_table("A16", phase_aliases={"Istruttoria": Fase.ESECUTIVA.value})
        if tabella:
            note.append("Tabella 16 per procedure esecutive mobiliari.")
            return tabella, 1.0, "A16", True, note
        note.append("Tabella 16 non disponibile in snapshot: fallback civile esecutivo.")
        tabella, exact = _exact_or_fallback("A2", _fallback_civile)
        return tabella, 1.0, "A2", exact, note

    if materia == Materia.VOLONTARIA:
        tabella = _tabella_snapshot("A7")
        if tabella:
            note.append("Tabella 7 per volontaria giurisdizione.")
            return tabella, 1.0, "A7", True, note
        note.append("Tabella 7 non disponibile in snapshot: fallback camerale.")
        tabella, exact = _exact_or_fallback("A2", _fallback_civile)
        return tabella, 1.0, "A2", exact, note

    if materia == Materia.CIVILE_COGN:
        if grado == Grado.CORTE_APPELLO:
            tabella = _tabella_snapshot("A12")
            if tabella:
                note.append("Tabella 12 per giudizi innanzi alla Corte d'Appello.")
                return tabella, 1.0, "A12", True, note
        if grado == Grado.CASSAZIONE:
            tabella = _tabella_snapshot("A13")
            if tabella:
                note.append("Tabella 13 per giudizi in Cassazione.")
                return tabella, 1.0, "A13", True, note
        tabella, exact = _exact_or_fallback("A2", _fallback_civile)
        note.append("Tabella 2 per giudizi civili ordinari di primo grado.")
        return tabella, 1.0, "A2", exact, note

    tabella, exact = _exact_or_fallback("A2", _fallback_civile)
    return tabella, 1.0, "A2", exact, note


def calcola_compenso(
    materia: Materia,
    grado: Grado,
    valore: float,
    fasi: List[Fase],
    profile_code: str = "",
    bonus_telematico: bool = False,
    includi_spese_generali: bool = True,
    perc_spese_generali: float = 0.15,
    variazioni_fasi: Optional[Dict[str, float]] = None,
    complessita: ComplessitaStimata | str | None = None,
) -> RisultatoCalcolo:
    """Calcola il compenso forense secondo DM 147/2022.

    Args:
        variazioni_fasi: dict fase_label → moltiplicatore (es. 1.20 = +20%).
            Consentito nell'intervallo [0.50, 1.50] per DM 147/2022 (±50%).
        perc_spese_generali: percentuale spese generali art. 2 DM 55/2014 (default 0.15 = 15%).
    """
    tabella, coeff, tabella_codice, esatto, note_parts = _tabella_per_calcolo(materia, grado, profile_code=profile_code)
    _variazioni = variazioni_fasi or {}
    valore_input = float(valore or 0.0)
    valore_calcolo = valore_input
    complessita_norm = _parse_complessita(complessita)
    force_compenso_unico = bool(_PROFILE_TABLE_OVERRIDES.get(profile_code or "", {}).get("force_compenso_unico"))

    _mediaz = {Materia.MEDIAZIONE, Materia.NEGOZIAZIONE_ASSISTITA}
    if materia in {Materia.STRAGIUD, Materia.ARBITRATO} or force_compenso_unico:
        fasi_richieste = ["Compenso unico"]
    elif materia in _mediaz:
        # Per mediazione/negoziazione usa tutte le fasi della tabella nell'ordine
        fasi_richieste = list(tabella[0].fasi.keys()) if tabella else []
    else:
        fasi_richieste = [fase.value for fase in fasi]

    materie_con_scaglione_virtuale = {
        Materia.CIVILE_COGN,
        Materia.LAVORO,
        Materia.PREVIDENZA,
        Materia.ESEC_IMMO,
        Materia.ESEC_MOB,
        Materia.VOLONTARIA,
        Materia.AMMINISTRATIVO,
        Materia.TRIBUTARIO,
        Materia.ARBITRATO,
    }
    if valore_calcolo <= 0 and materia in materie_con_scaglione_virtuale and complessita_norm:
        valore_calcolo, _ = valore_virtuale_indeterminabile(complessita_norm)
        note_parts.append(
            "Valore non determinato: per il calcolo HACS ha collocato la pratica nello scaglione "
            f"compatibile con complessita {complessita_norm.value}, secondo la logica di valore "
            "indeterminabile del D.M. 55/2014."
        )

    sc = tabella[-1]
    for scaglione in tabella:
        if valore_calcolo <= scaglione.valore_a:
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
    if materia in {Materia.STRAGIUD, Materia.ARBITRATO} or force_compenso_unico:
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
        valore_controversia=valore_calcolo,
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
        bonus_telematico_attivo=bonus_telematico,
        includi_spese_generali=includi_spese_generali,
        valore_input=valore_input,
        valore_calcolo=valore_calcolo,
        complessita_stimata=complessita_norm.value if complessita_norm else "",
    )


def tutte_le_materie() -> List[Materia]:
    return list(Materia)


def tutti_i_gradi() -> List[Grado]:
    return list(Grado)


def tutte_le_complessita() -> List[ComplessitaStimata]:
    return list(ComplessitaStimata)


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
