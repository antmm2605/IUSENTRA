"""Le varianti richieste devono selezionare lo stesso periodo civile."""

from datetime import date

import pytest

from lex.operational_knowledge.query_dates import resolve_query_dates
from lex.risposte_certe import date_nella_domanda


@pytest.mark.parametrize("value", [
    "14 10 2026", "14/10/26", "14/10/2026", "14.10.2026",
    "14-10-2026", "14-10-26", "14 ottobre 2026", "2026-10-14",
])
@pytest.mark.parametrize("domain", ["PEC ricevute", "Depositi accettati", "Notifiche da fare", "Agenda"])
def test_date_equivalenti(value, domain):
    result = resolve_query_dates(f"{domain} il {value}", today=date(2026, 10, 16))
    assert not result.error
    assert result.ranges == ((date(2026, 10, 14), date(2026, 10, 14)),)


def test_oggi_ieri_attraversano_l_anno_senza_scelta_arbitraria():
    result = resolve_query_dates("PEC oggi e ieri", today=date(2027, 1, 1))
    assert result.ranges == ((date(2026, 12, 31), date(2026, 12, 31)), (date(2027, 1, 1), date(2027, 1, 1)))


@pytest.mark.parametrize("question", [
    "PEC il 31/02/2026", "PEC il 14/10/026", "Agenda dal 16/10/2026 al 14/10/2026",
    "Agenda dal 14/10/2026 al giorno da decidere", "Agenda questa settimana e ieri",
])
def test_errori_non_allargano_la_selezione(question):
    result = resolve_query_dates(question, today=date(2026, 10, 16))
    assert result.error
    assert not result.ranges


def test_periodo_inclusivo_e_calcoli_esistenti():
    result = resolve_query_dates("Agenda dal 14/10/26 al 16/10/26", today=date(2026, 10, 16))
    assert result.ranges == ((date(2026, 10, 14), date(2026, 10, 16)),)
    assert date_nella_domanda("notificato il 14/10/2026") == [date(2026, 10, 14)]
    assert date_nella_domanda("art. 327 c.p.c., RG 2313/2025") == []


def test_anno_assente_non_significa_tutta_la_casella():
    assert resolve_query_dates("PEC del 14/10", today=date(2026, 10, 16)).error
    assert resolve_query_dates("PEC del 14 10", today=date(2026, 10, 16)).error
    assert resolve_query_dates("PEC del 14 ottobre", today=date(2026, 10, 16)).error
    assert resolve_query_dates("PEC dal 14/10/2026", today=date(2026, 10, 16)).error


def test_altro_ieri_non_viene_confuso_con_ieri():
    result = resolve_query_dates("Agenda l’altro ieri", today=date(2026, 10, 16))
    assert result.ranges == ((date(2026, 10, 14), date(2026, 10, 14)),)


@pytest.mark.parametrize("value,expected", [
    ("2026-10-13T22:30:00Z", date(2026, 10, 14)),
    ("2026-10-14T23:30:00-03:00", date(2026, 10, 15)),
    ("2026-10-14T00:30:00+05:00", date(2026, 10, 13)),
    ("2026-10-14T00:30:00", date(2026, 10, 14)),
    ("2026-03-29T22:30:00Z", date(2026, 3, 30)),
    ("2026-10-25T23:30:00Z", date(2026, 10, 26)),
])
def test_filtro_agenda_usa_giorno_civile_italiano(value, expected):
    from lex.operational_knowledge.tools import _row_date

    assert _row_date({"data_ora": value}) == expected
