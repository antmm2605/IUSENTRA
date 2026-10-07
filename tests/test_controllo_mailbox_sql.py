"""Guardrail di Controllo Studio su caselle SQL controllate, senza dato operativo."""
import ast
import importlib.util
import os
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_email_sql_client import AdapterChecks
from pct.email_client import GestioneEmailRicevute
from pct.email_mailbox_repository import MailboxConflict


CANDIDATE = Path(os.environ.get('MAILBOX_CALLERS_CANDIDATE', str(Path(__file__).resolve().parents[1])))


def load_candidate(name, relative):
    spec = importlib.util.spec_from_file_location(name, CANDIDATE / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


letture = load_candidate('candidate_controllo_letture', 'web/services/controllo_studio_letture.py')
runtime = load_candidate('candidate_controllo_runtime', 'web/services/controllo_studio_runtime.py')


class ControlloMailboxChecks(unittest.TestCase):
    backend = None
    setUpClass = classmethod(AdapterChecks.setUpClass.__func__)
    tearDownClass = classmethod(AdapterChecks.tearDownClass.__func__)
    setUp = AdapterChecks.setUp
    repo = AdapterChecks.repo
    manager = AdapterChecks.manager

    def test_bulk_read_uses_primary_and_never_writes_separate_registry(self):
        manager = self.manager()
        with patch('web.helpers.get_email_pec', return_value=manager), patch.object(letture, 'repository') as old:
            selected, message = letture.marca_pec(['one', 'one'])
            old.assert_not_called()
        self.assertEqual(selected, ['one'])
        self.assertIn('1 comunicazione', message)
        self.assertEqual(self.repo().load()['one']['stato'], 'LETTA')

    def test_bulk_read_rejects_missing_selection_without_partial_write(self):
        with patch('web.helpers.get_email_pec', return_value=self.manager()):
            with self.assertRaises(MailboxConflict):
                letture.marca_pec(['one', 'missing'])
        self.assertEqual(self.repo().load()['one']['stato'], 'NON_LETTA')

    def test_mirror_failure_reports_saved_primary_with_explicit_warning(self):
        manager = self.manager()
        with patch('web.helpers.get_email_pec', return_value=manager):
            with patch.object(manager.repository, 'export_mirror', side_effect=OSError('controlled failure')):
                selected, message = letture.marca_pec(['one'])
        self.assertEqual(selected, ['one'])
        self.assertIn('copia di scambio', message)
        self.assertEqual(self.repo().load()['one']['stato'], 'LETTA')

    def test_mark_unread_reappears_despite_historical_shadow_read(self):
        manager = self.manager()
        manager.marca_letta('one')
        manager.marca_non_letta('one')
        helpers = {'email_pec': lambda: self.manager(),
                   'messaggi': lambda: SimpleNamespace(tutti=lambda: [])}
        with patch('web.services.controllo_studio_letture.repository') as shadow:
            shadow.return_value.pec_lette.return_value = {'one'}
            result = runtime.costruisci(helpers, presidi_notifiche=lambda: [],
                                       oggi=date(2026, 10, 6), puo=lambda p: p == 'messaggi.leggi')
            shadow.assert_not_called()
        self.assertEqual([v['id'] for v in result['voci']], ['pec-one'])
        self.assertEqual(result['fonti_non_disponibili'], [])

    def test_helper_keeps_sql_primary_without_historical_shadow_overlay(self):
        source = ast.parse((CANDIDATE / 'web/helpers.py').read_text(encoding='utf-8'))
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'get_email_pec')
        function.returns = None
        manager = self.manager()
        namespace = {'tenant_data_path': lambda *a, **kw: str(self.path),
                     'create_email_mailbox': lambda **kw: manager,
                     'GestioneEmailRicevute': GestioneEmailRicevute}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual helper candidate>', 'exec'), namespace)
        with patch('web.services.controllo_studio_casella.CasellaConLettureSQL') as shadow:
            self.assertIs(namespace['get_email_pec'](), manager)
            shadow.assert_not_called()


class SQLiteControlloMailbox(ControlloMailboxChecks):
    backend = 'sqlite'


class PostgreSQLControlloMailbox(ControlloMailboxChecks):
    backend = 'postgresql'


if __name__ == '__main__':
    unittest.main()
