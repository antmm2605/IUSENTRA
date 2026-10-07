"""Migrazione su soli studi controllati; applicazione reale non eseguita."""
import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout

from pct.email_mailbox_repository import EmailMailboxRepository

tool_root = Path(os.environ.get('MAILBOX_MIGRATION_TOOLS', str(Path(__file__).resolve().parents[1] / 'scripts' / 'mailbox')))
spec = importlib.util.spec_from_file_location('candidate_mailbox_apply', tool_root / 'apply-mailbox-plans.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
planner = migration.load_planner()


class MigrationPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_root = Path(self.temp.name) / 'data'
        self.plan_dir = Path(self.temp.name) / 'plans'
        self.plan_dir.mkdir()
        self.backup = Path(self.temp.name) / 'backup'
        self.backup.mkdir()
        entries, manifest = {}, []
        self.roots = {}
        for tenant in ('controlled-a', 'controlled-b'):
            root = self.data_root / 'tenants' / tenant
            (root / 'email').mkdir(parents=True)
            (root / 'intelligence').mkdir()
            with sqlite3.connect(root / 'studio.db') as conn:
                conn.execute('CREATE TABLE moduli_json_records (modulo TEXT,record_key TEXT,payload_json TEXT)')
                for kind, module, filename in (('pec', 'email_casella', 'casella.json'), ('ordinary', 'email_ordinaria', 'ordinaria.json')):
                    record = {'id': 'one', 'cartella': 'INBOX', 'stato': 'NON_LETTA', 'letta_il': ''}
                    conn.execute('INSERT INTO moduli_json_records VALUES (?,?,?)', (module, 'one', json.dumps(record)))
                    (root / 'email' / filename).write_text(json.dumps({'one': record}))
            with sqlite3.connect(root / 'intelligence/registro_letture.db') as conn:
                conn.execute('CREATE TABLE controlled_empty (id INTEGER)')
            logical = '/data/tenants/' + tenant
            for kind, module, filename in (('pec', 'email_casella', 'casella.json'), ('ordinary', 'email_ordinaria', 'ordinaria.json')):
                plan = planner.plan(root, module, filename, tenant)
                plan.update(tenant_key=tenant, mailbox_kind=kind, tenant_root=logical)
                (self.plan_dir / (tenant + '-' + kind + '.json')).write_text(json.dumps(plan))
            prefix = hashlib.sha256(logical.encode()).hexdigest()[:16]
            for suffix, source in (('core', root / 'studio.db'), ('letture', root / 'intelligence/registro_letture.db')):
                name = prefix + '-' + suffix + '.db'
                content = source.read_bytes()
                (self.backup / name).write_bytes(content)
                manifest.append({'file': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                                 'source_of_truth': 'sqlite', 'quick_check': 'ok'})
            self.roots[tenant] = root
            entries[tenant] = {'slug': tenant, 'db_config': {'mode': 'SQLITE'}}
        self.registry = self.data_root / 'tenants.json'
        self.registry.write_text(json.dumps(entries))
        self.manifest = self.backup / 'manifest.json'
        self.manifest.write_text(json.dumps({'files': manifest}))

    def validate(self):
        roots = migration.tenant_roots(self.registry, self.data_root)
        return migration.validate_plans(self.plan_dir, roots, planner, self.data_root)

    def apply(self):
        argv = ['apply-mailbox-plans.py', '--plan-dir', str(self.plan_dir), '--registry', str(self.registry),
                '--data-root', str(self.data_root), '--backup-manifest', str(self.manifest), '--apply']
        with patch('sys.argv', argv), patch.object(migration, 'offline_writers'), redirect_stdout(io.StringIO()) as output:
            migration.main()
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def assert_no_catalog(self):
        for root in self.roots.values():
            with sqlite3.connect(root / 'studio.db') as conn:
                self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='email_mailbox_records'").fetchone())

    def test_all_plans_and_backups_are_verified_before_any_catalog_write(self):
        prepared = self.validate()
        self.assertEqual(len(prepared), 4)
        migration.verify_backup(self.manifest, prepared)
        for root in self.roots.values():
            with sqlite3.connect(root / 'studio.db') as conn:
                self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='email_mailbox_records'").fetchone())

    def test_changed_mirror_blocks_entire_plan_without_sql_write(self):
        path = self.roots['controlled-b'] / 'email/ordinaria.json'
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'copia storica'):
            self.validate()

    def test_missing_mailbox_plan_is_not_a_partial_migration(self):
        (self.plan_dir / 'controlled-b-ordinary.json').unlink()
        with self.assertRaisesRegex(ValueError, 'tutte le caselle'):
            self.validate()

    def test_already_initialized_catalog_can_resume_only_when_exactly_matching(self):
        plan, root, filename, _ = self.validate()[0]
        with sqlite3.connect(root / 'studio.db') as conn:
            repository = EmailMailboxRepository(SimpleNamespace(conn=conn), plan['tenant_key'], plan['mailbox_kind'], root / 'email' / filename)
            repository.ensure_schema()
            repository.initialize(plan['records'], source_of_truth='controlled_source_reconciliation')
            repository.export_mirror()
        self.assertEqual(sum(row[3] for row in self.validate()), 1)
        with sqlite3.connect(root / 'studio.db') as conn:
            conn.execute("UPDATE email_mailbox_records SET payload_json=?", (json.dumps({'id': 'one', 'stato': 'LETTA'}),))
        with self.assertRaisesRegex(ValueError, 'già operativo'):
            self.validate()

    def test_backup_corruption_blocks_apply(self):
        prepared = self.validate()
        name = json.loads(self.manifest.read_text())['files'][0]['file']
        snapshot = self.backup / name
        data = bytearray(snapshot.read_bytes())
        data[-1] ^= 1
        snapshot.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'Impronta'):
            migration.verify_backup(self.manifest, prepared)

    def test_running_writers_block_before_migration(self):
        for line in ('iusentra-app\tapp', 'worker\tscheduler-worker', 'worker\tocr-worker', 'iusentra-app\t'):
            with self.subTest(line=line), patch.object(migration.subprocess, 'run', return_value=SimpleNamespace(stdout=line)):
                with self.assertRaisesRegex(RuntimeError, 'processi applicativi'):
                    migration.offline_writers()

    def test_apply_all_four_mailboxes_and_resume_preserve_primary_and_audit(self):
        originals = {}
        for tenant, root in self.roots.items():
            with sqlite3.connect(root / 'studio.db') as conn:
                originals[tenant] = conn.execute('SELECT * FROM moduli_json_records ORDER BY modulo,record_key').fetchall()
        first = self.apply()
        self.assertEqual(len(first), 4)
        self.assertTrue(all(row['verified'] and not row['already_initialized'] for row in first))
        resumed = self.apply()
        self.assertTrue(all(row['verified'] and row['already_initialized'] for row in resumed))
        for tenant, root in self.roots.items():
            with sqlite3.connect(root / 'studio.db') as conn:
                self.assertEqual(conn.execute('SELECT * FROM moduli_json_records ORDER BY modulo,record_key').fetchall(), originals[tenant])
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM email_mailbox_audit').fetchone()[0], 2)
                for kind, filename in (('pec', 'casella.json'), ('ordinary', 'ordinaria.json')):
                    actual = EmailMailboxRepository(SimpleNamespace(conn=conn), tenant, kind).load(update_original=False)
                    self.assertEqual(json.loads((root / 'email' / filename).read_text()), actual)

    def test_main_rejects_corrupt_backup_before_creating_any_catalog(self):
        document = json.loads(self.manifest.read_text())
        document['files'][0]['sha256'] = '0' * 64
        self.manifest.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, 'Impronta'):
            self.apply()
        self.assert_no_catalog()

    def test_source_changed_during_backup_verification_blocks_every_write(self):
        original_verify = migration.verify_backup
        def verify_then_change(*args):
            original_verify(*args)
            path = self.roots['controlled-b'] / 'email/ordinaria.json'
            path.write_text(path.read_text() + ' ')
        with patch.object(migration, 'verify_backup', side_effect=verify_then_change):
            with self.assertRaisesRegex(ValueError, 'copia storica'):
                self.apply()
        self.assert_no_catalog()

    def test_host_planner_preserves_container_identity_and_validates_all_mailboxes(self):
        output_dir = Path(self.temp.name) / 'fresh-host-plans'
        argv = ['plan-mailbox-reconciliation.py', '--output-dir', str(output_dir), '--registry', str(self.registry),
                '--data-root', str(self.data_root)]
        with patch('sys.argv', argv), redirect_stdout(io.StringIO()):
            planner.main()
        prepared = migration.validate_plans(output_dir, self.roots, planner, self.data_root)
        self.assertEqual(len(prepared), 4)
        self.assertEqual({row[0]['tenant_root'] for row in prepared},
                         {'/data/tenants/controlled-a', '/data/tenants/controlled-b'})
        migration.verify_backup(self.manifest, prepared)
        self.assert_no_catalog()


if __name__ == '__main__':
    unittest.main()
