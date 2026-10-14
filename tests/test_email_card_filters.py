"""Guardrail sui filtri già provati nel browser; non accettazione utente."""
import unittest
from pathlib import Path
from unittest.mock import patch

from pct.email_client import EmailRicevuta
from pct.email_mailbox_repository import EmailMailboxRepository
from pct.email_sql_client import GestioneEmailSQL
from tests.test_condivisioni_sql_repository import SQLFactory
from web.services.react_email_bridge import _email_row, build_react_email_payload


class PecMatterAuditTests(unittest.TestCase):
    def test_native_register_paginates_all_linked_messages_and_isolates_tenants(self):
        import hashlib
        import tempfile
        from pct.pec_pipeline import PecAuditRepository
        from web.services.react_email_bridge import _pec_audit_all_summaries

        with tempfile.TemporaryDirectory() as directory:
            mailbox = Path(directory) / 'email' / 'casella.json'
            repo = PecAuditRepository(mailbox.parent / 'pec_audit.sqlite', tenant_id='studio-a')
            fixtures = [(f'controlled-{index:04}', 'studio-a', 'case-a') for index in range(201)]
            fixtures += [('other-matter', 'studio-a', 'case-b'), ('other-tenant', 'studio-b', 'case-a')]
            with repo.connect() as conn:
                conn.executemany('''INSERT INTO pec_messages
                    (id, tenant_id, account_email, folder, mime_sha256, mime_size, original_mime,
                     received_at, ingested_at, linked_fascicolo_id)
                    VALUES (?, ?, 'controlled@example.test', 'CESTINO', ?, 1, ?, ?, ?, ?)''',
                    [(key, tenant, hashlib.sha256(key.encode()).hexdigest(), b'x',
                      '2026-10-01T10:00:00+02:00', '2026-10-01T10:00:00+02:00', matter)
                     for key, tenant, matter in fixtures])
            rows = _pec_audit_all_summaries(str(mailbox), tenant_id='studio-a',
                                             fascicolo_id='case-a', include_details=False)
            self.assertEqual(len(rows), 201)
            self.assertEqual(len({row['id'] for row in rows}), 201)
            self.assertTrue(all(row['folder'] == 'CESTINO' for row in rows))
            self.assertFalse({'other-matter', 'other-tenant'} & {row['id'] for row in rows})

            with repo.connect() as conn:
                conn.execute('PRAGMA journal_mode=WAL')
            original = PecAuditRepository.list_messages
            inserted = False

            def concurrent_page(repository, **kwargs):
                nonlocal inserted
                result = original(repository, **kwargs)
                if kwargs.get('fascicolo_id') == 'case-a' and not inserted:
                    inserted = True
                    with repo.connect() as writer:
                        writer.execute('''INSERT INTO pec_messages
                            (id,tenant_id,account_email,folder,mime_sha256,mime_size,original_mime,
                             received_at,ingested_at,linked_fascicolo_id)
                            VALUES ('zz-new','studio-a','controlled@example.test','INBOX',?,1,?, ?,?, 'case-a')''',
                            (hashlib.sha256(b'new').hexdigest(), b'n', '2026-10-01T10:00:00+02:00',
                             '2026-10-01T10:00:00+02:00'))
                return result

            with patch.object(PecAuditRepository, 'list_messages', concurrent_page):
                snapshot_rows = _pec_audit_all_summaries(str(mailbox), tenant_id='studio-a',
                                                        fascicolo_id='case-a', include_details=False)
            self.assertEqual(len(snapshot_rows), 201)
            self.assertEqual(len({row['id'] for row in snapshot_rows}), 201)
            self.assertNotIn('zz-new', {row['id'] for row in snapshot_rows})
            refreshed = _pec_audit_all_summaries(str(mailbox), tenant_id='studio-a',
                                               fascicolo_id='case-a', include_details=False)
            self.assertEqual(len(refreshed), 202)

    def test_matter_register_error_is_not_an_empty_mailbox(self):
        import sqlite3
        import tempfile
        from web.services.react_email_bridge import _pec_audit_all_summaries

        with tempfile.TemporaryDirectory() as directory:
            mailbox = Path(directory) / 'casella.json'
            (mailbox.parent / 'pec_audit.sqlite').write_bytes(b'controlled-corrupt-database')
            with self.assertRaises(sqlite3.DatabaseError):
                _pec_audit_all_summaries(str(mailbox), fascicolo_id='case-a')


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

    def test_matter_uses_persisted_link_before_pagination(self):
        summaries = {f'<controlled-{index}@example.test>': {
            'id': f'audit-{index}', 'linked_fascicolo_id': 'case-a', 'quality_status': 'verde',
        } for index in (0, 1, 2, 4, 5, 6)}
        summaries['<controlled-8@example.test>'] = {'id': 'other', 'linked_fascicolo_id': 'case-b'}
        rows = [dict(value, message_id_header=header) for header, value in summaries.items()]
        rows.append(dict(rows[0], id='older-audit', quality_status='rosso'))
        with patch('web.services.react_email_bridge._pec_audit_all_summaries', return_value=rows), \
                patch('web.services.react_email_bridge._pec_audit_summaries') as bulk_lookup:
            result = self.payload(fascicolo_id='case-a', offset=4)
            self.assertEqual(result['summary']['filtered'], 6)
            self.assertEqual(len(result['items']), 2)
            self.assertEqual(result['summary']['inbox'], 2)
            self.assertEqual(result['summary']['sent'], 2)
            self.assertEqual(result['summary']['trash'], 2)
            self.assertNotIn('email-008', {row['id'] for row in result['items']})
            first_page = self.payload(fascicolo_id='case-a')
            first_item = next(row for row in first_page['items'] if row['id'] == 'email-000')
            self.assertEqual(first_item['pecAudit']['qualityStatus'], 'verde')
            bulk_lookup.assert_not_called()

    def test_audit_only_messages_preserve_folder_and_counts(self):
        rows = [{'id': folder, 'folder': folder, 'linked_fascicolo_id': 'case-a'}
                for folder in ('INBOX', 'INVIATI', 'CESTINO')]
        rows.append({'id': 'other', 'folder': 'INBOX', 'linked_fascicolo_id': 'case-b'})
        with patch('web.services.react_email_bridge._pec_audit_summaries', return_value={}), \
                patch('web.services.react_email_bridge._pec_audit_all_summaries', return_value=rows):
            for folder in ('TUTTE', 'INBOX', 'INVIATI', 'CESTINO'):
                result = build_react_email_payload(db_path=str(self.path), fascicolo_id='case-a', folder=folder)
                self.assertEqual(result['summary']['total'], 3)
                self.assertEqual(result['summary']['inbox'], 1)
                self.assertEqual(result['summary']['sent'], 1)
                self.assertEqual(result['summary']['trash'], 1)
                self.assertEqual(result['summary']['filtered'], 3 if folder == 'TUTTE' else 1)
                if folder != 'TUTTE':
                    self.assertEqual(result['items'][0]['folder'], folder)

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
