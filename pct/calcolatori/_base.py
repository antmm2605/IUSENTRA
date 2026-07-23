"""Helper condivisi per i calcolatori giuridici modulari.

Funzioni di parsing e formattazione usate dai moduli di ``pct/calcolatori``.
Nessuna logica di dominio: solo normalizzazione input e utilità di calendario.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Optional


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        raw = str(value).replace("€", "").replace(" ", "").strip()
        if not raw:
            return default
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        return float(raw)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "si", "sì", "yes", "on"}


def parse_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = clean_text(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def days_inclusive(start: date, end: date) -> int:
    return (end - start).days + 1


def year_denominator(day: date) -> int:
    year = day.year
    return 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365


def fmt_date_it(value: Any) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else clean_text(value)


def payload_get(payload: Mapping[str, Any], key: str, default: Any = "") -> Any:
    try:
        return payload.get(key, default)
    except AttributeError:
        return default
