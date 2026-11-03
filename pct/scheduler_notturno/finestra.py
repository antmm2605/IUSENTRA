"""Finestra notturna 21:30-07:30 Europe/Rome e chiave della notte (data della sera di partenza)."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")


def _hhmm(valore: str, predefinito: time) -> time:
    try:
        ore, minuti = str(valore).split(":", 1)
        return time(int(ore), int(minuti))
    except (TypeError, ValueError):
        return predefinito


def inizio() -> time:
    return _hhmm(os.getenv("PCT_NOTTE_INIZIO", "21:30"), time(21, 30))


def fine() -> time:
    return _hhmm(os.getenv("PCT_NOTTE_FINE", "07:30"), time(7, 30))


def adesso() -> datetime:
    return datetime.now(ROME_TZ)


def _rome(valore: datetime) -> datetime:
    return valore.replace(tzinfo=ROME_TZ) if valore.tzinfo is None else valore.astimezone(ROME_TZ)


def in_finestra(momento: datetime | None = None) -> bool:
    ora = _rome(momento or adesso()).time()
    return ora >= inizio() or ora < fine()


def sera_della_notte(momento: datetime | None = None) -> date:
    """La data della sera in cui la notte è cominciata (dopo mezzanotte è il giorno prima)."""
    m = _rome(momento or adesso())
    return m.date() - timedelta(days=1) if m.time() < fine() else m.date()


def scadenza(momento: datetime | None = None) -> datetime:
    """Le 07:30 della mattina che chiude la notte in corso."""
    sera = sera_della_notte(momento)
    return datetime.combine(sera + timedelta(days=1), fine(), tzinfo=ROME_TZ)
