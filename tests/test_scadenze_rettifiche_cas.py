"""CAS della rettifica: database controllati SQLite/PostgreSQL, nessun dato dello studio."""
import json,sys,unittest,sqlite3
from types import SimpleNamespace
from tests.test_condivisioni_sql_repository import SQLFactory
from pct.scadenze_rettifiche_repository import ScadenzeRettificheRepository as Repo
class Checks(unittest.TestCase):
    backend='sqlite'
    def setUp(self):
        self.factory=SQLFactory(self.backend);self.addCleanup(self.factory.close)
        self.db=self.factory.new()
        if self.backend=='sqlite': self.db.conn.row_factory=sqlite3.Row
        self.db.conn.execute('CREATE TABLE scadenze (id TEXT PRIMARY KEY,stato TEXT,titolo TEXT,data_scadenza TEXT,note TEXT,id_fascicolo TEXT,id_utente TEXT,dati_json TEXT)')
        self.riga=SimpleNamespace(id='auto-1',id_fascicolo='case-1',note='automatic provenance',titolo='Termine',data_scadenza='2026-10-06')
        self.payload={'id':'auto-1','stato':'APERTO','note':self.riga.note,'original_date':'2026-10-06','extra':{'amount':1234.56,'original_source':'controlled-source'}}
        for key,case in [('auto-1','case-1'),('manual-2','case-1'),('other-tenant-record','case-2')]:
            payload={**self.payload,'id':key}
            self.db.conn.execute('INSERT INTO scadenze VALUES (?,?,?,?,?,?,?,?)',(key,'APERTO','Termine','2026-10-06',self.riga.note,case,'',json.dumps(payload)))
        self.factory.commit(self.db)
    def row(self,key):return dict(self.db.conn.execute('SELECT * FROM scadenze WHERE id=?',(key,)).fetchone())
    def test_only_target_and_source_fields_preserved(self):
        others=[self.row('manual-2'),self.row('other-tenant-record')]
        Repo(self.db).annulla_proposta(self.riga,nota='automatic provenance\nRettifica motivata',traccia=[{'audit_id':'controlled-audit'}])
        changed=self.row('auto-1');payload=json.loads(changed['dati_json'])
        self.assertEqual(changed['stato'],'ANNULLATO');self.assertEqual(payload['extra'],self.payload['extra'])
        self.assertEqual(payload['original_date'],'2026-10-06');self.assertEqual(json.loads(payload['trace_json']),[{'audit_id':'controlled-audit'}])
        self.assertEqual([self.row('manual-2'),self.row('other-tenant-record')],others)
        with self.assertRaises(RuntimeError):Repo(self.db).annulla_proposta(self.riga,nota='second',traccia=[])
    def test_wrong_case_and_assigned_record_preserved(self):
        before=self.row('auto-1');wrong=SimpleNamespace(**vars(self.riga));wrong.id_fascicolo='case-2'
        with self.assertRaises(RuntimeError):Repo(self.db).annulla_proposta(wrong,nota='wrong',traccia=[])
        self.assertEqual(self.row('auto-1'),before)
        self.db.conn.execute('UPDATE scadenze SET id_utente=? WHERE id=?',('controlled-lawyer','auto-1'));self.factory.commit(self.db)
        with self.assertRaises(RuntimeError):Repo(self.db).annulla_proposta(self.riga,nota='wrong',traccia=[])
        self.assertEqual(self.row('auto-1')['stato'],'APERTO')
    def test_real_concurrent_update_is_not_overwritten(self):
        other=self.factory.new();original_conn=self.db.conn;factory=self.factory
        corrected={**self.payload,'description':'controlled manual correction'}
        class Interleaved:
            def execute(inner,sql,args=()):
                if sql.startswith('UPDATE scadenze SET stato='):
                    other.conn.execute('UPDATE scadenze SET dati_json=? WHERE id=?',(json.dumps(corrected),'auto-1'));factory.commit(other)
                return original_conn.execute(sql,args)
        guarded=SimpleNamespace(conn=Interleaved())
        with self.assertRaises(RuntimeError):Repo(guarded).annulla_proposta(self.riga,nota='must not apply',traccia=[])
        after=self.row('auto-1');self.assertEqual(after['stato'],'APERTO');self.assertEqual(json.loads(after['dati_json']),corrected)
if __name__=='__main__':
    Checks.backend='postgresql' if '--postgresql' in sys.argv else 'sqlite'
    sys.argv=[a for a in sys.argv if a!='--postgresql'];unittest.main(verbosity=2)