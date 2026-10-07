"""Guardrail dell'API di selezione, senza sessione o dato operativo."""
import ast
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask, current_app, jsonify, request
from pct.email_mailbox_repository import MailboxNotInitialized


class SelectionApiTests(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ.get('MAILBOX_CALLERS_CANDIDATE', str(Path(__file__).resolve().parents[1])))
        tree = ast.parse((root / 'web/blueprints/api_v1_react.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_email_selection_ids')
        self.can = Mock(return_value=True)
        namespace = {'jsonify': jsonify, 'request': request, 'current_app': current_app,
                     '_session_user_can': self.can, '_tenant_cfg_value': lambda key, fallback: key,
                     '_tenant_runtime_label': lambda: 'controlled-studio'}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual selection API>', 'exec'), namespace)
        app = Flask(__name__)
        app.add_url_rule('/selection', view_func=lambda: namespace['_email_selection_ids'](
            ordinary=request.args.get('ordinary') == '1'))
        self.client = app.test_client()

    def test_permission_is_checked_before_storage(self):
        self.can.return_value = False
        with patch('web.services.email_selection.select_mailbox_ids') as service:
            result = self.client.get('/selection')
        self.assertEqual(result.status_code, 403)
        service.assert_not_called()

    def test_mailbox_context_and_filter_params_reach_service_without_page_limit(self):
        for ordinary, key in ((False, 'EMAIL_CASELLA_DB'), (True, 'EMAIL_ORDINARIA_DB')):
            with self.subTest(ordinary=ordinary):
                with patch('web.services.email_selection.select_mailbox_ids', return_value={'ok': True, 'ids': ['one'], 'total': 1}) as service:
                    result = self.client.get('/selection?q=Controllata&con_allegati=1' + ('&ordinary=1' if ordinary else ''))
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json['ids'], ['one'])
                self.assertEqual(service.call_args.args[0], key)
                self.assertEqual(service.call_args.args[1]['q'], 'Controllata')
                self.assertEqual(service.call_args.kwargs, {'ordinary': ordinary, 'tenant_id': 'controlled-studio'})
                self.assertEqual(result.headers['Cache-Control'], 'no-store, max-age=0')

    def test_invalid_filter_is_explicit_and_does_not_claim_selection_success(self):
        with patch('web.services.email_selection.select_mailbox_ids', side_effect=ValueError('Selezione non valida.')):
            result = self.client.get('/selection')
        self.assertEqual(result.status_code, 400)
        self.assertFalse(result.json['ok'])

    def test_missing_primary_catalog_is_not_an_empty_selection(self):
        with patch('web.services.email_selection.select_mailbox_ids', side_effect=MailboxNotInitialized('Archivio da riallineare.')):
            result = self.client.get('/selection')
        self.assertEqual(result.status_code, 503)
        self.assertFalse(result.json['ok'])
        self.assertNotIn('ids', result.json)


if __name__ == '__main__':
    unittest.main()
