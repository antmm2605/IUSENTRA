"""Selezione filtrata su SQL controllato; nessuna accettazione UI simulata."""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_email_sql_client import AdapterChecks

candidate_root = Path(os.environ.get('MAILBOX_CALLERS_CANDIDATE', str(Path(__file__).resolve().parents[1])))
spec = importlib.util.spec_from_file_location('candidate_email_bridge', candidate_root / 'web/services/react_email_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class SelectionChecks(unittest.TestCase):
    backend = None
    setUpClass = classmethod(AdapterChecks.setUpClass.__func__)
    tearDownClass = classmethod(AdapterChecks.tearDownClass.__func__)
    setUp = AdapterChecks.setUp
    repo = AdapterChecks.repo
    manager = AdapterChecks.manager

    def selection(self, **kwargs):
        with patch.object(bridge, 'create_email_mailbox', return_value=self.manager()), \
                patch.object(bridge, '_pec_audit_summaries', return_value={}), \
                patch.object(bridge, '_pec_presidio_index', return_value={}):
            return bridge.build_react_email_payload(db_path=str(self.path), folder=kwargs.pop('folder', 'INBOX'),
                                                    selection_only=True, **kwargs)

    def populate(self):
        repo = self.repo()
        records = repo.load()
        for index in range(125):
            records[f'm-{index}'] = {'id': f'm-{index}', 'cartella': 'INBOX',
                                     'stato': 'NON_LETTA', 'oggetto': 'Filtrato' if index % 2 == 0 else 'Altro',
                                     'allegati': [{'nome': 'controllato.pdf'}] if index % 3 == 0 else []}
        records['sent'] = {'id': 'sent', 'cartella': 'INVIATI', 'stato': 'LETTA', 'oggetto': 'Filtrato'}
        repo.save(records)

    def test_selection_includes_all_pages_with_same_search_and_attachment_filter(self):
        self.populate()
        result = self.selection(query='Filtrato', con_allegati=True, limit=5, offset=10)
        self.assertEqual(result['total'], 21)
        self.assertEqual(set(result['ids']), {f'm-{index}' for index in range(0, 125, 6)})
        self.assertNotIn('sent', result['ids'])

    def test_empty_selection_is_valid_and_does_not_mutate_primary(self):
        before = self.repo().load()
        result = self.selection(query='Nessunrisultatocontrollato')
        self.assertEqual(result, {'ok': True, 'ids': [], 'total': 0})
        self.assertEqual(self.repo().load(), before)

    def test_other_folders_cannot_be_selected_for_bulk_read(self):
        for folder in ('TUTTE', 'INVIATI', 'CESTINO'):
            with self.subTest(folder=folder), self.assertRaises(ValueError):
                self.selection(folder=folder)

    def test_warning_filter_is_applied_before_selection_and_excludes_presidiated(self):
        repo = self.repo()
        records = repo.load()
        records['one']['stato_pct'] = 'WARN_CONTROLLI'
        records['two'] = {'id': 'two', 'cartella': 'INBOX', 'stato': 'NON_LETTA', 'stato_pct': 'ERRORE'}
        repo.save(records)
        with patch.object(bridge, 'create_email_mailbox', return_value=self.manager()), \
                patch.object(bridge, '_pec_audit_summaries', return_value={}), \
                patch.object(bridge, '_pec_presidio_index', return_value={'by_email_id': {'two': {'status': 'verificato'}}}):
            result = bridge.build_react_email_payload(db_path=str(self.path), folder='INBOX',
                                                      selection_only=True, solo_da_presidiare=True)
        self.assertEqual(result['ids'], ['one'])


class SQLiteSelection(SelectionChecks):
    backend = 'sqlite'


class PostgreSQLSelection(SelectionChecks):
    backend = 'postgresql'


if __name__ == '__main__':
    unittest.main()
