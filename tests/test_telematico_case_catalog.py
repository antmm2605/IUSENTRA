"""Guardrail SQL del catalogo; non sostituisce la prova nel browser reale."""
import sqlite3
import unittest
from types import SimpleNamespace
from web.services.telematico_case_catalog import build_telematico_case_catalog

class CatalogRepository:
    def __init__(self):
        self.db=sqlite3.connect(':memory:'); self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE v_telematic_case_overview (id TEXT, practice_id TEXT, service_code TEXT, office_name TEXT, subject_name TEXT, register_number TEXT, register_year TEXT, internal_status TEXT, native_status TEXT, documents_count INTEGER, open_tasks_count INTEGER, last_sync_at TEXT, updated_at TEXT, created_at TEXT)')
    def add(self, ident, practice='f1', service='polisweb_consultazione', status='import_completed', subject='Retribuzione', stamp='2026-10-06 22:30:00'):
        self.db.execute('INSERT INTO v_telematic_case_overview VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(ident,practice,service,'Tribunale di Vicenza',subject,'538','2026',status,'',1,0,stamp,stamp,stamp))
    def _fetchone(self, sql, args): return self.db.execute(sql,args).fetchone()
    def _fetchall(self, sql, args): return self.db.execute(sql,args).fetchall()

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.repo=CatalogRepository()
        self.visible=[SimpleNamespace(id='f1',titolo='Calabrò c. MIM',rg_completo='538/2026',tribunale='Vicenza',oggetto='Retribuzione')]
    def tearDown(self): self.repo.db.close()
    def catalog(self, **kwargs):return build_telematico_case_catalog(repository=self.repo,fascicoli=self.visible,**kwargs)
    def test_full_archive_pagination_and_scope(self):
        for i in range(61):self.repo.add(f'case-{i:03}')
        self.repo.add('secret',practice='other-studio')
        pages=[self.catalog(page=i) for i in range(1,4)]
        self.assertEqual([p['total'] for p in pages],[61]*3)
        ids=[item['id'] for p in pages for item in p['items']]
        self.assertEqual(len(ids),61);self.assertEqual(len(set(ids)),61);self.assertNotIn('secret',ids)
        self.assertEqual(self.catalog(page=999)['page'],3)
    def test_empty_visible_scope_has_no_foreign_data(self):
        self.repo.add('secret',practice='other-studio')
        result=build_telematico_case_catalog(repository=self.repo,fascicoli=[])
        self.assertEqual(result['total'],0)
    def test_missing_repository_fails_closed(self):
        with self.assertRaises(RuntimeError):build_telematico_case_catalog(repository=None,fascicoli=self.visible)
    def test_portals_filter_actual_sql_rows(self):
        for code in ['polisweb_consultazione','pdp_penale','pat_siga','ptt_sigit','custom']:
            self.repo.add(code,service=code)
        for portal in ['pst','pdp','pat','ptt','altro']:self.assertEqual(self.catalog(portal=portal)['total'],1)
        self.assertEqual(self.catalog(portal='pst-pdp')['total'],2)
        with self.assertRaises(ValueError):self.catalog(portal='inventato')
    def test_search_italian_label_without_synthetic_status(self):
        self.repo.add('a');self.repo.add('b',status='manual_review_required')
        self.assertEqual(self.catalog(query='Import completato')['total'],1)
        self.assertEqual(self.catalog(query='Verifica manuale richiesta')['total'],1)
        self.assertEqual(self.catalog(query='Da verificare')['total'],0)
    def test_accent_case_and_literal_wildcards(self):
        self.repo.add('a',subject='Termine 10%_~ Élite')
        self.assertEqual(self.catalog(query='CALABRO')['total'],1)
        self.assertEqual(self.catalog(query='élite')['total'],1)
        self.assertEqual(self.catalog(query='%_~')['total'],1)
        self.assertEqual(self.catalog(query='20%')['total'],0)
    def test_rg_year_visible_and_searchable(self):
        self.repo.add('a')
        self.assertIn('RG 538/2026',self.catalog()['items'][0]['subtitle'])
        self.assertEqual(self.catalog(query='538/2026')['total'],1)
    def test_presidi_preserve_independent_controls_and_unique_ids(self):
        for i in range(30):self.repo.add(str(i),status='manual_review_required')
        self.repo.add('completed')
        result=self.catalog(presidi=True,page_size=100)
        self.assertEqual(result['total'],90)
        self.assertEqual(len({i['id'] for i in result['items']}),90)
        self.assertEqual({i['controlCategory'] for i in result['items']},{'Blocco','Import incompleto','Avviso'})
        self.assertEqual(self.catalog(presidi=True,query='Import incompleto')['total'],30)
    def test_naive_timestamp_is_explicit_utc(self):
        self.repo.add('a')
        self.assertEqual(self.catalog()['items'][0]['syncedAt'],'2026-10-06T22:30:00+00:00')
    def test_aware_timestamp_preserves_offset(self):
        self.repo.add('a',stamp='2026-10-07T00:30:00+02:00')
        self.assertEqual(self.catalog()['items'][0]['syncedAt'],'2026-10-07T00:30:00+02:00')
    def test_invalid_timestamp_is_not_silently_replaced(self):
        self.repo.add('a',stamp='data non valida')
        self.assertEqual(self.catalog()['items'][0]['syncedAt'],'data non valida')

    def selection(self, **changes):
        value={'portal':'','query':'','scope':'','all':True,'selected':[],'excluded':[],'total':1,'count':1}
        value.update(changes);return value
    def export(self, **changes):
        from web.services.telematico_case_catalog import export_telematico_case_catalog
        return export_telematico_case_catalog(repository=self.repo,fascicoli=self.visible,payload=self.selection(**changes))
    def test_export_real_csv_format_and_exclusion(self):
        import csv,io
        self.repo.add('a');self.repo.add('b')
        data,name,count=self.export(total=2,count=1,excluded=['b'])
        rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')),delimiter=';'))
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'));self.assertEqual(count,1);self.assertEqual(len(rows),1)
        self.assertEqual(name,'pratiche-telematiche-selezionate.csv')
        self.assertEqual(rows[0]['Stato'],'Import completato')
        self.assertEqual(rows[0]['Ultimo aggiornamento'],'07/10/2026 00:30')
        self.assertEqual(rows[0]['Titolo'],'Calabrò c. MIM')
    def test_export_selected_does_not_include_foreign_ids(self):
        self.repo.add('a');self.repo.add('secret',practice='foreign')
        with self.assertRaises(ValueError):self.export(all=False,selected=['secret'])
    def test_export_rejects_changed_count_and_duplicate_ids(self):
        self.repo.add('a')
        with self.assertRaises(ValueError):self.export(total=2)
        with self.assertRaises(ValueError):self.export(all=False,selected=['a','a'])
        with self.assertRaises(ValueError):self.export(count=2)
    def test_export_empty_and_invalid_selection_are_rejected(self):
        self.repo.add('a')
        for value in [dict(count=0),dict(all='true'),dict(total=True),dict(selected=None),dict(scope='invalid')]:
            with self.subTest(value=value),self.assertRaises(ValueError):self.export(**value)
    def test_export_formula_quotes_and_newlines_are_safe(self):
        import csv,io
        self.visible[0].titolo=' =SUM(1;2)\n"Prova"'
        self.repo.add('a')
        data,_,_=self.export()
        row=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')),delimiter=';'))[0]
        self.assertTrue(row['Titolo'].startswith("'"));self.assertIn('"Prova"',row['Titolo'])
    def test_export_presidi_preserves_each_category(self):
        import csv,io
        self.repo.add('a',status='manual_review_required')
        data,name,count=self.export(scope='presidi',total=3,count=3)
        rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(count,3);self.assertEqual(name,'presidi-telematici-selezionati.csv')
        self.assertEqual({r['Dettaglio'].split(' · ')[0] for r in rows},{'Blocco','Avviso','Import incompleto'})
    def test_export_large_selection_covers_all_pages(self):
        for i in range(207):self.repo.add(str(i))
        data,_,count=self.export(total=207,count=207)
        self.assertEqual(count,207);self.assertEqual(len(data.decode('utf-8-sig').splitlines()),208)
    def test_export_invalid_date_is_explicit(self):
        self.repo.add('a',stamp='2026-invalid')
        data,_,_=self.export()
        self.assertIn('Data da verificare',data.decode('utf-8-sig'))
if __name__=='__main__':unittest.main()