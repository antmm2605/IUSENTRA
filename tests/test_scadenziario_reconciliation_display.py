"""Una rettifica tecnica non deve diventare un calcolo giuridico."""
import unittest
from types import SimpleNamespace
from web.services.react_scadenziario_bridge import _has_advanced_calculation, _reconciliation_reason, _readable_source_name


class Checks(unittest.TestCase):
    def record(self, **values):
        return SimpleNamespace(ha_calcolo_avanzato=True, trace=[{'operazione': '2026.10.06.date-sanitarie.annullamento', 'audit_id': 'controlled-audit'}], **values)

    def test_technical_audits_are_not_legal_calculations(self):
        self.assertFalse(_has_advanced_calculation(self.record()))
        old = self.record()
        old.trace[0]['operazione'] = '2026.10.05.riconciliazione.annullamento'
        self.assertFalse(_has_advanced_calculation(old))

    def test_real_and_mixed_calculations_remain_visible(self):
        self.assertTrue(_has_advanced_calculation(self.record(legal_due_at='2026-10-06')))
        self.assertTrue(_has_advanced_calculation(self.record(deadline_profile_code='controlled-profile')))
        mixed = self.record()
        mixed.trace.append({'operazione': 'calcolo_termine'})
        self.assertTrue(_has_advanced_calculation(mixed))
        unproved = self.record()
        unproved.trace[0].pop('audit_id')
        self.assertTrue(_has_advanced_calculation(unproved))

    def test_both_reconciliation_reasons_are_explained(self):
        for kind in ('automatica', 'documentata'):
            item = SimpleNamespace(note=f'Nota originaria\nRettifica {kind} della lettura: Data di validità della tessera; non un termine processuale.')
            self.assertEqual(_reconciliation_reason(item), 'Data di validità della tessera; non un termine processuale.')
        self.assertEqual(_reconciliation_reason(SimpleNamespace(note='Nota del difensore')), '')

    def test_source_names_are_readable_without_losing_real_filenames(self):
        self.assertEqual(_readable_source_name('documento:abc-123'), 'Documento del fascicolo')
        self.assertEqual(_readable_source_name('pec:abc_123'), 'Messaggio PEC')
        self.assertEqual(_readable_source_name('Provvedimento del giudice.pdf'), 'Provvedimento del giudice.pdf')


if __name__ == '__main__':
    unittest.main(verbosity=2)
