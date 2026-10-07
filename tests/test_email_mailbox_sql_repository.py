"""Guardrail SQL della persistenza; attivazione e prova UI ancora richieste."""
import json
import os
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from tests.test_condivisioni_sql_repository import SQLFactory
from pct.email_mailbox_repository import EmailMailboxRepository, MailboxConflict, MailboxNotInitialized


class MailboxChecks(unittest.TestCase):
    backend = None

    @classmethod
    def setUpClass(cls):
        if cls.backend is None:
            raise unittest.SkipTest('Classe base: usare SQLite o PostgreSQL.')
        cls.factory = SQLFactory(cls.backend)
        try:
            EmailMailboxRepository(cls.factory.new(), 'schema-only', 'pec').ensure_schema()
        except Exception:
            cls.factory.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.factory.close()

    def setUp(self):
        self.tenant = 'controlled-' + uuid.uuid4().hex
        self.path = Path(self.factory.temp.name) / (self.tenant + '.json')
        self.records = {
            'one': {'id': 'one', 'cartella': 'INBOX', 'stato': 'NON_LETTA', 'letta_il': '', 'auto_registrata': False},
            'two': {'id': 'two', 'cartella': 'INBOX', 'stato': 'NON_LETTA', 'letta_il': '', 'auto_registrata': False},
            'trash': {'id': 'trash', 'cartella': 'CESTINO', 'stato': 'CESTINO', 'letta_il': ''},
        }
        self.first = self.repo()
        self.first.initialize(self.records, source_of_truth=self.backend)

    def repo(self, tenant=None, kind='pec'):
        return EmailMailboxRepository(self.factory.new(), tenant or self.tenant, kind, self.path)

    def audit_count(self):
        return self.first.db.conn.execute(
            'SELECT COUNT(*) FROM email_mailbox_audit WHERE tenant_key=? AND mailbox_kind=?',
            (self.tenant, 'pec'),
        ).fetchone()[0]

    def test_bulk_read_updates_only_unread_inbox_and_is_idempotent(self):
        before_audit = self.audit_count()
        result = self.first.mark_read(['one', 'two', 'trash', 'one'], actor_key='controlled-user')
        self.assertEqual(result['selected'], 3)
        self.assertEqual(result['updated'], 2)
        current = self.repo().load()
        self.assertEqual(current['one']['stato'], 'LETTA')
        self.assertEqual(current['two']['stato'], 'LETTA')
        self.assertEqual(current['trash'], self.records['trash'])
        self.assertEqual(self.audit_count(), before_audit + 2)
        self.assertEqual(self.first.mark_read(['one', 'two'], actor_key='controlled-user')['updated'], 0)
        self.assertEqual(self.audit_count(), before_audit + 2)

    def test_missing_selection_never_partially_marks_read(self):
        before_audit = self.audit_count()
        with self.assertRaises(MailboxConflict):
            self.first.mark_read(['one', 'missing'], actor_key='controlled-user')
        self.assertEqual(self.repo().load(), self.records)
        self.assertEqual(self.audit_count(), before_audit)

    def test_concurrent_independent_fields_and_new_acquisition_are_preserved(self):
        stale = self.first.load()
        other = self.repo()
        acquired = other.load()
        acquired['one']['auto_registrata'] = True
        acquired['new'] = {'id': 'new', 'cartella': 'INBOX', 'stato': 'NON_LETTA'}
        other.save(acquired, action='controlled-acquisition')
        stale['one'].update(stato='LETTA', letta_il='2026-10-06T01:00:00+00:00')
        result = self.first.save(stale, actor_key='controlled-user', action='mark_read')
        self.assertTrue(result['one']['auto_registrata'])
        self.assertEqual(result['one']['stato'], 'LETTA')
        self.assertIn('new', result)

    def test_same_field_conflict_rolls_back_other_changes_and_audit(self):
        stale = self.first.load()
        other = self.repo()
        current = other.load()
        current['one'].update(stato='LETTA', letta_il='earlier')
        other.save(current)
        before_audit = self.audit_count()
        stale['one'].update(stato='LETTA', letta_il='stale')
        stale['two'].update(stato='LETTA', letta_il='stale')
        with self.assertRaises(MailboxConflict):
            self.first.save(stale, actor_key='controlled-user', action='mark_read')
        result = self.repo().load()
        self.assertEqual(result['one']['letta_il'], 'earlier')
        self.assertEqual(result['two']['stato'], 'NON_LETTA')
        self.assertEqual(self.audit_count(), before_audit)

    def test_tenant_and_mailbox_are_isolated_and_unknown_selection_fails(self):
        separate = self.repo(tenant=self.tenant + '-other')
        separate.initialize({'other': {'id': 'other'}}, source_of_truth=self.backend)
        ordinary = self.repo(kind='ordinary')
        ordinary.initialize({'ordinary': {'id': 'ordinary'}}, source_of_truth=self.backend)
        with self.assertRaises(MailboxConflict):
            self.first.mark_read(['other'], actor_key='controlled-user')
        self.assertEqual(set(self.first.load()), set(self.records))
        self.assertEqual(set(separate.load()), {'other'})
        self.assertEqual(set(ordinary.load()), {'ordinary'})

    def test_empty_sql_and_missing_bootstrap_never_read_stale_json(self):
        self.path.write_text(json.dumps({'stale': {'id': 'stale'}}))
        empty = self.repo(tenant=self.tenant + '-empty')
        empty.initialize({}, source_of_truth=self.backend)
        self.assertEqual(empty.load(), {})
        with self.assertRaises(RuntimeError):
            self.repo(tenant=self.tenant + '-uninitialized').load()

    def test_changed_message_cannot_be_deleted_by_stale_snapshot(self):
        stale = self.first.load()
        other = self.repo()
        current = other.load()
        current['one']['corpo_testo'] = 'Fonte controllata acquisita nel frattempo'
        other.save(current)
        del stale['one']
        with self.assertRaises(MailboxConflict):
            self.first.save(stale, action='controlled-delete')
        self.assertIn('one', self.repo().load())

    def test_mirror_is_regenerated_from_sql_and_never_imported_on_save(self):
        self.path.write_text(json.dumps({'stale': {'id': 'stale'}}))
        self.first.mark_read(['one'], actor_key='controlled-user')
        self.first.export_mirror()
        mirror = json.loads(self.path.read_text())
        self.assertEqual(mirror, self.repo().load())
        self.assertNotIn('stale', mirror)

    def test_bootstrap_cannot_replace_existing_messages(self):
        with self.assertRaises(MailboxConflict):
            self.first.initialize({}, source_of_truth=self.backend)
        self.assertEqual(self.first.load(), self.records)

    def test_overlapping_mirrors_cannot_restore_the_old_unread_state(self):
        exporting = threading.Event()
        second_started = threading.Event()
        release = threading.Event()
        failures = []
        native_replace = os.replace

        def delayed_replace(source, target):
            if threading.current_thread().name == 'old-mailbox-export':
                exporting.set()
                if not release.wait(5):
                    raise TimeoutError('Il controllo concorrente non ha rilasciato il mirror.')
            native_replace(source, target)

        def worker(mark_read=False):
            db = self.factory.new()
            raw = getattr(db, 'raw_conn', None) or db.conn
            try:
                repo = EmailMailboxRepository(db, self.tenant, 'pec', self.path)
                if mark_read:
                    second_started.set()
                    repo.mark_read(['one'], actor_key='controlled-concurrent-user')
                repo.export_mirror()
            except Exception as exc:
                failures.append(exc)
            finally:
                raw.close()
                self.factory.connections.remove(raw)

        first = threading.Thread(target=worker, name='old-mailbox-export')
        second = threading.Thread(target=worker, args=(True,), name='new-mailbox-export')
        with patch('pct.email_mailbox_repository.os.replace', side_effect=delayed_replace):
            first.start()
            try:
                self.assertTrue(exporting.wait(5))
                second.start()
                self.assertTrue(second_started.wait(5))
            finally:
                release.set()
                first.join(10)
                if second.ident is not None:
                    second.join(10)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(failures, [])
        mirror = json.loads(self.path.read_text())
        self.assertEqual(mirror, self.repo().load())
        self.assertEqual(mirror['one']['stato'], 'LETTA')

    def test_failed_mirror_preserves_file_releases_sql_lock_and_removes_temporary(self):
        self.first.export_mirror()
        before = self.path.read_bytes()
        with patch('pct.email_mailbox_repository.os.replace', side_effect=OSError('controlled failure')):
            with self.assertRaises(OSError):
                self.first.export_mirror()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('tmp*')), [])
        other = self.repo()
        self.assertEqual(other.mark_read(['one'], actor_key='controlled-user')['updated'], 1)
        other.export_mirror()
        self.assertEqual(json.loads(self.path.read_text())['one']['stato'], 'LETTA')

    def test_uninitialized_export_never_replaces_historical_file(self):
        self.path.write_text('{"historical": {"id": "historical"}}')
        before = self.path.read_bytes()
        with self.assertRaises(MailboxNotInitialized):
            self.repo(tenant=self.tenant + '-uninitialized').export_mirror()
        self.assertEqual(self.path.read_bytes(), before)

    def test_strict_bulk_rejects_wrong_folder_without_partial_reads(self):
        before = self.audit_count()
        with self.assertRaises(MailboxConflict):
            self.first.mark_read(['one', 'trash'], actor_key='controlled-user', require_inbox=True)
        self.assertEqual(self.repo().load(), self.records)
        self.assertEqual(self.audit_count(), before)

    def test_folder_change_after_selection_rolls_back_the_whole_read(self):
        native_save = self.first.save
        def move_then_save(records, **kwargs):
            other = self.repo()
            current = other.load()
            # Un cambio cartella concorrente non modifica lo stato di lettura.
            current['two']['cartella'] = 'INVIATI'
            other.save(current)
            return native_save(records, **kwargs)
        with patch.object(self.first, 'save', side_effect=move_then_save):
            with self.assertRaises(MailboxConflict):
                self.first.mark_read(['one', 'two'], actor_key='controlled-user', require_inbox=True)
        current = self.repo().load()
        self.assertEqual(current['one']['stato'], 'NON_LETTA')
        self.assertEqual(current['two']['cartella'], 'INVIATI')
        self.assertEqual(current['two']['stato'], 'NON_LETTA')

    def test_already_read_selection_is_checked_without_new_read_audit(self):
        self.first.mark_read(['one'], actor_key='controlled-user', require_inbox=True)
        before = self.audit_count()
        result = self.first.mark_read(['one'], actor_key='controlled-user', require_inbox=True)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(self.audit_count(), before)


class SQLiteMailboxChecks(MailboxChecks):
    backend = 'sqlite'


@unittest.skipUnless(os.environ.get('AUDIT_POSTGRES_PASSWORD'), 'PostgreSQL controllato non configurato: eseguire nel profilo di test SQL.')
class PostgreSQLMailboxChecks(MailboxChecks):
    backend = 'postgresql'


if __name__ == '__main__':
    unittest.main()
