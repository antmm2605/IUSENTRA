from datetime import datetime
from types import SimpleNamespace

import pytest

from web.services.react_agenda_bridge import _agenda_event


@pytest.mark.parametrize('minutes', [1, 5, 10, 15, 60])
def test_agenda_payload_preserves_actual_duration(minutes):
    event = _agenda_event(SimpleNamespace(
        id='controlled-duration', titolo='Collaudo durata', tipo='ALTRO',
        stato='PROGRAMMATO', data_ora_dt=datetime(2026, 10, 19, 9),
        durata_minuti=minutes,
    ))
    assert event is not None
    assert event['durationLabel'] == f'{minutes} min'
    assert (datetime.fromisoformat(event['end']) - datetime.fromisoformat(event['start'])).total_seconds() == minutes * 60
