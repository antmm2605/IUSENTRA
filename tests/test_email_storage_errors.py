"""Contratti JSON degli errori catalogo: nessun invio o dato operativo."""
import unittest

from flask import Blueprint, Flask
from pct.email_mailbox_repository import MailboxConflict, MailboxNotInitialized
from pct.email_sql_client import MailboxMirrorError
from web.services.email_storage_errors import register_mailbox_errors


class MailboxErrorTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        blueprint = Blueprint('controlled_mail', __name__)
        register_mailbox_errors(blueprint)
        for name in ('segna_letta', 'segna_non_letta', 'elimina', 'sincronizza', 'detail', 'list'):
            def fail(error_type, label=name):
                error = {'conflict': MailboxConflict, 'unavailable': MailboxNotInitialized,
                         'mirror': MailboxMirrorError}[error_type]
                raise error('Modifica controllata: ' + label)
            blueprint.add_url_rule('/' + name + '/<error_type>', name, fail, methods=['GET', 'POST'])
        app.register_blueprint(blueprint)
        self.client = app.test_client()

    def test_conflict_requires_refresh_without_reporting_success(self):
        result = self.client.post('/segna_letta/conflict')
        self.assertEqual(result.status_code, 409)
        self.assertFalse(result.json['ok'])
        self.assertTrue(result.json['refresh_required'])

    def test_uninitialized_catalog_does_not_become_an_empty_mailbox(self):
        result = self.client.get('/list/unavailable')
        self.assertEqual(result.status_code, 503)
        self.assertFalse(result.json['ok'])
        self.assertNotIn('summary', result.json)
        self.assertEqual(result.headers['Cache-Control'], 'no-store, max-age=0')

    def test_read_commit_survives_mirror_failure_with_explicit_warning(self):
        for name in ('segna_letta', 'segna_non_letta'):
            with self.subTest(name=name):
                result = self.client.post('/' + name + '/mirror')
                self.assertEqual(result.status_code, 200)
                self.assertTrue(result.json['ok'])
                self.assertTrue(result.json['warning'])
                self.assertTrue(result.json['primary_committed'])

    def test_delete_sync_and_get_do_not_claim_whole_operation_completed(self):
        for method, name in (('post', 'elimina'), ('post', 'sincronizza'), ('get', 'detail')):
            with self.subTest(method=method, name=name):
                result = getattr(self.client, method)('/' + name + '/mirror')
                self.assertEqual(result.status_code, 503)
                self.assertFalse(result.json['ok'])
                self.assertTrue(result.json['primary_committed'])


if __name__ == '__main__':
    unittest.main()
