"""Backfill idempotente dei profili deposito sui record SQL esistenti."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pct.pratiche_collegate_catalog import (
    codice_oggetto_pst_entry,
    list_codici_oggetto_pst,
    normalize_codice_oggetto_pst,
    resolve_codice_oggetto_pst_payload,
)
from pct.profilo_deposito import costruisci_profilo_deposito


CORE_DEPOSIT_PROFILE_TABLES: tuple[tuple[str, str], ...] = (
    ("fascicoli", "id"),
    ("preventivi_records", "preventivo_id"),
    ("conferimenti_records", "conferimento_id"),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower_key(value: Any) -> str:
    return " ".join(_text(value).lower().split())


def _load_json(value: Any, fallback: Any) -> Any:
    if isinstance(value, type(fallback)):
        return value
    if not value:
        return fallback
    try:
        parsed = json.loads(str(value))
    except Exception:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _profile_get(profile: dict[str, Any], *path: str) -> Any:
    cur: Any = profile
    for key in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return cur


def _first(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


@lru_cache(maxsize=1)
def _unique_codice_by_description() -> dict[str, str]:
    counts: dict[str, int] = {}
    matches: dict[str, str] = {}
    for row in list_codici_oggetto_pst():
        key = _lower_key(row.get("descrizione"))
        code = _text(row.get("codice"))
        if not key or not code:
            continue
        counts[key] = counts.get(key, 0) + 1
        matches[key] = code
    return {key: code for key, code in matches.items() if counts.get(key) == 1}


def _resolve_codice_payload(*candidates: Any) -> dict[str, str]:
    for candidate in candidates:
        text = _text(candidate)
        if not text:
            continue
        payload = resolve_codice_oggetto_pst_payload(text)
        if payload.get("codice_oggetto_pst"):
            return payload
        exact_code = _unique_codice_by_description().get(_lower_key(text), "")
        if exact_code and codice_oggetto_pst_entry(exact_code):
            return resolve_codice_oggetto_pst_payload(exact_code)
    return resolve_codice_oggetto_pst_payload("")


def _record_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = _load_json(row.get("dati_json"), {})
    if payload:
        return payload
    return {key: value for key, value in row.items() if key != "dati_json"}


def build_deposit_profile_for_record(
    table: str,
    row: dict[str, Any],
    *,
    verify_certificates: bool = False,
    force_refresh_certificates: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ricostruisce il profilo deposito da una riga core SQL."""

    payload = _record_payload(row)
    current_profile = _load_json(row.get("profilo_deposito_json"), {})
    if not current_profile:
        current_profile = payload.get("profilo_deposito") if isinstance(payload.get("profilo_deposito"), dict) else {}

    oggetto = _first(row.get("oggetto"), payload.get("oggetto"), row.get("titolo"), payload.get("titolo"))
    codice_payload = _resolve_codice_payload(
        payload.get("codice_oggetto_pst"),
        row.get("codice_oggetto_pst"),
        _profile_get(current_profile, "codice_deposito", "codice_oggetto_pst"),
        oggetto,
    )
    ufficio = _first(
        row.get("tribunale"),
        payload.get("tribunale"),
        _profile_get(current_profile, "ufficio", "nome"),
    )
    tipo = _first(row.get("tipo"), payload.get("tipo"), _profile_get(current_profile, "pratica", "tipo_fascicolo"))

    profile = costruisci_profilo_deposito(
        id_pratica=_first(row.get("id_pratica"), payload.get("id_pratica"), _profile_get(current_profile, "pratica", "id_pratica")),
        area_pratica=_first(row.get("area_pratica"), payload.get("area_pratica"), _profile_get(current_profile, "pratica", "area_pratica")),
        tipo_procedimento=_first(
            row.get("tipo_procedimento"),
            payload.get("tipo_procedimento"),
            _profile_get(current_profile, "pratica", "tipo_procedimento"),
        ),
        tipo=tipo,
        source=_first(payload.get("source"), _profile_get(current_profile, "pratica", "source")),
        canale_operativo=_first(row.get("canale_operativo"), payload.get("canale_operativo")),
        registro_operativo=_first(
            row.get("registro_operativo"),
            payload.get("registro_operativo"),
            _profile_get(current_profile, "pratica", "registro_operativo"),
        ),
        procedura_operativa_codice=_first(
            row.get("procedura_operativa_codice"),
            payload.get("procedura_operativa_codice"),
            _profile_get(current_profile, "pratica", "procedura_operativa_codice"),
        ),
        codice_oggetto_pst=codice_payload["codice_oggetto_pst"],
        fonte_codice_oggetto=_first(
            row.get("fonte_codice_oggetto"),
            payload.get("fonte_codice_oggetto"),
            codice_payload["fonte_codice_oggetto"],
        ),
        file_fonte_codice_oggetto=_first(
            row.get("file_fonte_codice_oggetto"),
            payload.get("file_fonte_codice_oggetto"),
            codice_payload["file_fonte_codice_oggetto"],
        ),
        ufficio=ufficio,
        verifica_certificato=bool(verify_certificates and ufficio),
        force_refresh_certificato=force_refresh_certificates,
        richiedi_ufficio=bool(ufficio),
        profilo_origine=current_profile if isinstance(current_profile, dict) else {},
    )
    return profile, payload


def deposit_profile_needs_update(current: dict[str, Any], profile: dict[str, Any]) -> bool:
    if not current:
        return True
    checks = (
        ("canale", "codice"),
        ("codice_deposito", "codice_oggetto_pst"),
        ("ufficio", "codice_pst"),
        ("ufficio", "pec"),
        ("certificato_cifratura", "richiesto"),
        ("certificato_cifratura", "verificato"),
        ("certificato_cifratura", "path"),
        ("certificato_cifratura", "sha256"),
        ("source_of_truth",),
    )
    for path in checks:
        new_value = _profile_get(profile, *path)
        if new_value and _profile_get(current, *path) != new_value:
            return True
    return False


def merge_profile_into_payload(payload: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    merged = dict(payload or {})
    merged["profilo_deposito"] = profile
    codice = _text(_profile_get(profile, "codice_deposito", "codice_oggetto_pst"))
    if codice and not _text(merged.get("codice_oggetto_pst")):
        merged["codice_oggetto_pst"] = codice
        merged["fonte_codice_oggetto"] = _text(_profile_get(profile, "codice_deposito", "fonte"))
        merged["file_fonte_codice_oggetto"] = _text(_profile_get(profile, "codice_deposito", "file"))
    return merged
