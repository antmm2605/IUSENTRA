"""CAS delle letture su SQL controllato; nessuna modifica ai dati operativi."""
import json,os,sqlite3,unittest,uuid
from contextlib import contextmanager
from types import SimpleNamespace
from tests.test_condivisioni_sql_repository import SQLFactory
from pct.registro_letture.repository import RegistroLetture,SCHEMA_SQLITE,SCHEMA_POSTGRES
from pct.registro_letture.modello import Oggetto
from pct.registro_letture.fatti_repository import Fatto

ControlledRegistro=RegistroLetture

class Checks(unittest.TestCase):
    backend='sqlite'
    @classmethod
    def setUpClass(cls):
        cls.factory=SQLFactory(cls.backend)
        try:
            db=cls.factory.new()
            if cls.backend=='sqlite':
                db.conn.executescript(SCHEMA_SQLITE.read_text())
            else:
                with db.raw_conn.cursor() as cur:
                    cur.execute(SCHEMA_POSTGRES.read_text())
            cls.factory.commit(db)
        except Exception:
            cls.factory.close()
            raise
    @classmethod
    def tearDownClass(cls):
        cls.factory.close()
    def setUp(self):
        self.tenant='controlled-'+uuid.uuid4().hex
        self.reg=object.__new__(ControlledRegistro)
        @contextmanager
        def connection():
            db=self.factory.new()
            if self.backend=='sqlite':
                db.conn.row_factory=sqlite3.Row
            if self.backend=='postgresql':
                from pct.postgres_runtime_support import PostgresRepositoryConnection
                db.conn=PostgresRepositoryConnection(db)
            try:
                yield db.conn
                self.factory.commit(db)
            except Exception:
                (getattr(db,'raw_conn',None) or db.conn).rollback()
                raise
        self.reg.connection=connection
        self.obj=Oggetto(tipo='documento',oggetto_id='D1',nome='Tessera sanitaria.pdf',sha256='a'*64)
        self.reg.registra_inventario(self.tenant,'F1',[self.obj])
        self.reg.registra_fatti(self.tenant,'F1',self.obj,'documenti',[
            Fatto(categoria='data',campo='termine',valore='2028-10-12',valore_letto='12/10/2028',contesto='TESSERA SANITARIA Data di scadenza 12/10/2028',verifica='plausibile'),
            Fatto(categoria='data',campo='udienza',valore='2028-10-12',valore_letto='12/10/2028',contesto='Il Giudice fissa udienza del 12/10/2028',verifica='plausibile'),
        ])
        self.rows=self.reg.fatti(self.tenant,'F1')
        self.invalid=next(f for f in self.rows if f.campo=='termine')
    def apply(self):
        return self.reg.riconvalida_fatti(self.tenant,'F1',fatti_ids=[self.invalid.id],impronte_attese={self.invalid.id:'a'*64})
    def test_selected_fact_rejected_with_evidence_and_legal_date_preserved(self):
        self.assertEqual([f.id for f in self.apply()],[self.invalid.id])
        rows=self.reg.fatti(self.tenant,'F1',verifiche=None)
        rejected=next(f for f in rows if f.id==self.invalid.id)
        self.assertEqual(rejected.verifica,'respinta')
        self.assertTrue(any(p.get('codice')=='riconvalida' for p in rejected.prove))
        self.assertEqual(next(f for f in rows if f.campo=='udienza').verifica,'plausibile')
    def test_legal_order_to_produce_health_card_is_not_rejected(self):
        obj=Oggetto(tipo='documento',oggetto_id='D2',nome='Ordine di produzione.pdf',sha256='c'*64)
        self.reg.registra_inventario(self.tenant,'F1',[self.obj,obj])
        self.reg.registra_fatti(self.tenant,'F1',obj,'documenti',[
            Fatto(categoria='data',campo='termine',valore='2028-10-12',valore_letto='12/10/2028',contesto='Il giudice assegna termine perentorio entro il 12/10/2028 per produzione tessera sanitaria',verifica='plausibile'),
        ])
        selected=next(f for f in self.reg.fatti(self.tenant,'F1') if f.oggetto_id=='D2')
        self.assertEqual(self.reg.riconvalida_fatti(self.tenant,'F1',fatti_ids=[selected.id],impronte_attese={selected.id:'c'*64}),[])
    def test_explicit_empty_selection_never_runs_all_records(self):
        self.assertEqual(self.reg.riconvalida_fatti(self.tenant,'F1',fatti_ids=[]),[])
        self.assertEqual(len(self.reg.fatti(self.tenant,'F1')),2)
    def test_tenant_isolation(self):
        self.assertEqual(self.reg.riconvalida_fatti('other','F1',fatti_ids=[self.invalid.id]),[])
        self.assertEqual(len(self.reg.fatti(self.tenant,'F1')),2)
    def test_manual_decision_is_preserved(self):
        self.reg.decidi_fatto(self.tenant,self.invalid.id,verifica='corretta',valore='2028-10-12',utente_id='controlled-lawyer')
        self.assertEqual(self.apply(),[])
        self.assertEqual(next(f for f in self.reg.fatti(self.tenant,'F1',verifiche=None) if f.id==self.invalid.id).verifica,'corretta')
    def test_changed_source_hash_blocks_revalidation(self):
        with self.reg.connection() as conn:
            conn.execute('UPDATE letture_oggetti SET sha256=? WHERE tenant_id=? AND oggetto_id=?',('b'*64,self.tenant,'D1'))
        with self.assertRaisesRegex(RuntimeError,'fonte'):
            self.apply()
        self.assertEqual(len(self.reg.fatti(self.tenant,'F1')),2)
    def test_removed_source_blocks_revalidation(self):
        with self.reg.connection() as conn:
            conn.execute('UPDATE letture_oggetti SET presente=0 WHERE tenant_id=? AND oggetto_id=?',(self.tenant,'D1'))
        with self.assertRaisesRegex(RuntimeError,'fonte'):
            self.apply()
    def test_wrong_expected_fact_hash_blocks_revalidation(self):
        with self.assertRaisesRegex(RuntimeError,'impronta'):
            self.reg.riconvalida_fatti(self.tenant,'F1',fatti_ids=[self.invalid.id],impronte_attese={self.invalid.id:'b'*64})
    def test_concurrent_manual_decision_cannot_be_overwritten(self):
        original=self.reg._seleziona_fatti
        changed=False
        def interleave(*args):
            nonlocal changed
            snapshot=original(*args)
            if not changed:
                changed=True
                with self.reg.connection() as conn:
                    conn.execute('UPDATE letture_fatti SET verifica=?,risolta_da=? WHERE tenant_id=? AND id=?',('corretta','controlled-lawyer',self.tenant,self.invalid.id))
            return snapshot
        self.reg._seleziona_fatti=interleave
        with self.assertRaisesRegex(RuntimeError,'cambiata durante'):
            self.apply()
        self.reg._seleziona_fatti=original
        self.assertEqual(next(f for f in self.reg.fatti(self.tenant,'F1',verifiche=None) if f.id==self.invalid.id).verifica,'corretta')

class SQLiteChecks(Checks):
    pass
@unittest.skipUnless(os.environ.get('AUDIT_POSTGRES_PASSWORD'),'PostgreSQL controllato non configurato')
class PostgreSQLChecks(Checks):
    backend='postgresql'
# Evita una terza esecuzione della sola base.
Checks.__unittest_skip__=True
Checks.__unittest_skip_why__='base'
SQLiteChecks.__unittest_skip__=False
PostgreSQLChecks.__unittest_skip__=not bool(os.environ.get('AUDIT_POSTGRES_PASSWORD'))
if __name__=='__main__':
    unittest.main()
