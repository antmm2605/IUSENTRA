"""Guardrail di lettura, successivi alla prova materiale dei cataloghi."""
import unittest
from datetime import date
from types import SimpleNamespace as Row
from unittest.mock import patch

from web.services.preparazione_udienza_associazione import fascicolo_udienza
from web.services.react_statistiche_bridge import _monthly_billing
from web.services.lex_operational_surface import _build_udienza_surface


class OperationalCatalogRegressionTests(unittest.TestCase):
    def test_draft_cancelled_and_previous_year_are_not_current_turnover(self):
        year = date.today().year
        invoices = [Row(data_emissione=f'{year}-01-12', stato=state, totale=amount)
                    for state, amount in [('BOZZA', 1000), ('ANNULLATA', 2000),
                                          ('EMESSA', 100), ('SCADUTA', 50), ('PAGATA', 25)]]
        invoices.append(Row(data_emissione=f'{year - 1}-01-12', stato='PAGATA', totale=500))
        months = _monthly_billing(invoices)
        self.assertEqual(months[0]['value'], 175)
        self.assertEqual(months[0]['secondaryValue'], 25)
        self.assertEqual(sum(row['value'] for row in months), 175)

    def test_same_court_never_identifies_a_hearing_without_identity(self):
        appointment = Row(id='meeting', titolo='Udienza', procedimento='',
                          data_ora='2026-10-06T14:00:00', tribunale='Vicenza', id_cliente='')
        case = Row(id='case', numero='2026/001', numero_rg='901', anno_rg='2026',
                   tribunale='Vicenza', id_cliente='client', attivita=[], data_prossima_udienza='')
        self.assertIsNone(fascicolo_udienza(appointment, [case]))
        appointment.procedimento = 'RG 901/2026'
        self.assertIs(fascicolo_udienza(appointment, [case]), case)
        duplicate = Row(**{**vars(case), 'id': 'other-case'})
        self.assertIsNone(fascicolo_udienza(appointment, [case, duplicate]))

    def test_explicit_conflicting_links_remain_ambiguous(self):
        appointment = Row(id='meeting', titolo='Udienza', procedimento='')
        first = Row(id='one', attivita=[Row(id_appuntamento='meeting')])
        second = Row(id='two', attivita=[])
        session = Row(id_appuntamento='meeting', id_fascicolo='two', stato='in_corso')
        self.assertIsNone(fascicolo_udienza(appointment, [first, second], [session]))

    def test_hearing_horizon_excludes_past_and_keeps_all_matching_cases(self):
        cases = [dict(id=str(day), giorni_udienza=day, critical_badges=[])
                 for day in [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 15]]
        with patch('web.services.lex_operational_surface.build_hearing_preparation_dashboard',
                   return_value=dict(cases=cases, metrics=[])):
            result = _build_udienza_surface(14)
        self.assertEqual([row['id'] for row in result['cases']],
                         ['0', '1', '2', '3', '4', '5', '6', '7', '8'])


if __name__ == '__main__':
    unittest.main()
