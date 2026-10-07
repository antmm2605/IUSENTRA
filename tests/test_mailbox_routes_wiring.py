"""Import e registrazione delle vere route candidate; nessun dato operativo."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, g


class MailboxRoutesWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ.get('MAILBOX_CALLERS_CANDIDATE', str(Path(__file__).resolve().parents[1])))
        cls.modules = {}
        for filename, blueprint in (('api_v1_react', 'api_v1_react'), ('email_client', 'email_client'),
                                    ('email_ordinaria', 'email_ordinaria')):
            name = 'web.blueprints.mailbox_wiring_' + filename
            spec = importlib.util.spec_from_file_location(name, root / 'web/blueprints' / (filename + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(name, None)
                raise
            cls.modules[filename] = module
        cls.app = Flask(__name__)
        cls.app.config.update(TESTING=True, SECRET_KEY='controlled-test-only')
        for filename, blueprint in (('api_v1_react', 'api_v1_react'), ('email_client', 'email_client'),
                                    ('email_ordinaria', 'email_ordinaria')):
            cls.app.register_blueprint(getattr(cls.modules[filename], blueprint))

    @classmethod
    def tearDownClass(cls):
        for module in cls.modules.values():
            sys.modules.pop(module.__name__, None)

    def test_both_selection_routes_require_authentication_before_any_storage(self):
        api = self.modules['api_v1_react']
        with patch.object(api, '_api_key_valida', return_value=False), patch('web.services.email_selection.select_mailbox_ids') as storage:
            for path in ('/api/v1/ui/email/selection-ids', '/api/v1/ui/email-ordinaria/selection-ids'):
                response = self.app.test_client().get(path)
                self.assertEqual(response.status_code, 401)
                self.assertFalse(response.json['ok'])
        storage.assert_not_called()

    def test_registered_selection_routes_enforce_permissions(self):
        api = self.modules['api_v1_react']
        with self.app.test_request_context('/api/v1/ui/email/selection-ids'):
            g.utente_corrente = object()
            with patch.object(api, '_session_user_can', return_value=False), patch('web.services.email_selection.select_mailbox_ids') as storage:
                response = self.app.full_dispatch_request()
            self.assertEqual(response.status_code, 403)
            self.assertFalse(response.json['ok'])
            storage.assert_not_called()

    def test_native_mailbox_action_routes_remain_registered(self):
        routes = {(rule.rule, frozenset(rule.methods)) for rule in self.app.url_map.iter_rules()}
        paths = {path for path, methods in routes if 'POST' in methods}
        for prefix in ('/email', '/email-ordinaria'):
            for action in ('segna-letta', 'segna-non-letta', 'cestino', 'ripristina'):
                self.assertIn(prefix + '/<id_email>/' + action, paths)


if __name__ == '__main__':
    unittest.main()
