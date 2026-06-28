"""Formattazioni visibili condivise da IUSENTRA."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo


DISPLAY_TIMEZONE = ZoneInfo("Europe/Rome")


def _coerce_amount(value: Any) -> float:
    if isinstance(value, str):
        text = (
            value.strip()
            .replace("€", "")
            .replace("EUR", "")
            .replace("eur", "")
            .replace("euro", "")
            .replace("Euro", "")
            .strip()
        )
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        text = text.replace(" ", "")
        try:
            return float(text or 0.0)
        except ValueError:
            return 0.0
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def format_decimal_it(value: Any, *, places: int = 2) -> str:
    """Formatta un numero con separatori italiani, senza simbolo valuta."""

    amount = round(_coerce_amount(value), places)
    text = f"{amount:,.{places}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def format_euro_it(value: Any) -> str:
    """Formatta un importo visibile come euro italiano."""

    return f"€ {format_decimal_it(value)}"


def format_signed_euro_it(value: Any) -> str:
    """Formatta un importo euro con segno esplicito, per differenze e incrementi."""

    amount = _coerce_amount(value)
    sign = "+ " if amount >= 0 else "- "
    return f"{sign}€ {format_decimal_it(abs(amount))}"


def parse_datetime_rome(value: Any) -> datetime | None:
    """Converte date/timestamp tecnici nel fuso visibile Europe/Rome."""

    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, time):
        parsed = datetime.combine(date.today(), value)
    else:
        text = str(value).strip()
        if not text:
            return None
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        candidates = [normalized]
        if "T" in normalized or " " in normalized:
            candidates.append(normalized[:19])
        candidates.append(normalized[:10])
        parsed = None
        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = datetime.fromisoformat(candidate)
                break
            except ValueError:
                continue
        if parsed is None:
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
        if parsed is None:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=DISPLAY_TIMEZONE)
    return parsed.astimezone(DISPLAY_TIMEZONE)


def format_date_it(value: Any) -> str:
    """Formatta una data visibile in formato italiano."""

    parsed = parse_datetime_rome(value)
    return "" if parsed is None else parsed.strftime("%d/%m/%Y")


def format_time_it(value: Any) -> str:
    """Formatta un orario visibile in Europe/Rome."""

    parsed = parse_datetime_rome(value)
    return "" if parsed is None else parsed.strftime("%H:%M")


def format_datetime_it(value: Any, *, include_timezone: bool = False) -> str:
    """Formatta data e ora visibili in italiano, convertendo UTC in Europe/Rome."""

    parsed = parse_datetime_rome(value)
    if parsed is None:
        return "" if value in (None, "") else str(value)
    label = parsed.strftime("%d/%m/%Y %H:%M")
    return f"{label} (Europe/Rome)" if include_timezone else label
