"""Guardrail della cessazione governata degli avvisi PEC, senza dati dello studio."""
import unittest
from types import SimpleNamespace
from web.services.notifications_runtime import _superseded_pec_notification_keys

def item(identifier, status, key, linked=''):
    return SimpleNamespace(id=identifier,stato=status,external_uid=key,note='',id_appuntamento=linked)

def sources(appointments=(),deadlines=(),current=()):
    agenda=SimpleNamespace(tutti=lambda:list(appointments))
    scad=SimpleNamespace(tutte=lambda **kwargs:list(deadlines))
    return _superseded_pec_notification_keys(agenda,scad,[{'id':key} for key in current])

class ProjectionGovernanceTests(unittest.TestCase):
    def test_cancelled_and_postponed_primary_sources_expire(self):
        for status in ('ANNULLATO','COMPLETATO','RINVIATO'):
            with self.subTest(status=status):
                self.assertEqual(sources([item('a',status,'PEC_AUDIT:cancelled')]),{'PEC_AUDIT:cancelled:deadline'})

    def test_closed_deadline_expires_without_deleting_projection(self):
        for status in ('ANNULLATO','COMPLETATO'):
            self.assertEqual(sources(deadlines=[item('s',status,'PEC_AUDIT:closed')]),{'PEC_AUDIT:closed:deadline'})

    def test_shared_key_retained_by_an_active_primary_source(self):
        key='PEC_AUDIT:shared'
        self.assertEqual(sources([item('a','ANNULLATO',key),item('b','PROGRAMMATO',key)]),set())
        self.assertEqual(sources([item('a','ANNULLATO',key)],[item('s','APERTO',key)]),set())

    def test_valid_sources_outside_current_horizon_do_not_expire(self):
        self.assertEqual(sources([item('a','CONFERMATO','PEC_AUDIT:future')],[item('s','SCADUTO','PEC_AUDIT:ongoing')]),set())

    def test_explicit_sql_link_replaces_appointment_alias(self):
        self.assertEqual(sources([item('a','PROGRAMMATO','PEC_AUDIT:alias')],[item('s','APERTO','PEC_AUDIT:canonical','a')],['PEC_AUDIT:canonical:deadline']),{'PEC_AUDIT:alias:deadline'})

    def test_alias_kept_when_replacement_not_materialized(self):
        self.assertEqual(sources([item('a','PROGRAMMATO','PEC_AUDIT:alias')],[item('s','APERTO','PEC_AUDIT:canonical','a')]),set())

    def test_similar_case_without_explicit_sql_link_never_merged(self):
        self.assertEqual(sources([item('a','PROGRAMMATO','PEC_AUDIT:alias')],[item('s','APERTO','PEC_AUDIT:canonical')],['PEC_AUDIT:canonical:deadline']),set())

    def test_active_materialized_key_cannot_expire(self):
        self.assertEqual(sources([item('a','ANNULLATO','PEC_AUDIT:key')],current=['PEC_AUDIT:key:deadline']),set())

    def test_non_pec_sources_are_not_included(self):
        self.assertEqual(sources([item('a','ANNULLATO','hearing:a')],[item('s','ANNULLATO','deadline:s')]),set())

if __name__=='__main__':
    unittest.main()