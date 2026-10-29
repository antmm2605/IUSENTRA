"""Calendario Microsoft: orari italiani in andata e ritorno (Graph lavora in UTC senza offset)."""
from __future__ import annotations

from pct.agenda import _dt_locale
from pct.calendar_providers.microsoft import MicrosoftCalendarProvider, _da_graph, _per_graph


def test_in_scrittura_l_orario_italiano_diventa_utc() -> None:
    # Prima della 2.457.7 «09:30+01:00» partiva dichiarato UTC: in Outlook l'udienza compariva alle 10:30.
    assert _per_graph("2026-11-23T09:30:00+01:00", all_day=False) == "2026-11-23T08:30:00"
    assert _per_graph("2026-07-15T09:30:00", all_day=False) == "2026-07-15T07:30:00"  # senza fuso: ora italiana legale
    assert _per_graph("2026-11-23", all_day=True) == "2026-11-23"


def test_in_lettura_l_utc_di_graph_resta_utc() -> None:
    letto = _da_graph("2026-11-23T08:30:00.0000000", all_day=False)
    assert letto == "2026-11-23T08:30:00+00:00"
    assert _dt_locale(letto).isoformat() == "2026-11-23T09:30:00"
    assert _da_graph("2026-11-23T00:00:00.0000000", all_day=True) == "2026-11-23"


def test_evento_graph_mappato_con_offset() -> None:
    evento = MicrosoftCalendarProvider.__new__(MicrosoftCalendarProvider)._map_event({
        "id": "x", "subject": "Udienza", "isAllDay": False,
        "start": {"dateTime": "2026-07-14T22:15:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-07-14T23:15:00.0000000", "timeZone": "UTC"},
    })
    assert _dt_locale(evento["start"]).isoformat() == "2026-07-15T00:15:00"
