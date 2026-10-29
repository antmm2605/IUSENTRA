"""Giorno e ora italiani: PEC ricevute fra mezzanotte e le 2 e date con e senza fuso (regola Europe/Rome)."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from pct.archivio_letture.collaudo import Contesto
from pct.archivio_letture.motore_pec import fatti_da_messaggio
from pct.ora_italiana import ROME_TZ, giorno_italiano, in_ora_italiana, oggi_roma, ora_italiana


@pytest.mark.parametrize(
    ("valore", "giorno", "ora"),
    [
        ("2026-10-28T23:30:00Z", "2026-10-29", "00:30"),  # ora solare: UTC+1
        ("2026-07-14T22:15:00Z", "2026-07-15", "00:15"),  # ora legale: UTC+2
        ("2026-07-14T22:15:00+00:00", "2026-07-15", "00:15"),
        ("2026-07-15T00:15:00+02:00", "2026-07-15", "00:15"),
        ("2026-07-15T00:15:00", "2026-07-15", "00:15"),  # senza fuso: già italiana
        ("2026-07-15", "2026-07-15", ""),
        ("", "", ""),
    ],
)
def test_giorno_e_ora_in_italia(valore: str, giorno: str, ora: str) -> None:
    assert giorno_italiano(valore) == giorno
    assert ora_italiana(valore) == ora


def test_date_aware_e_naive_confrontabili() -> None:
    aware = in_ora_italiana("2026-10-28T23:30:00Z")
    naive = in_ora_italiana("2026-10-29T00:30:00")
    assert aware == naive
    assert aware.tzinfo is not None and naive.tzinfo is not None


def test_oggi_roma_e_il_giorno_italiano() -> None:
    assert oggi_roma() == datetime.now(timezone.utc).astimezone(ROME_TZ).date()
    assert isinstance(oggi_roma(), date)


def test_ricevuta_pec_dopo_mezzanotte_ha_il_giorno_italiano() -> None:
    # Prima della 2.457.7 la consegna delle 00:30 italiane risultava del giorno prima (UTC tagliato a 10 caratteri).
    messaggio = {"received_at": "2026-10-28T23:30:00Z", "subject": "CONSEGNA: notifica ai sensi della L. 53/1994", "from": "posta-certificata@pec.example.it"}
    fatti = fatti_da_messaggio(messaggio, Contesto())
    date_consegna = [f.valore for f in fatti if f.categoria == "data" and f.campo == "consegna"]
    assert date_consegna == ["2026-10-29T00:30"]
