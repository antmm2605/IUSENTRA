"""Guardrail della migrazione SQL Timesheet, senza mirror JSON."""
import tempfile
import unittest
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

if __name__=='__main__': unittest.main()