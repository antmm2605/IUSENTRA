"""API reale e StudioDB nativo su studio controllato, senza dato operativo."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, g
from pct.storage import StudioDB
from pct.tenant import StudioLegale
from web.services.email_storage_runtime import create_email_mailbox


class NativeMailboxFlow(unittest.TestCase):
    def test_pec_read_response_confirms_json_without_changing_legacy_redirect(self):
        from web.blueprints.email_client import _redirect_email_next

        app = Flask(__name__)
        app.add_url_rule('/email/', endpoint='email_client.casella', view_func=lambda: '')
        for headers in ({'Accept': 'application/json'}, {'X-Requested-With': 'XMLHttpRequest'}):
            with app.test_request_context('/email/controlled-id/segna-letta', method='POST', headers=headers):
                result = _redirect_email_next('INBOX')
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json, {'ok': True, 'messaggio': 'Operazione eseguita.', 'cartella': 'INBOX'})
        with app.test_request_context('/email/controlled-id/segna-letta', method='POST'):
            result = _redirect_email_next('INBOX')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.location, '/email/?cartella=INBOX')

    def test_all_filtered_pages_are_read_and_counts_reload_from_native_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            tenant = StudioLegale(slug='controlled-native-mailbox', db_config={'mode': 'SQLITE'})
            root = base / 'tenants' / tenant.slug
            root.mkdir(parents=True)
            db_path = str(root / 'studio.db')
            db = StudioDB.get(db_path)
            self.addCleanup(StudioDB.invalidate, db_path)
            path = root / 'email/ordinaria.json'
            registry = base / 'tenants.json'
            registry.write_text(json.dumps({tenant.slug: tenant.to_dict()}))
            (root / 'messaggi').mkdir()
            (root / 'messaggi/storico.json').write_text('[]')
            app = Flask(__name__)
            app.config.update(TESTING=True, SECRET_KEY='controlled-test-only', MULTI_TENANT=True,
                              TENANTS_REGISTRY=str(registry))

            @app.before_request
            def context():
                g.tenant = tenant
                g.utente_corrente = SimpleNamespace(id='controlled-lawyer', ha_permesso=lambda permission: True)
                g.data_paths = {'EMAIL_ORDINARIA_DB': str(path), 'MESSAGGI_DB': str(root / 'messaggi/storico.json')}

            with app.test_request_context('/'):
                context()
                mailbox = create_email_mailbox(path)
                records = {str(index): {'id': str(index), 'cartella': 'INBOX', 'stato': 'NON_LETTA',
                                       'oggetto': 'Comunicazione controllata', 'mittente': 'casella@example.test',
                                       'corpo_testo': ('Testo controllato. ' * 50) + 'prova',
                                       'data': '2026-10-05T12:00:00+00:00'} for index in range(81)}
                records['already-read'] = {**records['0'], 'id': 'already-read', 'stato': 'LETTA'}
                records['other-folder'] = {**records['0'], 'id': 'other-folder', 'cartella': 'INVIATI', 'stato': 'LETTA'}
                mailbox.repository.load()
                mailbox.repository.save(records, actor_key='controlled-import')
                mailbox.repository.export_mirror()

            source_root = Path(os.environ.get('MAILBOX_CALLERS_CANDIDATE', str(Path(__file__).resolve().parents[1])))
            name = 'web.blueprints.native_mailbox_flow_api'
            spec = importlib.util.spec_from_file_location(name, source_root / 'web/blueprints/api_v1_react.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            self.addCleanup(sys.modules.pop, name, None)
            spec.loader.exec_module(module)
            app.register_blueprint(module.api_v1_react)
            client = app.test_client()
            query = '?q=prova&stato=NON_LETTA'
            before = client.get('/api/v1/ui/email-ordinaria' + query + '&limit=80')
            self.assertEqual(before.status_code, 200)
            self.assertEqual(len(before.json['items']), 80)
            self.assertEqual(before.json['summary']['filtered'], 81)
            self.assertTrue(all('prova' not in row['preview'].lower() for row in before.json['items']))
            selection = client.get('/api/v1/ui/email-ordinaria/selection-ids' + query)
            self.assertEqual(selection.status_code, 200)
            self.assertEqual(len(selection.json['ids']), 81)
            self.assertNotIn('already-read', selection.json['ids'])
            self.assertNotIn('other-folder', selection.json['ids'])
            self.assertTrue({row['id'] for row in before.json['items']} <= set(selection.json['ids']))
            with patch.object(module, '_audit_event'):
                saved = client.post('/api/v1/ui/email-ordinaria/bulk-action',
                                    json={'action': 'read', 'ids': selection.json['ids']})
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json['ok'])
            self.assertEqual(len(saved.json['updated']), 81)
            after = client.get('/api/v1/ui/email-ordinaria' + query)
            self.assertEqual(after.status_code, 200)
            self.assertEqual(after.json['items'], [])
            self.assertEqual(after.json['summary']['filtered'], 0)
            self.assertTrue(all(record['stato'] == 'LETTA' for record in json.loads(path.read_text()).values()))
            audit = db.conn.execute("SELECT COUNT(*) FROM email_mailbox_audit WHERE action='mark_read' AND actor_key=?",
                                    ('controlled-lawyer',)).fetchone()[0]
            self.assertEqual(audit, 81)
            StudioDB.invalidate(db_path)


if __name__ == '__main__':
    unittest.main()
