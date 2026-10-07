"""Guardrail sul confronto delle date registrate, senza modificare gli adempimenti."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest

from web.services.react_statistiche_bridge import _parse_date, _productivity


def deadline(due, closed):
    return SimpleNamespace(stato="COMPLETATO", data_scadenza=due, completata_il=closed)


class StatisticheChiusureTests(unittest.TestCase):
    def test_missing_dates_are_explicit_and_excluded_from_percentage(self):
        result = _productivity([], [
            deadline("2026-10-05", "2026-10-05T18:30:00Z"),
            deadline("2026-10-05", "2026-10-06T08:00:00Z"),
            deadline("2026-10-05", ""),
            deadline("", "2026-10-05T08:00:00Z"),
        ])
        self.assertEqual(result["scadenze_completate"], 4)
        self.assertEqual(result["chiusure_entro_termine"], 1)
        self.assertEqual(result["chiusure_dopo_termine"], 1)
        self.assertEqual(result["chiusure_non_verificabili"], 2)
        self.assertEqual(result["tasso_scadenze_rispettate_pct"], 50)

    def test_no_comparable_dates_never_claim_zero_or_all_respected(self):
        result = _productivity([], [deadline("2026-10-05", "not-a-date")])
        self.assertIsNone(result["tasso_scadenze_rispettate_pct"])
        self.assertEqual(result["chiusure_non_verificabili"], 1)

    def test_midnight_conversion_uses_the_italian_day(self):
        result = _productivity([], [deadline("2026-10-05", "2026-10-05T22:30:00Z")])
        self.assertEqual(result["chiusure_dopo_termine"], 1)
        self.assertEqual(_parse_date("2026-01-05T23:30:00Z"), date(2026, 1, 6))
        self.assertEqual(_parse_date(datetime(2026, 10, 5, 22, 30, tzinfo=timezone.utc)), date(2026, 10, 6))

    def test_local_date_only_and_naive_datetime_keep_their_day(self):
        self.assertEqual(_parse_date("2026-10-05"), date(2026, 10, 5))
        self.assertEqual(_parse_date(datetime(2026, 10, 5, 23, 30)), date(2026, 10, 5))
        self.assertIsNone(_parse_date("2026-10-05broken"))

    def test_cancelled_and_open_rows_do_not_change_closure_statistics(self):
        result = _productivity([], [
            SimpleNamespace(stato="ANNULLATO", data_scadenza="2026-01-01", completata_il="2026-01-02"),
            SimpleNamespace(stato="APERTO", data_scadenza="2027-01-01", completata_il=""),
        ])
        self.assertEqual(result["scadenze_completate"], 0)
        self.assertEqual(result["chiusure_entro_termine"], 0)
        self.assertEqual(result["chiusure_dopo_termine"], 0)


if __name__ == "__main__":
    unittest.main()
