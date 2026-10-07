"""Conteggi del contesto statistico; nessuna scrittura o accettazione UI simulata."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from web.services import react_statistiche_bridge as bridge


class StatisticsContext(unittest.TestCase):
    def payload(self, day):
        rows = [SimpleNamespace(stato=state, data_scadenza=day, priorita='MEDIA')
                for state in ['ANNULLATO'] * 6 + ['APERTO'] * 5 + ['SCADUTO']]
        empty = SimpleNamespace(tutti=lambda **kwargs: [], statistiche=lambda: {},
                                crediti_aperti=lambda: {'importo': 0})
        deadlines = SimpleNamespace(tutte=lambda **kwargs: rows,
                                    statistiche=lambda: {'totale': 12, 'aperte': 5})
        return bridge.build_react_statistiche_payload(
            get_agenda=lambda: SimpleNamespace(tutti=lambda: [], per_giorno=lambda day: []),
            get_clienti=lambda: empty, get_fascicoli=lambda: empty,
            get_fatturazione=lambda: empty, get_scadenziario=lambda: deadlines)

    def test_note_and_filter_use_the_same_open_records(self):
        payload = self.payload(datetime.now(bridge.ZoneInfo('Europe/Rome')).date().isoformat())
        self.assertEqual(payload['warnings'], [])
        metric = next(item for item in payload['metrics'] if item['id'] == 'scadenze')
        self.assertEqual(metric['value'], 5)
        self.assertEqual(metric['note'], 'Oggi: 5 aperte, 1 scaduta')
        self.assertEqual(sum(item['value'] for item in payload['metricSections']['scadenze'][0]['items']), 5)
        history = next(item for item in payload['records'] if item['id'] == 'scadenze')
        self.assertEqual(history['value'], 12)

    def test_day_is_italian_when_utc_is_still_yesterday(self):
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 5, 23, 30, tzinfo=timezone.utc).astimezone(tz)

        with patch.object(bridge, 'datetime', FrozenDatetime):
            payload = self.payload('2026-10-06')
        metric = next(item for item in payload['metrics'] if item['id'] == 'scadenze')
        self.assertEqual(metric['note'], 'Oggi: 5 aperte, 1 scaduta')


if __name__ == '__main__':
    unittest.main()
