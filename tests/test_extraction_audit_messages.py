"""Errori osservati nel fascicolo reale: isolamento SQL e impronta corrente."""
import json
import sqlite3
import sys
import unittest
from types import SimpleNamespace

from pct.document_intelligence.extraction_audit_repository import DocumentAIExtractionAuditRepository
from pct.document_intelligence.security import DocumentAIValidationError
from tests.test_condivisioni_sql_repository import SQLFactory


class Checks(unittest.TestCase):
    backend = 'sqlite'

    def setUp(self):
        self.factory = SQLFactory(self.backend)
        self.addCleanup(self.factory.close)
        self.db = self.factory.new()
        if self.backend == 'sqlite':
            self.db.conn.row_factory = sqlite3.Row
        self.db.conn.execute('CREATE TABLE fascicolo_documenti_ai_audit (id TEXT PRIMARY KEY, tenant_id TEXT, fascicolo_id TEXT, document_id TEXT, event_type TEXT, created_at TEXT, payload_json TEXT)')
        self.repo = DocumentAIExtractionAuditRepository(SimpleNamespace(_backend=self.db, _conn=lambda: self.db.conn))

    def add(self, key, *, tenant='studio', case='caso', doc='doc', date='2026-10-01T12:00:00Z', sha='current', message='Busta cifrata: occorrono gli originali.', event='document_ai.extraction.failed', raw=None):
        payload = json.dumps({'sha256': sha, 'error_message': message}) if raw is None else raw
        self.db.conn.execute('INSERT INTO fascicolo_documenti_ai_audit VALUES (?,?,?,?,?,?,?)', (key, tenant, case, doc, event, date, payload))
        self.factory.commit(self.db)

    def messages(self, hashes=None):
        return self.repo.error_messages('studio', 'caso', {'doc': 'current'} if hashes is None else hashes)

    def test_latest_failure_and_deterministic_tie(self):
        self.add('a', message='vecchio')
        self.add('b', message='corrente')
        self.add('c', event='document_ai.extraction.completed', date='2026-10-02T12:00:00Z', message='non è un errore')
        self.assertEqual(self.messages(), {'doc': 'corrente'})

    def test_tenant_case_and_selected_document_isolation(self):
        self.add('base')
        self.add('other-tenant', tenant='altro', date='2026-10-03T12:00:00Z')
        self.add('other-case', case='altro', date='2026-10-03T12:00:00Z')
        self.add('other-doc', doc='altro', date='2026-10-03T12:00:00Z')
        self.assertEqual(self.messages(), {'doc': 'Busta cifrata: occorrono gli originali.'})
        self.assertEqual(self.repo.error_messages('inesistente', 'caso', {'doc': 'current'}), {})
        self.assertEqual(self.messages({"' OR 1=1 --": 'current'}), {})

    def test_previous_imprint_is_never_shown_for_current_source(self):
        self.add('a')
        self.add('b', date='2026-10-02T12:00:00Z', sha='old', message='da non attribuire alla fonte corrente')
        self.assertEqual(self.messages(), {})

    def test_empty_selection_and_bounded_selection(self):
        self.assertEqual(self.messages({}), {})
        with self.assertRaises(DocumentAIValidationError):
            self.messages({str(index): 'hash' for index in range(13)})
        self.assertEqual(self.messages({str(index): 'hash' for index in range(12)}), {})

    def test_invalid_audit_is_explicit_and_never_reported_as_success(self):
        self.add('a', raw='not-json')
        with self.assertRaises(DocumentAIValidationError):
            self.messages()
        self.db.conn.execute('UPDATE fascicolo_documenti_ai_audit SET payload_json=?', ('[]',))
        self.factory.commit(self.db)
        with self.assertRaises(DocumentAIValidationError):
            self.messages()

    def test_blank_message_and_missing_sql(self):
        self.add('a', message='   ')
        self.assertEqual(self.messages(), {})
        with self.assertRaises(DocumentAIValidationError):
            DocumentAIExtractionAuditRepository(SimpleNamespace()).error_messages('studio', 'caso', {'doc': 'current'})


if __name__ == '__main__':
    Checks.backend = 'postgresql' if '--postgresql' in sys.argv else 'sqlite'
    sys.argv = [arg for arg in sys.argv if arg != '--postgresql']
    unittest.main(verbosity=2)
