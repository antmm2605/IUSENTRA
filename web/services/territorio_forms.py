"""Helpers per normalizzare indirizzi italiani nei form operativi."""

from __future__ import annotations

import re
from typing import Any, Mapping

from pct.territorio_italia import ComuneItalia, get_comune, normalize_comune_key, search_comuni


def _text(value: Any, fallback: str = "") -> str:
    return str(value or fallback).strip()


def _looks_italian(value: str) -> bool:
    text = normalize_comune_key(value or "Italia")
    return text in {"", "italia", "italy", "it"}


def _query_from_comune(value: str) -> str:
    # Accetta anche valori scelti dalla UI come "Maddaloni (CE)".
    return re.sub(r"\s*\([A-Z]{2}\)\s*$", "", _text(value), flags=re.IGNORECASE).strip()


def resolve_comune_italiano(value: str) -> ComuneItalia | None:
    query = _query_from_comune(value)
    if len(normalize_comune_key(query)) < 2:
        return None
    exact = get_comune(nome=query)
    if exact is not None:
        return exact
    matches = search_comuni(query, limit=5)
    key = normalize_comune_key(query)
    exact_matches = [
        item for item in matches
        if normalize_comune_key(item.nome) == key or normalize_comune_key(item.label) == normalize_comune_key(value)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(matches) == 1:
        return matches[0]
    return None


def normalize_address_fields(
    *,
    via: Any = "",
    civico: Any = "",
    cap: Any = "",
    comune: Any = "",
    provincia: Any = "",
    nazione: Any = "Italia",
) -> dict[str, str]:
    """Normalizza Comune, CAP e provincia usando la banca dati dei Comuni."""

    result = {
        "via": _text(via),
        "civico": _text(civico),
        "cap": _text(cap),
        "comune": _text(comune),
        "provincia": _text(provincia).upper(),
        "nazione": _text(nazione, "Italia") or "Italia",
    }
    if not result["comune"] or not _looks_italian(result["nazione"]):
        return result

    comune_obj = resolve_comune_italiano(result["comune"])
    if comune_obj is None:
        return result

    caps = tuple(item for item in comune_obj.cap if item)
    result["comune"] = comune_obj.nome
    result["provincia"] = comune_obj.sigla_provincia
    if caps and result["cap"] not in caps:
        result["cap"] = caps[0]
    return result


def address_fields_from_form(form: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    return normalize_address_fields(
        via=form.get(f"{prefix}via", ""),
        civico=form.get(f"{prefix}civico", ""),
        cap=form.get(f"{prefix}cap", ""),
        comune=form.get(f"{prefix}comune", ""),
        provincia=form.get(f"{prefix}provincia", ""),
        nazione=form.get(f"{prefix}nazione", "Italia"),
    )
