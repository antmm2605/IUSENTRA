"""Riferimenti temporali della Panoramica React nel fuso dell'utente.

Regola obbligatoria (CLAUDE.md / AGENTS.md): agenda, scadenze, conteggi di
oggi e riepiloghi economici esposti in UI ragionano su ``Europe/Rome``, non
sull'ora UTC del server. Fra la mezzanotte italiana e le 2 il giorno UTC e'
ancora quello precedente: senza questa normalizzazione la Panoramica mostra
gli impegni di ieri e, il primo del mese, il fatturato del mese scorso.

Il modulo resta volutamente minimo (sole primitive di calendario) cosi' da
poter essere riusato dai bridge React senza trascinare dipendenze Flask.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")

__all__ = ["ROME_TZ", "adesso_rome", "oggi_rome", "rome_aware"]


def adesso_rome() -> datetime:
    """Istante corrente con fuso ``Europe/Rome`` (sempre timezone-aware)."""

    return datetime.now(ROME_TZ)


def oggi_rome() -> date:
    """Data odierna lato utente: sostituisce ``date.today()`` nelle viste."""

    return adesso_rome().date()


def rome_aware(value: datetime) -> datetime:
    """Normalizza un datetime a ``Europe/Rome``, anche se privo di fuso.

    I dati persistiti (JSON agenda/scadenze) contengono sia stringhe naive sia
    stringhe con offset: confrontarle senza normalizzare solleva
    ``TypeError: can't compare offset-naive and offset-aware datetimes``.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=ROME_TZ)
    return value.astimezone(ROME_TZ)
