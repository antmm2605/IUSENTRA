"""Calcolo puro del compenso a tempo ex art. 22-bis D.M. 55/2014."""
from __future__ import annotations


from pct.formatting import format_euro_it
import math
from typing import Any


COMPENSO_A_TEMPO_CODE = "COMPENSO_A_TEMPO_DM55_ART22BIS"
COMPENSO_A_TEMPO_LABEL = "A ore / compenso a tempo - art. 22-bis D.M. 55/2014"
COMPENSO_A_TEMPO_SOURCE_LABEL = "Compenso a tempo ex art. 22-bis D.M. 55/2014"
FONTE_NORMATIVA_COMPENSO_A_TEMPO = "Art. 22-bis D.M. 55/2014, introdotto dal D.M. 147/2022"
RANGE_TARIFFA_MIN = 200.0
RANGE_TARIFFA_MAX = 500.0

_ALIASES_COMPENSO_A_TEMPO = {
    "compenso orario",
    "a ore",
    "compenso a ore",
    "compenso a tempo",
    "compenso a tempo dm55 art22bis",
    COMPENSO_A_TEMPO_CODE.lower(),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").split()).strip()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.strip().replace(".", "").replace(",", ".") if "," in value else value.strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return int(float(value))
    except (TypeError, ValueError):
        return default


def is_compenso_a_tempo(value: str) -> bool:
    normalized = _clean(value).lower()
    return normalized in _ALIASES_COMPENSO_A_TEMPO


def normalizza_tipo_compenso(value: str) -> str:
    raw = str(value or "").strip()
    return COMPENSO_A_TEMPO_CODE if is_compenso_a_tempo(raw) else raw


def _round_hours(total_minutes: int, criterio_arrotondamento: str) -> float:
    criterio = str(criterio_arrotondamento or "ora_frazione_oltre_30").strip()
    if criterio == "effettivo_minuti":
        return round(total_minutes / 60.0, 4)
    if criterio == "scatti_15":
        return math.ceil(total_minutes / 15.0) * 0.25
    if criterio == "scatti_30":
        return math.ceil(total_minutes / 30.0) * 0.5

    ore_intere = total_minutes // 60
    resto = total_minutes % 60
    return float(ore_intere + (1 if resto > 30 else 0))


def calcola_compenso_a_tempo_art22bis(
    tariffa_oraria: float,
    ore_stimate: float = 0.0,
    minuti_stimati: int = 0,
    criterio_arrotondamento: str = "ora_frazione_oltre_30",
    massimale_ore: float = 0.0,
    soglia_preapprovazione_ore: float = 0.0,
) -> dict:
    tariffa = _to_float(tariffa_oraria)
    ore = _to_float(ore_stimate)
    minuti_extra = _to_int(minuti_stimati)
    criterio = str(criterio_arrotondamento or "ora_frazione_oltre_30").strip() or "ora_frazione_oltre_30"
    massimale = _to_float(massimale_ore)
    soglia = _to_float(soglia_preapprovazione_ore)
    total_minutes = max(0, int(round(ore * 60)) + max(0, minuti_extra))

    warnings: list[str] = []
    errors: list[str] = []

    if tariffa <= 0:
        errors.append("La tariffa oraria deve essere maggiore di zero.")
    elif tariffa < RANGE_TARIFFA_MIN or tariffa > RANGE_TARIFFA_MAX:
        warnings.append(
            "Tariffa oraria fuori dal parametro indicativo art. 22-bis D.M. 55/2014 "
            f"({RANGE_TARIFFA_MIN:.0f}-{RANGE_TARIFFA_MAX:.0f} euro/ora)."
        )

    if total_minutes <= 0:
        errors.append("Il tempo stimato deve essere maggiore di zero.")

    ore_fatturabili = 0.0 if total_minutes <= 0 else _round_hours(total_minutes, criterio)
    compenso_base = round(tariffa * ore_fatturabili, 2) if not errors else 0.0

    richiede_consenso = True
    if soglia > 0 and ore_fatturabili > soglia:
        warnings.append(
            f"Ore fatturabili oltre la soglia di preapprovazione ({soglia:g} ore): "
            "richiedere consenso preventivo del cliente."
        )
        richiede_consenso = True
    if massimale > 0 and ore_fatturabili > massimale:
        warnings.append(
            f"Ore fatturabili oltre il massimale pattuito ({massimale:g} ore): "
            "serve autorizzazione espressa prima di procedere."
        )
        richiede_consenso = True

    return {
        "source": COMPENSO_A_TEMPO_CODE,
        "source_label": COMPENSO_A_TEMPO_SOURCE_LABEL,
        "fonte_normativa": FONTE_NORMATIVA_COMPENSO_A_TEMPO,
        "tariffa_oraria": round(tariffa, 2),
        "totale_minuti": total_minutes,
        "ore_fatturabili": round(float(ore_fatturabili), 4),
        "criterio_arrotondamento": criterio,
        "compenso_base": compenso_base,
        "range_normativo_min": RANGE_TARIFFA_MIN,
        "range_normativo_max": RANGE_TARIFFA_MAX,
        "massimale_ore": round(massimale, 4),
        "soglia_preapprovazione_ore": round(soglia, 4),
        "richiede_consenso": richiede_consenso,
        "warnings": warnings,
        "errors": errors,
    }


def descrizione_voce_compenso_a_tempo(payload: dict) -> str:
    tariffa = float(payload.get("tariffa_oraria") or 0.0)
    ore = float(payload.get("ore_fatturabili") or 0.0)
    criterio = str(payload.get("criterio_arrotondamento") or "").strip()
    return (
        "Compenso a tempo ex art. 22-bis D.M. 55/2014 - "
        f"tariffa {format_euro_it(tariffa)}/h, {ore:g} ore fatturabili, criterio: {criterio}"
    )
