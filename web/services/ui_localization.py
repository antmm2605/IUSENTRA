"""UI localization helpers for Italian-facing templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

EMPTY_UI_VALUE = "—"

WEEKDAYS_IT = [
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
]
WEEKDAYS_SHORT_IT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MONTHS_IT = [
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
]
MONTHS_SHORT_IT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


@dataclass(frozen=True)
class ParsedTemporalValue:
    date_value: date
    datetime_value: datetime | None = None


def parse_temporal_value(value: Any) -> ParsedTemporalValue | None:
    """Best-effort parser for dates/datetimes coming from JSON, ORM or templates."""
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return ParsedTemporalValue(date_value=value.date(), datetime_value=value)

    if isinstance(value, date):
        return ParsedTemporalValue(date_value=value)

    if isinstance(value, time):
        today = date.today()
        return ParsedTemporalValue(
            date_value=today,
            datetime_value=datetime.combine(today, value),
        )

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        return ParsedTemporalValue(date_value=dt.date(), datetime_value=dt)
    except ValueError:
        pass

    candidate_date = text
    for sep in ("T", " "):
        if sep in candidate_date:
            candidate_date = candidate_date.split(sep, 1)[0]
            break

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            parsed_date = datetime.strptime(candidate_date[:10], fmt).date()
            return ParsedTemporalValue(date_value=parsed_date)
        except ValueError:
            continue

    return None


def format_date(value: Any) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    return parsed.date_value.strftime("%d/%m/%Y")


def format_datetime(value: Any) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    if parsed.datetime_value is None:
        return format_date(parsed.date_value)
    return f"{format_date(parsed.date_value)} {parsed.datetime_value.strftime('%H:%M')}"


def format_time_only(value: Any) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    if parsed.datetime_value:
        return parsed.datetime_value.strftime("%H:%M")
    return "00:00"


def format_date_long(value: Any, *, include_weekday: bool = False) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    day = parsed.date_value.day
    month = MONTHS_IT[parsed.date_value.month - 1]
    year = parsed.date_value.year
    core = f"{day} {month} {year}"
    if not include_weekday:
        return core
    weekday = WEEKDAYS_IT[parsed.date_value.weekday()]
    return f"{weekday} {core}"


def format_short_weekday_date(value: Any) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    weekday = WEEKDAYS_SHORT_IT[parsed.date_value.weekday()]
    month = MONTHS_SHORT_IT[parsed.date_value.month - 1]
    return f"{weekday} {parsed.date_value.day:02d} {month} {parsed.date_value.year}"


def format_day_month(value: Any) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    month = MONTHS_SHORT_IT[parsed.date_value.month - 1]
    return f"{parsed.date_value.day:02d} {month}"


def format_day_month_year(value: Any) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    month = MONTHS_SHORT_IT[parsed.date_value.month - 1]
    return f"{parsed.date_value.day:02d} {month} {parsed.date_value.year}"


def format_month_short(value: Any) -> str:
    parsed = parse_temporal_value(value)
    if not parsed:
        return EMPTY_UI_VALUE if value in (None, "") else str(value)
    return MONTHS_SHORT_IT[parsed.date_value.month - 1]
