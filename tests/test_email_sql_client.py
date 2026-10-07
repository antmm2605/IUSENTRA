"""Guardrail dell'adattatore su archivi controllati SQLite/PostgreSQL."""
import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from tests.test_condivisioni_sql_repository import SQLFactory
from pct.email_client import GestioneEmailRicevute
from pct.email_mailbox_repository import EmailMailboxRepository, MailboxConflict
from pct.email_sql_client import GestioneEmailSQL, MailboxMirrorError


class AdapterChecks(unittest.TestCase):
    backend = None

    @classmethod
    def setUpClass(cls):
        if cls.backend is None:
            raise unittest.SkipTest('Classe base: usare SQLite o PostgreSQL.')
        cls.factory = SQLFactory(cls.backend)
        EmailMailboxRepository(cls.factory.new(), 'schema', 'pec').ensure_schema()

    @classmethod
    def tearDownClass(cls):
        cls.factory.close()

    def setUp(self):
        self.tenant = 'controlled-' + uuid.uuid4().hex
        self.root = Path(self.factory.temp.name) / self.tenant
        self.path = self.root / 'email' / 'casella.json'
        self.records = {'one': {'id': 'one', 'cartella': 'INBOX', 'stato': 'NON_LETTA',
                                'letta_il': '', 'future_metadata': {'version': 7}}}
        self.repo().initialize(self.records, source_of_truth=self.backend)

    def repo(self):
        return EmailMailboxRepository(self.factory.new(), self.tenant, 'pec', self.path)

    def manager(self, **kwargs):
        return GestioneEmailSQL(str(kwargs.get('path', self.path)), studio_db=self.factory.new(),
                                tenant_key=self.tenant, mailbox_kind='pec', tenant_root=self.root,
                                actor_key='controlled-user', load_catalog=kwargs.get('load_catalog', True))

    def test_read_preserves_unknown_fields_and_does_not_add_dataclass_defaults(self):
        manager = self.manager()
        manager.marca_letta('one')
        actual = self.repo().load()['one']
        self.assertEqual(set(actual), set(self.records['one']))
        self.assertEqual(actual['future_metadata'], {'version': 7})
        self.assertEqual(actual['stato'], 'LETTA')
        self.assertTrue(actual['letta_il'])
        self.assertEqual(json.loads(self.path.read_text()), self.repo().load())

    def test_native_parser_attachment_and_transport_methods_are_inherited_unchanged(self):
        for name in ('leggi_allegato', 'leggi_eml_originale', '_iter_allegati_da_eml',
                     '_salva_eml_originale', '_salva_allegato'):
            left, right = getattr(GestioneEmailSQL, name), getattr(GestioneEmailRicevute, name)
            self.assertIs(getattr(left, '__func__', left), getattr(right, '__func__', right))

    def test_concurrent_unknown_metadata_and_new_acquisition_survive_read(self):
        manager = self.manager()
        other = self.repo()
        records = other.load()
        records['one']['future_metadata'] = {'version': 8}
        records['new'] = {'id': 'new', 'cartella': 'INBOX', 'stato': 'NON_LETTA'}
        other.save(records)
        manager.marca_letta('one')
        current = self.repo().load()
        self.assertEqual(current['one']['future_metadata'], {'version': 8})
        self.assertIn('new', current)
        self.assertEqual(manager.statistiche()['non_lette'], 1)

    def test_read_conflict_is_atomic_and_never_exports_stale_mirror(self):
        manager = self.manager()
        other = self.repo()
        records = other.load()
        records['one'].update(stato='LETTA', letta_il='newer')
        other.save(records)
        with self.assertRaises(MailboxConflict):
            manager.marca_letta('one')
        self.assertEqual(self.repo().load()['one']['letta_il'], 'newer')
        self.assertFalse(self.path.exists())

    def test_mirror_failure_is_explicit_after_primary_commit(self):
        manager = self.manager()
        with patch.object(manager.repository, 'export_mirror', side_effect=OSError('controlled-failure')):
            with self.assertRaises(MailboxMirrorError) as failure:
                manager.marca_lette_multipla(['one'])
        self.assertTrue(failure.exception.primary_committed)
        self.assertEqual(self.repo().load()['one']['stato'], 'LETTA')
        self.assertEqual(manager.statistiche()['non_lette'], 0)

    def test_tenant_path_mismatch_is_blocked_before_directory_creation(self):
        alien = self.root / 'alien' / 'email' / 'casella.json'
        with self.assertRaises(ValueError):
            self.manager(path=alien)
        self.assertFalse(alien.parent.exists())

    def test_single_delete_preserves_attachment_on_sql_conflict(self):
        manager = self.manager()
        attachment = manager.attachments_dir / 'one' / 'controlled.txt'
        attachment.parent.mkdir()
        attachment.write_text('Documento controllato, nessun dato dello studio.')
        other = self.repo()
        records = other.load()
        records['one']['future_metadata'] = {'version': 8}
        other.save(records)
        with self.assertRaises(MailboxConflict):
            manager.elimina_definitivamente('one')
        self.assertTrue(attachment.is_file())
        self.assertIn('one', self.repo().load())

    def test_single_delete_uses_native_bulk_cleanup_after_primary_commit(self):
        manager = self.manager()
        attachment = manager.attachments_dir / 'one' / 'controlled.txt'
        attachment.parent.mkdir()
        attachment.write_text('Documento controllato, nessun dato dello studio.')
        manager.elimina_definitivamente('one')
        self.assertNotIn('one', self.repo().load())
        self.assertFalse(attachment.exists())

    def test_bulk_mirror_failure_exposes_committed_result(self):
        manager = self.manager()
        with patch.object(manager.repository, 'export_mirror', side_effect=OSError('Controlled failure')):
            with self.assertRaises(MailboxMirrorError) as caught:
                manager.marca_lette_multipla(['one'])
        self.assertTrue(caught.exception.primary_committed)
        self.assertEqual(caught.exception.operation_result['message_keys'], ['one'])
        self.assertEqual(self.repo().load()['one']['stato'], 'LETTA')

    def test_bulk_constructor_does_not_load_all_messages_before_selection(self):
        native_load = EmailMailboxRepository.load
        with patch.object(EmailMailboxRepository, 'load', autospec=True, side_effect=native_load) as loads:
            manager = self.manager(load_catalog=False)
            self.assertIsNone(manager._cache)
            self.assertEqual(loads.call_args_list[0].kwargs['message_keys'], [])
            manager.marca_lette_multipla(['one'])
            self.assertEqual(loads.call_args_list[1].kwargs['message_keys'], ['one'])
        self.assertEqual(self.repo().load()['one']['stato'], 'LETTA')

    def test_readonly_detail_loads_one_message_and_never_turns_into_partial_edit_cache(self):
        native_load = EmailMailboxRepository.load
        with patch.object(EmailMailboxRepository, 'load', autospec=True, side_effect=native_load) as loads:
            manager = self.manager(load_catalog=False)
            message = manager.get_readonly('one')
            self.assertEqual(message.id, 'one')
            self.assertEqual(loads.call_args_list[-1].kwargs['message_keys'], ['one'])
            self.assertFalse(loads.call_args_list[-1].kwargs['update_original'])
            self.assertIsNone(manager._cache)
            self.assertEqual(manager.repository.original, {})
            self.assertIsNone(manager.get_readonly('missing'))
        message.stato = 'LETTA'
        self.assertEqual(self.repo().load()['one']['stato'], 'NON_LETTA')


class SQLiteAdapter(AdapterChecks):
    backend = 'sqlite'


@unittest.skipUnless(os.environ.get('AUDIT_POSTGRES_PASSWORD'), 'PostgreSQL controllato non configurato: eseguire nel profilo di test SQL.')
class PostgreSQLAdapter(AdapterChecks):
    backend = 'postgresql'


if __name__ == '__main__':
    unittest.main()
