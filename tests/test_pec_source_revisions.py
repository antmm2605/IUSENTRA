"""Revision counters cover inserts, links, tenant moves and deletion."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.migrate_pec_source_revisions import migrate, revision_statements


class PecSourceRevisionTests(unittest.TestCase):
    def test_revision_tracks_changes_without_content_scans(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE pec_messages(id TEXT PRIMARY KEY, tenant_id TEXT, linked_fascicolo_id TEXT, ingested_at TEXT, subject TEXT)')
        for statement in revision_statements():
            conn.execute(statement)
        def revisions():
            return {row[0]: (row[1], row[2]) for row in conn.execute('SELECT tenant_id,messages_revision,initialized FROM pec_source_revisions')}
        conn.execute("INSERT INTO pec_messages VALUES ('1','a','','2026-09-21','A')")
        self.assertEqual(revisions(), {'a': (1, 1)})
        conn.execute("UPDATE pec_messages SET subject='B'")
        self.assertEqual(revisions(), {'a': (1, 1)})
        conn.execute("UPDATE pec_messages SET linked_fascicolo_id='case-a'")
        self.assertEqual(revisions(), {'a': (2, 1)})
        conn.execute("UPDATE pec_messages SET tenant_id='b'")
        self.assertEqual(revisions(), {'a': (3, 1), 'b': (1, 1)})
        conn.execute("DELETE FROM pec_messages")
        self.assertEqual(revisions(), {'a': (3, 1), 'b': (2, 1)})
        conn.close()

    def test_migration_dry_run_backup_and_partial_index(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'pec.sqlite'
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE pec_messages(id TEXT PRIMARY KEY, tenant_id TEXT, linked_fascicolo_id TEXT, ingested_at TEXT)')
                conn.execute("INSERT INTO pec_messages VALUES ('1','a','','2026-09-21')")
            conn.close()
            report = migrate(db, apply=False, backup_dir=None)
            self.assertFalse(report['applied'])
            with sqlite3.connect(db) as conn:
                self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='pec_source_revisions'").fetchone())
            conn.close()
            report = migrate(db, apply=True, backup_dir=Path(directory)/'backups')
            self.assertTrue(report['applied'])
            self.assertTrue(Path(report['backup']).is_file())
            self.assertTrue(any('idx_pec_messages_unlinked_ingested' in line for line in report['query_plan_after']))
            self.assertEqual(report['revisions'], [['a',1,1]])
            with sqlite3.connect(report['backup']) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM pec_messages').fetchone()[0],1)
                self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='pec_source_revisions'").fetchone())
            conn.close()


if __name__ == '__main__':
    unittest.main()
