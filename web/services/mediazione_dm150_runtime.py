"""Runtime condiviso per i costi organismo mediazione D.M. 150/2023."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from pct.mediazione_dm150 import (
    ESITO_PRIMO_INCONTRO_CON_ACCORDO,
    ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
    ESITO_SUCCESSIVI_CON_ACCORDO,
    ESITO_SUCCESSIVI_SENZA_ACCORDO,
    REGIME_OBBLIGATORIA,
    REGIME_VOLONTARIA,
    calcola_costi_mediazione_dm150,
    descrizione_operativa_mediazione_dm150,
)
from pct.tariffario import parse_numero_locale


MEDIAZIONE_ODM_TABLE_ID = "mediazione_costi_odm_dm150"


def _bool_from_source(source: Any, key: str, default: bool = False) -> bool:
    values = source.getlist(key) if hasattr(source, "getlist") else []
    if values:
        normalized = [str(value or "").strip().lower() for value in values]
        if any(value in {"1", "true", "on", "si", "s", "yes"} for value in normalized):
            return True
        if any(value in {"0", "false", "off", "no"} for value in normalized):
            return False
    raw = str(source.get(key, "") or "").strip().lower()
    if raw in {"1", "true", "on", "si", "s", "yes"}:
        return True
    if raw in {"0", "false", "off", "no"}:
        return False
    return default


def parse_mediazione_odm_context(source: Any) -> Dict[str, Any]:
    regime = str(source.get("mediazione_odm_regime", "") or "").strip()
    esito = str(source.get("mediazione_odm_esito", "") or "").strip()
    return {
        "attiva": _bool_from_source(source, "mediazione_odm_attiva"),
        "regime": regime if regime in {REGIME_VOLONTARIA, REGIME_OBBLIGATORIA} else REGIME_VOLONTARIA,
        "esito": (
            esito
            if esito
            in {
                ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
                ESITO_PRIMO_INCONTRO_CON_ACCORDO,
                ESITO_SUCCESSIVI_SENZA_ACCORDO,
                ESITO_SUCCESSIVI_CON_ACCORDO,
            }
            else ESITO_PRIMO_INCONTRO_SENZA_ACCORDO
        ),
        "art31_comma3_maggiorazione_20": _bool_from_source(
            source, "mediazione_odm_art31_maggiorazione_20"
        ),
    }


def mediazione_odm_context_for_prefill(source: Any) -> Dict[str, Any]:
    context = parse_mediazione_odm_context(source)
    context["has_prefill"] = bool(
        context["attiva"]
        or str(source.get("mediazione_odm_regime", "") or "").strip()
        or str(source.get("mediazione_odm_esito", "") or "").strip()
        or context["art31_comma3_maggiorazione_20"]
    )
    return context


def is_mediazione_practice(practice: Any) -> bool:
    if not practice:
        return False
    practice_id = str(getattr(practice, "id", "") or practice.get("id", "")).strip().lower()
    materia = str(getattr(practice, "materia", "") or practice.get("materia", "")).strip().lower()
    return practice_id == "mediazione" or "mediazione" in materia


def unique_mediazione_practice_ids(practice_ids: Iterable[str]) -> List[str]:
    unique: List[str] = []
    seen = set()
    for practice_id in practice_ids or []:
        current = str(practice_id or "").strip()
        if not current or current in seen:
            continue
        unique.append(current)
        seen.add(current)
    return unique


def calcola_mediazione_odm_da_context(
    valore: Any,
    context: Dict[str, Any],
) -> Dict[str, Any] | None:
    if not (context or {}).get("attiva"):
        return None
    valore_float = parse_numero_locale(valore, 0.0)
    result = calcola_costi_mediazione_dm150(
        valore_float,
        regime=context.get("regime") or REGIME_VOLONTARIA,
        esito=context.get("esito") or ESITO_PRIMO_INCONTRO_SENZA_ACCORDO,
        art31_comma3_maggiorazione_20=bool(context.get("art31_comma3_maggiorazione_20")),
        indeterminabile=valore_float <= 0,
    )
    payload = result.to_dict()
    payload["table_id"] = MEDIAZIONE_ODM_TABLE_ID
    payload["voce_label"] = descrizione_operativa_mediazione_dm150(payload)
    return payload
