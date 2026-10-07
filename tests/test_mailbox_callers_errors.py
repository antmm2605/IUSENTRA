"""I chiamanti non nascondono errori del catalogo SQL durante l'allineamento."""
import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from web.services.email_storage_errors import MAILBOX_STORAGE_ERRORS


class MailboxCallerErrors(unittest.TestCase):
    def functions(self):
        root = Path(os.environ.get('MAILBOX_CALLERS_CANDIDATE', str(Path(__file__).resolve().parents[1])))
        for filename, name in (('web/services/react_email_bridge.py', '_sync_inviati_da_messaggi'),
                               ('web/blueprints/email_client.py', '_sync_inviati'),
                               ('web/blueprints/email_ordinaria.py', '_sync_inviati')):
            tree = ast.parse((root / filename).read_text(encoding='utf-8'))
            node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
            node.decorator_list = []
            namespace = {'MAILBOX_STORAGE_ERRORS': MAILBOX_STORAGE_ERRORS,
                         '_cfg_path': lambda *args: '/controlled/messaggi.json',
                         '_enum_value': lambda value: getattr(value, 'value', value)}
            module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
            exec(compile(ast.fix_missing_locations(module), filename, 'exec'), namespace)
            yield filename, namespace[name], name == '_sync_inviati_da_messaggi'

    def invoke(self, function, bridge, error=None):
        manager = Mock()
        manager.tutti.return_value = [SimpleNamespace(stato=SimpleNamespace(value='INVIATO'))]
        mailbox = Mock()
        if error is not None:
            mailbox.sincronizza_inviati.side_effect = error
        with patch('pct.messaggi.GestioneMessaggi', return_value=manager):
            function(mailbox, '/controlled/messaggi.json') if bridge else function(mailbox)
        return mailbox

    def test_storage_conflicts_and_unavailable_catalog_reach_json_handlers(self):
        for filename, function, bridge in self.functions():
            for error_type in MAILBOX_STORAGE_ERRORS:
                with self.subTest(filename=filename, error=error_type.__name__):
                    with self.assertRaises(error_type):
                        self.invoke(function, bridge, error_type('controlled storage error'))

    def test_other_legacy_errors_keep_existing_behavior(self):
        for filename, function, bridge in self.functions():
            with self.subTest(filename=filename):
                self.invoke(function, bridge, ValueError('controlled legacy error'))

    def test_successful_alignment_uses_native_sync_once_without_transport(self):
        for filename, function, bridge in self.functions():
            with self.subTest(filename=filename):
                mailbox = self.invoke(function, bridge)
                mailbox.sincronizza_inviati.assert_called_once()
                mailbox.invia.assert_not_called()


if __name__ == '__main__':
    unittest.main()
