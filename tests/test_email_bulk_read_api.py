"""Guardrail della funzione API reale, senza avviare copie dell'applicazione."""
import ast
import os
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from flask import Flask, current_app, jsonify, request
from pct.email_mailbox_repository import MailboxConflict, MailboxNotInitialized


class BulkReadApiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ.get('MAILBOX_CALLERS_CANDIDATE', str(Path(__file__).resolve().parents[1])))
        source = root / 'web/blueprints/api_v1_react.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        cls.function = next(node for node in tree.body
                            if isinstance(node, ast.FunctionDef) and node.name == '_email_bulk_action')

    def setUp(self):
        self.audit = Mock()
        self.can = Mock(return_value=True)
        self.ns = {
            'Any': Any, 'jsonify': jsonify, 'current_app': current_app,
            '_request_json_object': lambda: (request.get_json(), None),
            '_session_user_can': self.can, '_audit_event': self.audit,
            '_tenant_cfg_value': lambda key, default: '/controlled/studio/email/casella.json',
            '_json_validation_error': lambda message, fields, status: (jsonify(ok=False, message=message, fields=fields), status),
        }
        exec(compile(ast.Module(body=[self.function], type_ignores=[]), '<real-email-bulk-action>', 'exec'), self.ns)
        self.app = Flask(__name__)
        self.app.add_url_rule('/controlled', view_func=lambda: self.ns['_email_bulk_action'](
            db_key='EMAIL_CASELLA_DB', default_db_path='', resource_prefix='email'), methods=['POST'])
        self.client = self.app.test_client()

    def test_read_requires_write_permission_before_opening_storage(self):
        self.can.return_value = False
        with patch('web.services.email_bulk_read.mark_selected_mail_read') as service:
            response = self.client.post('/controlled', json={'ids': ['one'], 'action': 'read'})
        self.assertEqual(response.status_code, 403)
        service.assert_not_called()
        self.audit.assert_not_called()

    def test_invalid_id_collections_never_reach_storage(self):
        with patch('web.services.email_bulk_read.mark_selected_mail_read') as service:
            for ids in ('one', {'one': True}, [1], [None], [], [' '], ['x' * 201], ['one'] * 5001):
                response = self.client.post('/controlled', json={'ids': ids, 'action': 'read'})
                self.assertEqual(response.status_code, 400)
            service.assert_not_called()

    def test_missing_or_conflicting_primary_storage_is_explicit(self):
        for error, status in [(MailboxNotInitialized('Archivio da riallineare.'), 503),
                              (MailboxConflict('Selezione cambiata.'), 409)]:
            with patch('web.services.email_bulk_read.mark_selected_mail_read', side_effect=error):
                response = self.client.post('/controlled', json={'ids': ['one'], 'action': 'read'})
            self.assertEqual(response.status_code, status)
            self.assertFalse(response.json['ok'])
        self.audit.assert_not_called()

    def test_successful_primary_and_mirror_warning_keep_exact_result(self):
        result = {'ok': True, 'updated': ['one'], 'selected': 1, 'warning': True,
                  'primary_committed': True, 'message': 'Lettura salvata. Copia da aggiornare.'}
        with patch('web.services.email_bulk_read.mark_selected_mail_read', return_value=result) as service:
            response = self.client.post('/controlled', json={'ids': [' one ', 'one'], 'action': 'read'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, result)
        service.assert_called_once_with('/controlled/studio/email/casella.json', ['one'])
        self.audit.assert_called_once_with('email.lettura.bulk', 'email', 'bulk', '1 messaggi segnati come letti; 1 selezionati')


if __name__ == '__main__':
    unittest.main()
