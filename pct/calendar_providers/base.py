"""Interfacce comuni per i provider calendario server-side."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Protocol


class CalendarProviderError(RuntimeError):
    """Errore operativo di un provider calendario."""


class CalendarProvider(Protocol):
    provider_name: str

    def list_calendars(self, account: dict[str, Any]) -> list[dict[str, Any]]:
        ...

    def pull_changes(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        cursor: str = "",
    ) -> dict[str, Any]:
        ...

    def push_event(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        event: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def delete_event(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        ...


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_datetime(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    raw = str(value or "").strip()
    if not raw:
        return (fallback or datetime.now()).replace(microsecond=0)
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        if len(raw) == 10:
            return datetime.combine(date.fromisoformat(raw), datetime.min.time())
        return datetime.fromisoformat(raw).replace(microsecond=0)
    except ValueError:
        return (fallback or datetime.now()).replace(microsecond=0)


def event_content_hash(event: dict[str, Any]) -> str:
    keys = (
        "title",
        "description",
        "location",
        "start",
        "end",
        "all_day",
        "status",
        "categories",
        "sequence",
    )
    return stable_hash({key: event.get(key) for key in keys})


def normalise_provider_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = dict(event or {})
    payload.pop("raw", None)
    payload.setdefault("id", str(payload.get("external_event_id") or payload.get("uid") or "").strip())
    payload.setdefault("uid", str(payload.get("id") or "").strip())
    payload.setdefault("title", str(payload.get("summary") or payload.get("title") or "Evento calendario").strip())
    payload.setdefault("description", str(payload.get("description") or "").strip())
    payload.setdefault("location", str(payload.get("location") or "").strip())
    payload.setdefault("status", str(payload.get("status") or "confirmed").strip().lower())
    payload["deleted"] = bool(payload.get("deleted") or payload.get("status") == "cancelled")
    payload["all_day"] = bool(payload.get("all_day"))
    payload.setdefault("updated_at", utc_now_iso())
    payload.setdefault("etag", "")
    payload.setdefault("change_key", "")
    payload.setdefault("sequence", 0)
    categories = payload.get("categories") or []
    if isinstance(categories, str):
        categories = [item.strip() for item in categories.split(",") if item.strip()]
    payload["categories"] = list(categories) if isinstance(categories, (list, tuple, set)) else []
    return payload


def build_ics_event(event: dict[str, Any], uid: str) -> str:
    """Crea un VEVENT minimale per provider CalDAV."""

    def _escape(value: Any) -> str:
        return (
            str(value or "")
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(",", "\\,")
            .replace(";", "\\;")
        )

    def _dt(value: Any, *, all_day: bool = False) -> str:
        parsed = parse_datetime(value)
        if all_day:
            return parsed.strftime("%Y%m%d")
        return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") if parsed.tzinfo else parsed.strftime("%Y%m%dT%H%M%S")

    all_day = bool(event.get("all_day"))
    dtstart_name = "DTSTART;VALUE=DATE" if all_day else "DTSTART"
    dtend_name = "DTEND;VALUE=DATE" if all_day else "DTEND"
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//IUSENTRA//Calendar Sync//IT",
            "BEGIN:VEVENT",
            f"UID:{_escape(uid)}",
            f"SUMMARY:{_escape(event.get('title'))}",
            f"{dtstart_name}:{_dt(event.get('start'), all_day=all_day)}",
            f"{dtend_name}:{_dt(event.get('end') or event.get('start'), all_day=all_day)}",
            f"LOCATION:{_escape(event.get('location'))}",
            f"DESCRIPTION:{_escape(event.get('description'))}",
            f"STATUS:{'CANCELLED' if event.get('status') == 'cancelled' else 'CONFIRMED'}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
