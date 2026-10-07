from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from pct.scadenziario import StatoTermine
from web.services.topbar_operational import _deadline_status


@pytest.mark.parametrize('offset', [-1, 0, 1])
@pytest.mark.parametrize('state, expected', [
    (StatoTermine.SCADUTO, 'overdue'),
    (StatoTermine.COMPLETATO, 'completed'),
    (StatoTermine.ANNULLATO, 'cancelled'),
])
def test_stato_registrato_prevale_sulla_data(offset, state, expected):
    today = date(2026, 10, 6)
    deadline = SimpleNamespace(stato=state, data_scadenza=(today + timedelta(days=offset)).isoformat())
    assert _deadline_status(deadline, today) == expected


@pytest.mark.parametrize('offset, expected', [(-1, 'overdue'), (0, 'open'), (1, 'open')])
def test_scadenza_aperta_usa_la_data_legale(offset, expected):
    today = date(2026, 10, 6)
    deadline = SimpleNamespace(stato=StatoTermine.APERTO, data_scadenza=(today + timedelta(days=offset)).isoformat())
    assert _deadline_status(deadline, today) == expected
