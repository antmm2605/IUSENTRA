"""Giorno e ora italiani per la logica dell'avvocato (Europe/Rome).

Il server gira in UTC: fra mezzanotte e le 2 italiane `date.today()` e una data
ISO in UTC tagliata ai primi dieci caratteri danno il giorno precedente. Le
decorrenze, le scadenze «di oggi» e le date delle PEC si leggono quindi sempre
nel fuso italiano. Una data senza fuso si considera già italiana (dati
persistiti dal gestionale); una data con «Z» o con offset si converte.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")


def oggi_roma() -> date:
    """Il giorno corrente in Italia."""
    return datetime.now(ROME_TZ).date()


def in_ora_italiana(valore: object) -> datetime | None:
    """Il momento in ora italiana; None se il valore non è una data e ora leggibile."""
    testo = str(valore or "").strip()
    if len(testo) < 10:
        return None
    try:
        momento = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento.replace(tzinfo=ROME_TZ) if momento.tzinfo is None else momento.astimezone(ROME_TZ)


def giorno_italiano(valore: object) -> str:
    """AAAA-MM-GG in ora italiana; per una sola data (senza ora) restituisce la data stessa."""
    testo = str(valore or "").strip()
    if len(testo) == 10:
        return testo
    momento = in_ora_italiana(testo)
    return momento.date().isoformat() if momento else testo[:10]


def ora_italiana(valore: object) -> str:
    """HH:MM in ora italiana; vuota se il valore non porta l'ora."""
    testo = str(valore or "").strip()
    if len(testo) < 16 or testo[10] not in "T ":
        return ""
    momento = in_ora_italiana(testo)
    return momento.strftime("%H:%M") if momento else testo[11:16]


__all__ = ["ROME_TZ", "giorno_italiano", "in_ora_italiana", "oggi_roma", "ora_italiana"]
