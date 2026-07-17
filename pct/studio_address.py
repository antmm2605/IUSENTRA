"""Normalizzazione condivisa dell'indirizzo dello studio."""

from __future__ import annotations

import re
from typing import Any

from pct.territorio_italia import get_comune, normalize_comune_key, search_comuni


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _digits(value: Any, limit: int = 5) -> str:
    return "".join(character for character in _text(value) if character.isdigit())[:limit]


def normalize_bic_swift(value: Any) -> str:
    return "".join(character for character in _text(value).upper() if character.isalnum())[:11]


def normalize_studio_location(
    *,
    indirizzo: Any = "",
    cap: Any = "",
    city: Any = "",
    province: Any = "",
) -> dict[str, str]:
    """Completa CAP e provincia dalla banca dati italiana, senza valori fissi."""

    address = _text(indirizzo)
    city_value = _text(city)
    province_value = _text(province).upper()[:2]
    cap_value = _digits(cap)
    if len(cap_value) != 5:
        match = re.search(r"(?<!\d)(\d{5})(?!\d)", address)
        cap_value = match.group(1) if match else ""

    comune = None
    if city_value:
        comune = get_comune(nome=city_value)
        if comune is None:
            key = normalize_comune_key(city_value)
            matches = search_comuni(city_value, limit=20)
            exact = [
                item
                for item in matches
                if normalize_comune_key(item.nome) == key
                and (not province_value or item.sigla_provincia.upper() == province_value)
            ]
            if len(exact) == 1:
                comune = exact[0]

    if comune is not None:
        city_value = comune.nome
        province_value = comune.sigla_provincia.upper()
        valid_caps = [item for item in comune.cap if item]
        if valid_caps and not cap_value:
            cap_value = valid_caps[0]

    return {
        "indirizzo": address,
        "cap": cap_value,
        "city": city_value,
        "province": province_value,
    }


def format_city_province(city: Any, province: Any) -> str:
    city_value = _text(city)
    province_value = _text(province).upper()[:2]
    if city_value and province_value:
        return f"{city_value} ({province_value})"
    return city_value or province_value


def _street_only(indirizzo: str, *, cap: str, city: str) -> str:
    address = _text(indirizzo).strip(" ,;-")
    if not address:
        return ""
    candidates: list[int] = []
    lowered = address.casefold()
    if cap:
        match = re.search(rf"(?<!\d){re.escape(cap)}(?!\d)", address)
        if match and match.start() > 0:
            candidates.append(match.start())
    if city:
        city_index = lowered.rfind(city.casefold())
        city_end = city_index + len(city)
        prefix = address[:city_index].rstrip() if city_index > 0 else ""
        if city_index > 0 and (city_end == len(address) or prefix.endswith((",", ";", "-"))):
            candidates.append(city_index)
    for index in sorted(set(candidates)):
        prefix = address[:index].rstrip(" ,;-")
        separator = address[len(prefix):index]
        if prefix and (separator or address[index - 1] in " ,;-"):
            return prefix
    return address


def compose_studio_address(
    *,
    indirizzo: Any = "",
    cap: Any = "",
    city: Any = "",
    province: Any = "",
    cap_label: bool = False,
) -> str:
    location = normalize_studio_location(
        indirizzo=indirizzo,
        cap=cap,
        city=city,
        province=province,
    )
    city_province = format_city_province(location["city"], location["province"])
    street = _street_only(
        location["indirizzo"],
        cap=location["cap"],
        city=location["city"],
    )
    if cap_label:
        return ", ".join(
            part
            for part in (
                street,
                f"CAP {location['cap']}" if location["cap"] else "",
                city_province,
            )
            if part
        )
    locality = " ".join(part for part in (location["cap"], city_province) if part)
    return ", ".join(part for part in (street, locality) if part)
