"""Provider calendario disponibili per il motore di sincronizzazione."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .apple_caldav import AppleCalDAVProvider
from .base import CalendarProvider
from .demo import DemoCalendarProvider
from .google import GoogleCalendarProvider
from .microsoft import MicrosoftCalendarProvider
from .webcal import WebCalProvider


def build_default_providers(*, demo_store_path: str | Path | None = None) -> dict[str, CalendarProvider]:
    providers: dict[str, CalendarProvider] = {
        "google": GoogleCalendarProvider(),
        "microsoft": MicrosoftCalendarProvider(),
        "outlook": MicrosoftCalendarProvider(),
        "apple_caldav": AppleCalDAVProvider(),
        "apple": AppleCalDAVProvider(),
        "icloud": AppleCalDAVProvider(),
        "webcal": WebCalProvider(),
        "ics": WebCalProvider(),
        "demo": DemoCalendarProvider(store_path=demo_store_path),
    }
    return providers


def provider_for(providers: dict[str, CalendarProvider], name: str) -> CalendarProvider:
    key = str(name or "").strip().lower()
    if key not in providers:
        raise KeyError(f"Provider calendario non disponibile: {name}")
    return providers[key]


__all__ = [
    "AppleCalDAVProvider",
    "CalendarProvider",
    "DemoCalendarProvider",
    "GoogleCalendarProvider",
    "MicrosoftCalendarProvider",
    "WebCalProvider",
    "build_default_providers",
    "provider_for",
]
