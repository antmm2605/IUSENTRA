"""Guardrail sui filtri già provati nel browser; non accettazione utente."""
import unittest
from pathlib import Path
from unittest.mock import patch

from pct.email_client import EmailRicevuta
from pct.email_mailbox_repository import EmailMailboxRepository
from pct.email_sql_client import GestioneEmailSQL
from tests.test_condivisioni_sql_repository import SQLFactory
from web.services.react_email_bridge import _email_row, build_react_email_payload


class EmailCardFiltersTests(unittest.TestCase):
    def setUp(self):
        self.factory = SQLFactory('sqlite')
        self.addCleanup(self.factory.close)
        self.root = Path(self.factory.temp.name) / 'controlled-studio'
        self.path = self.root / 'email' / 'casella.json'
        records = {}
        for index in range(100):
            folder = ('INBOX', 'INVIATI', 'CESTINO', 'BOZZE')[index % 4]
            row = EmailRicevuta(
                id=f'email-{index:03}', cartella=folder,
                stato='NON_LETTA' if folder == 'INBOX' else 'LETTA',
                oggetto=f'Messaggio controllato {index}',
                message_id=f'<controlled-{index}@example.test>',
                data=f'2026-10-01T12:{index % 60:02}:00+02:00',
                stato_pct='CONSEGNATO' if index % 7 == 0 else '',
                auto_registrata=index % 3 == 0,
                allegati=[{'nome': f'allegato-{index}.pdf'}, {'nome': f'nota-{index}.txt'}] if index % 5 == 0 else [],
            )
            records[row.id] = row.to_dict()
        repository = EmailMailboxRepository(self.factory.new(), 'controlled-studio', 'pec', self.path)
        repository.ensure_schema()
        repository.initialize(records, source_of_truth='sqlite')
        factory_patch = patch('web.services.react_email_bridge.create_email_mailbox', side_effect=lambda **kwargs: GestioneEmailSQL(str(self.path), studio_db=self.factory.new(), tenant_key='controlled-studio', mailbox_kind='pec', tenant_root=self.root, actor_key='controlled-user'))
        factory_patch.start()
        self.addCleanup(factory_patch.stop)
        for name, value in [
            ('_pec_audit_summaries', {'<controlled-1@example.test>': {'id': 'audit-1', 'quality_status': 'verde'}}),
            ('_pec_audit_all_summaries', []),
            ('_pec_presidio_index', {}),
        ]:
            self.addCleanup(patch.stopall)
            patch('web.services.react_email_bridge.' + name, return_value=value).start()

    def payload(self, **kwargs):
        return build_react_email_payload(db_path=str(self.path), folder='TUTTE', limit=10, **kwargs)

    def test_all_folders_and_page_count_are_complete(self):
        first, second = self.payload(), self.payload(offset=10)
        self.assertEqual(first['summary']['filtered'], 100)
        self.assertEqual(len(first['items']), 10)
        self.assertEqual(len(second['items']), 10)
        self.assertFalse({row['id'] for row in first['items']} & {row['id'] for row in second['items']})
        self.assertEqual({row['value']: row['count'] for row in first['facets']['folders']}['TUTTE'], 100)

    def test_linked_filter_count_matches_card_across_folders(self):
        result = self.payload(solo_collegate=True)
        self.assertEqual(result['summary']['filtered'], 34)
        self.assertEqual(result['summary']['filtered'], result['summary']['autoLinked'])
        self.assertTrue(all(int(row['id'].split('-')[-1]) % 3 == 0 for row in result['items']))

    def test_linked_filter_precedes_pagination(self):
        result = self.payload(solo_collegate=True, offset=30)
        self.assertEqual(result['summary']['filtered'], 34)
        self.assertEqual(len(result['items']), 4)

    def test_pst_filter_includes_persisted_audit_without_changing_classification(self):
        result = self.payload(solo_pst=True)
        self.assertEqual(result['summary']['pst'], 16)
        self.assertEqual(result['summary']['filtered'], 16)
        all_result = build_react_email_payload(db_path=str(self.path), folder='TUTTE', limit=100, solo_pst=True)
        self.assertIn('email-001', {row['id'] for row in all_result['items']})
        original = EmailMailboxRepository(self.factory.new(), 'controlled-studio', 'pec', self.path).load()
        self.assertEqual(original['email-001']['stato_pct'], '')

    def test_attachment_card_counts_files_but_filter_counts_messages(self):
        result = self.payload(con_allegati=True)
        self.assertEqual(result['summary']['attachments'], 40)
        self.assertEqual(result['summary']['filtered'], 20)

    def test_unread_filter_matches_card_and_excludes_read_messages(self):
        result = build_react_email_payload(db_path=str(self.path), folder='INBOX', stato='NON_LETTA', limit=10)
        self.assertEqual(result['summary']['filtered'], 25)
        self.assertEqual(result['summary']['unread'], 25)
        self.assertTrue(all(row['unread'] for row in result['items']))

    def test_all_outcomes_has_explicit_empty_filter_and_real_total(self):
        result = self.payload(stato_pct='CONSEGNATO')
        self.assertEqual(result['summary']['filtered'], 15)
        self.assertEqual(result['facets']['pctStatuses'][0], {'value': '', 'label': 'Tutti gli esiti', 'count': 100})

    def test_ordinary_html_preview_removes_styles_and_decodes_accents_without_mutating_source(self):
        email = EmailRicevuta(id='html', corpo_testo='body{color:red}',
                              corpo_html='<style>body{color:red}</style><script>alert(1)</script><p>È una comunicazione &egrave; leggibile.</p>')
        original = email.to_dict()
        result = _email_row(email, include_telematic=False)
        self.assertEqual(result['preview'], 'È una comunicazione è leggibile.')
        self.assertEqual(email.to_dict(), original)

    def test_plaintext_preview_remains_available_when_html_has_no_readable_body(self):
        email = EmailRicevuta(id='plain', corpo_testo='Testo originale della comunicazione', corpo_html='<style>p{color:red}</style>')
        result = _email_row(email, include_telematic=False)
        self.assertEqual(result['preview'], 'Testo originale della comunicazione')

    def test_pec_preview_prefers_html_without_changing_source_or_classification(self):
        email = EmailRicevuta(id='pec', corpo_testo='Ricevuta di consegna certificata',
                              corpo_html='<p>Altra rappresentazione</p>', stato_pct='CONSEGNATO')
        original = email.to_dict()
        result = _email_row(email, include_telematic=True, include_provisional_audit=False)
        self.assertEqual(result['preview'], 'Altra rappresentazione')
        self.assertEqual(result['pctStatus'], 'CONSEGNATO')
        self.assertEqual(email.to_dict(), original)


if __name__ == '__main__':
    unittest.main()
