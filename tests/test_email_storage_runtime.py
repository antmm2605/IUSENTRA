"""Guardrail della scelta del catalogo: studio, worker e nessun fallback SQL."""
import json
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, g
from tests.test_condivisioni_sql_repository import SQLFactory
from pct.email_client import GestioneEmailRicevute
from pct.email_mailbox_repository import EmailMailboxRepository
from pct.email_sql_client import GestioneEmailSQL
from pct.tenant import StudioLegale
from web.services.email_storage_runtime import create_email_mailbox


class FactoryChecks(unittest.TestCase):
    def setUp(self):
        self.factory = SQLFactory('sqlite')
        self.addCleanup(self.factory.close)
        self.tenant = StudioLegale(slug='controlled-' + uuid.uuid4().hex, db_config={'mode': 'SQLITE'})
        self.registry = Path(self.factory.temp.name) / 'tenants.json'
        self.root = self.registry.parent / 'tenants' / self.tenant.slug
        self.root.mkdir(parents=True)
        (self.root / 'studio.db').touch()
        self.path = self.root / 'email' / 'casella.json'
        self.registry.write_text(json.dumps({self.tenant.slug: self.tenant.to_dict()}))
        self.db = self.factory.new()
        repo = EmailMailboxRepository(self.db, self.tenant.slug, 'pec', self.path)
        repo.ensure_schema()
        repo.initialize({'one': {'id': 'one', 'cartella': 'INBOX', 'stato': 'NON_LETTA'}}, source_of_truth='sqlite')
        self.app = Flask(__name__)
        self.app.config.update(MULTI_TENANT=True, TENANTS_REGISTRY=str(self.registry))

    def test_request_uses_current_studio_and_user_for_primary_audit(self):
        with self.app.test_request_context('/email'):
            g.tenant = self.tenant
            g.utente_corrente = SimpleNamespace(id='controlled-user')
            with patch('web.services.email_storage_runtime.StudioDB.get', return_value=self.db):
                manager = create_email_mailbox(self.path)
            self.assertIsInstance(manager, GestioneEmailSQL)
            manager.marca_lette_multipla(['one'])
        actor = self.db.conn.execute("SELECT actor_key FROM email_mailbox_audit WHERE action='mark_read'").fetchone()[0]
        self.assertEqual(actor, 'controlled-user')

    def test_worker_resolves_studio_config_from_registered_canonical_path(self):
        with self.app.app_context():
            with patch('web.services.email_storage_runtime.StudioDB.get', return_value=self.db) as backend:
                manager = create_email_mailbox(self.path, actor_key='controlled-worker')
        self.assertEqual(manager.repository.tenant, self.tenant.slug)
        self.assertEqual(manager.actor_key, 'controlled-worker')
        backend.assert_called_once_with(str(self.root / 'studio.db'))

    def test_cross_studio_request_cannot_select_another_registered_path(self):
        with self.app.test_request_context('/email'):
            g.tenant = self.tenant
            with self.assertRaises(RuntimeError):
                create_email_mailbox(self.registry.parent / 'tenants' / 'other' / 'email' / 'casella.json')

    def test_unregistered_worker_path_is_blocked_without_registry_recovery(self):
        before = self.registry.read_bytes()
        other = self.registry.parent / 'tenants' / 'other' / 'email' / 'casella.json'
        with self.app.app_context():
            with self.assertRaises(RuntimeError):
                create_email_mailbox(other)
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertFalse(other.parent.exists())

    def test_sql_missing_database_never_creates_it_from_json(self):
        (self.root / 'studio.db').unlink()
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({'stale': {'id': 'stale'}}))
        with self.app.app_context():
            with self.assertRaises(RuntimeError):
                create_email_mailbox(self.path)
        self.assertFalse((self.root / 'studio.db').exists())

    def test_sql_missing_bootstrap_never_reads_ordinary_historical_copy(self):
        ordinary = self.path.with_name('ordinaria.json')
        ordinary.parent.mkdir()
        ordinary.write_text(json.dumps({'stale': {'id': 'stale'}}))
        with self.app.app_context():
            with patch('web.services.email_storage_runtime.StudioDB.get', return_value=self.db):
                with self.assertRaises(RuntimeError):
                    create_email_mailbox(ordinary)
        self.assertEqual(json.loads(ordinary.read_text()), {'stale': {'id': 'stale'}})

    def test_unavailable_postgresql_never_falls_back_to_sqlite_or_json(self):
        profile = SimpleNamespace(effective_mode='POSTGRESQL', selected_mode='POSTGRESQL',
                                  studio_db_path=str(self.root / 'studio.db'), uses_sqlite=False)
        with self.app.app_context():
            with patch('web.services.email_storage_runtime.resolve_storage_runtime', return_value=profile), \
                 patch('web.services.email_storage_runtime.build_core_storage_backend', return_value=None), \
                 patch('web.services.email_storage_runtime.StudioDB.get') as sqlite:
                with self.assertRaises(RuntimeError):
                    create_email_mailbox(self.path)
                sqlite.assert_not_called()

    def test_explicit_single_studio_json_preserves_native_compatibility(self):
        self.app.config.update(MULTI_TENANT=False, STORAGE_MODE_DEFAULT='JSON')
        custom = self.registry.parent / 'controlled-json' / 'historical-mail.json'
        with self.app.app_context():
            manager = create_email_mailbox(custom)
        self.assertIs(type(manager), GestioneEmailRicevute)

    def test_new_empty_sql_mailbox_initializes_without_json_import(self):
        ordinary = self.path.with_name('ordinaria.json')
        ordinary.parent.mkdir()
        ordinary.write_text('{}')
        with self.app.app_context():
            with patch('web.services.email_storage_runtime.StudioDB.get', return_value=self.db):
                manager = create_email_mailbox(ordinary)
        self.assertIsInstance(manager, GestioneEmailSQL)
        self.assertEqual(manager.statistiche()['totale'], 0)
        self.assertEqual(manager.repository.load(), {})
        self.assertEqual(json.loads(ordinary.read_text()), {})

    def test_nonempty_primary_core_catalog_requires_governed_migration(self):
        ordinary = self.path.with_name('ordinaria.json')
        ordinary.parent.mkdir()
        ordinary.write_text('{}')
        primary = {'id': 'historical-primary', 'cartella': 'INBOX', 'stato': 'NON_LETTA'}
        self.db.conn.execute('INSERT INTO moduli_json_records VALUES (?,?,?)',
                             ('email_ordinaria', primary['id'], json.dumps(primary)))
        self.factory.commit(self.db)
        with self.app.app_context():
            with patch('web.services.email_storage_runtime.StudioDB.get', return_value=self.db):
                with self.assertRaises(RuntimeError):
                    create_email_mailbox(ordinary)
        marker = self.db.conn.execute('SELECT 1 FROM email_mailbox_bootstrap WHERE mailbox_kind=?',
                                       ('ordinary',)).fetchone()
        self.assertIsNone(marker)

    def test_historical_empty_ordinary_seed_initializes_only_empty_sql(self):
        ordinary = self.path.with_name('ordinaria.json')
        ordinary.parent.mkdir()
        ordinary.write_text('[]')
        with self.app.app_context():
            with patch('web.services.email_storage_runtime.StudioDB.get', return_value=self.db):
                manager = create_email_mailbox(ordinary)
        self.assertIsInstance(manager, GestioneEmailSQL)
        self.assertEqual(manager.repository.load(), {})
        self.assertEqual(manager.statistiche()['totale'], 0)
        self.assertEqual(json.loads(ordinary.read_text()), [])

    def test_populated_list_seed_is_not_imported_or_discarded(self):
        ordinary = self.path.with_name('ordinaria.json')
        ordinary.parent.mkdir()
        ordinary.write_text('[{"id":"historical"}]')
        before = ordinary.read_bytes()
        with self.app.app_context():
            with patch('web.services.email_storage_runtime.StudioDB.get', return_value=self.db):
                with self.assertRaises(RuntimeError):
                    create_email_mailbox(ordinary)
        self.assertEqual(ordinary.read_bytes(), before)
        self.assertIsNone(self.db.conn.execute('SELECT 1 FROM email_mailbox_bootstrap WHERE mailbox_kind=?',
                                              ('ordinary',)).fetchone())


if __name__ == '__main__':
    unittest.main()


def test_initialized_empty_sql_mailbox_is_not_unseeded(tmp_path):
    from tests.mailbox_test_support import sql_mailbox
    from web.services.storage_runtime import _sqlite_runtime_is_unseeded

    path = tmp_path / "email" / "casella.json"
    manager = sql_mailbox(path)
    assert manager.statistiche()["totale"] == 0
    assert not _sqlite_runtime_is_unseeded(tmp_path / "studio.db", tmp_path / "clienti.json")
