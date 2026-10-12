"""Guardrail della migrazione SQL Timesheet, senza mirror JSON."""
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch
from pathlib import Path
from pct.storage import StudioDB
from pct.timesheet import GestioneTimesheet

from tools import migrate_timesheet_canonical_sql as migration

class CanonicalMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'timesheet').mkdir()
        self.source=StudioDB(str(self.root/'timesheet'/'studio.db'))
        self.target=StudioDB(str(self.root/'studio.db'))
        self.old=GestioneTimesheet(str(self.root/'timesheet'/'entries.json'),studio_db=self.source)
        self.core=GestioneTimesheet(str(self.root/'core.json'),studio_db=self.target)
    def tearDown(self):
        self.source.chiudi(); self.target.chiudi(); self.temp.cleanup()
    def test_merge_preserves_existing_rows_and_original_ids(self):
        old=self.old.crea(descrizione='Attività interna originale',minuti=1,fatturabile=False)
        current=self.core.crea(descrizione='Attività canonica esistente',minuti=2,fatturabile=False)
        preview=migration.migrate(self.root)
        self.assertFalse(preview['applied'])
        self.assertEqual(self.core.tutte()[0].id,current.id)
        report=migration.migrate(self.root,self.root/'backup')
        self.assertEqual(report['inserted'],1)
        loaded=GestioneTimesheet(str(self.root/'unused.json'),studio_db=self.target)
        self.assertEqual({row.id for row in loaded.tutte()},{old.id,current.id})
        self.assertEqual(loaded.get(old.id).descrizione,old.descrizione)
        self.assertTrue((self.root/'backup'/'studio-prima.sqlite').exists())
        again=migration.migrate(self.root,self.root/'backup-again')
        self.assertEqual(again['inserted'],0)
    def test_conflicting_ids_never_overwrite_target(self):
        old=self.old.crea(descrizione='Origine',minuti=1,fatturabile=False)
        migration.migrate(self.root,self.root/'first')
        core=GestioneTimesheet(str(self.root/'unused.json'),studio_db=self.target)
        core.aggiorna(old.id,descrizione='Modifica canonica successiva')
        with self.assertRaisesRegex(ValueError,'Collisione'):
            migration.migrate(self.root,self.root/'second')
        loaded=GestioneTimesheet(str(self.root/'unused.json'),studio_db=self.target)
        self.assertEqual(loaded.get(old.id).descrizione,'Modifica canonica successiva')
        self.assertEqual(len(loaded.tutte()),1)

    def test_backup_failure_prevents_writes_and_preserves_source(self):
        old = self.old.crea(descrizione='Fonte da preservare', minuti=3, fatturabile=False)
        with patch.object(migration, '_backup_sqlite', side_effect=OSError('Spazio insufficiente')):
            with self.assertRaisesRegex(OSError, 'Spazio insufficiente'):
                migration.migrate(self.root, self.root/'backup-fallito')
        self.assertEqual(self.target.conn.execute('SELECT count(*) FROM timesheet_entries').fetchone()[0], 0)
        self.assertEqual(self.source.conn.execute('SELECT id FROM timesheet_entries').fetchone()[0], old.id)
        self.assertEqual(self.target.conn.execute("SELECT count(*) FROM audit_log WHERE azione='timesheet.adozione_sql'").fetchone()[0], 0)

    def test_backup_is_coherent_and_replay_does_not_repeat_audit(self):
        import json
        import sqlite3
        old = self.old.crea(descrizione='Voce storica', minuti=3, fatturabile=False)
        migration.migrate(self.root, self.root/'backup-verificato')
        manifest = json.loads((self.root/'backup-verificato'/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual([item['quick_check'] for item in manifest['backups']], ['ok', 'ok'])
        with closing(sqlite3.connect(self.root/'backup-verificato'/'studio-prima.sqlite')) as before:
            self.assertEqual(before.execute('SELECT count(*) FROM timesheet_entries').fetchone()[0], 0)
        migration.migrate(self.root, self.root/'backup-replay')
        self.assertEqual(self.target.conn.execute('SELECT id FROM timesheet_entries').fetchone()[0], old.id)
        self.assertEqual(self.target.conn.execute("SELECT count(*) FROM audit_log WHERE azione='timesheet.adozione_sql'").fetchone()[0], 1)

    def test_missing_case_reference_blocks_adoption(self):
        self.old.crea(descrizione='Voce con collegamento storico', minuti=3,
                      fatturabile=False, id_fascicolo='NON_PRESENTE')
        with self.assertRaisesRegex(ValueError, 'Riferimento Timesheet assente'):
            migration.migrate(self.root, self.root/'backup-rifiutato')
        self.assertEqual(self.target.conn.execute('SELECT count(*) FROM timesheet_entries').fetchone()[0], 0)
        self.assertFalse((self.root/'backup-rifiutato').exists())

if __name__=='__main__': unittest.main()
