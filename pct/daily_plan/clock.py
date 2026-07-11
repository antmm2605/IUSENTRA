"""Clock iniettabile con fuso orario dello studio (Europe/Rome).

I motori decisionali del piano del giorno non devono usare direttamente
``date.today()`` o ``datetime.now()``: ricevono un :class:`Clock` così i
test possono fissare una data e la logica resta coerente col fuso italiano
anche quando il server gira in UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")


@dataclass(frozen=True)
class Clock:
    """Sorgente di tempo deterministica e tenant-neutrale.

    ``fixed_now`` permette ai test di bloccare l'orologio; se naive viene
    interpretato nel fuso ``tz``.
    """

    tz: tzinfo = ROME_TZ
    fixed_now: datetime | None = None

    def now(self) -> datetime:
        """Datetime aware nel fuso dello studio."""
        if self.fixed_now is not None:
            value = self.fixed_now
            if value.tzinfo is None:
                return value.replace(tzinfo=self.tz)
            return value.astimezone(self.tz)
        return datetime.now(self.tz)

    def today(self) -> date:
        return self.now().date()

    def local_naive_now(self) -> datetime:
        """Datetime naive locale, per confronti con dati persistiti naive."""
        return self.now().replace(tzinfo=None)

    def to_local(self, value: datetime) -> datetime:
        """Normalizza un datetime (naive o aware) nel fuso dello studio."""
        if value.tzinfo is None:
            return value.replace(tzinfo=self.tz)
        return value.astimezone(self.tz)

    def local_date_of(self, value: datetime) -> date:
        """Data locale (Europe/Rome) di un datetime naive o aware."""
        return self.to_local(value).date()


def system_clock(tz: tzinfo | None = None) -> Clock:
    """Clock di sistema nel fuso dello studio (default Europe/Rome)."""
    return Clock(tz=tz or ROME_TZ)


__all__ = ["Clock", "ROME_TZ", "system_clock"]
