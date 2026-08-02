"""Regressioni sulle date visibili del Piano del giorno."""

from pct.daily_plan.serializers import _format_date_it


def test_serializzatore_converte_utc_in_ora_italiana_oltre_mezzanotte():
    assert _format_date_it("2026-08-02T22:30:00Z") == "03/08/2026 00:30"
