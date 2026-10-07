"""Guardrail di servizio su SQL controllato, non accettazione UI dello studio."""
import os
import unittest
from unittest.mock import patch

from tests.test_email_sql_client import AdapterChecks
from pct.email_mailbox_repository import MailboxConflict
from web.services.email_bulk_read import mark_selected_mail_read


class BulkReadChecks(unittest.TestCase):
    backend = None
    setUpClass = classmethod(AdapterChecks.setUpClass.__func__)
    tearDownClass = classmethod(AdapterChecks.tearDownClass.__func__)
    setUp = AdapterChecks.setUp
    repo = AdapterChecks.repo
    manager = AdapterChecks.manager

    def test_service_commits_selection_and_reports_already_read(self):
        manager = self.manager()
        with patch('web.services.email_bulk_read.create_email_mailbox', return_value=manager):
            result = mark_selected_mail_read(str(self.path), ['one', 'one'])
            self.assertEqual(result['updated'], ['one'])
            self.assertEqual(result['selected'], 1)
            self.assertFalse(result['warning'])
            again = mark_selected_mail_read(str(self.path), ['one'])
            self.assertEqual(again['updated'], [])
            self.assertEqual(again['skipped'], ['one'])
            self.assertIn('già letti', again['message'])

    def test_invalid_selection_never_opens_mailbox(self):
        with patch('web.services.email_bulk_read.create_email_mailbox') as factory:
            for value in (None, [], 'one', {'one': True}, [None], [1], [' '], ['x' * 201], ['one'] * 5001):
                with self.subTest(value_type=type(value).__name__):
                    with self.assertRaises(ValueError):
                        mark_selected_mail_read(str(self.path), value)
            factory.assert_not_called()

    def test_invalid_folder_does_not_partially_acknowledge_other_messages(self):
        other = self.repo()
        records = other.load()
        records['two'] = {'id': 'two', 'cartella': 'CESTINO', 'stato': 'CESTINO'}
        other.save(records)
        with patch('web.services.email_bulk_read.create_email_mailbox', return_value=self.manager()):
            with self.assertRaises(MailboxConflict):
                mark_selected_mail_read(str(self.path), ['one', 'two'])
        self.assertEqual(self.repo().load()['one']['stato'], 'NON_LETTA')

    def test_mirror_failure_remains_success_with_explicit_warning_and_real_ids(self):
        manager = self.manager()
        with patch('web.services.email_bulk_read.create_email_mailbox', return_value=manager):
            with patch.object(manager.repository, 'export_mirror', side_effect=OSError('Controlled failure')):
                result = mark_selected_mail_read(str(self.path), ['one'])
        self.assertTrue(result['ok'])
        self.assertTrue(result['warning'])
        self.assertTrue(result['primary_committed'])
        self.assertEqual(result['updated'], ['one'])
        self.assertIn('copia di scambio', result['message'])
        self.assertEqual(self.repo().load()['one']['stato'], 'LETTA')


class SQLiteBulkRead(BulkReadChecks):
    backend = 'sqlite'


@unittest.skipUnless(os.environ.get('AUDIT_POSTGRES_PASSWORD'), 'PostgreSQL controllato non configurato: eseguire nel profilo di test SQL.')
class PostgreSQLBulkRead(BulkReadChecks):
    backend = 'postgresql'


if __name__ == '__main__':
    unittest.main()
