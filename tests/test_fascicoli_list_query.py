"""Guardie tecniche: selezione SQL prima del trasferimento dei payload."""
import os
import sqlite3

import pytest

from pct.fascicoli_list_query import FascicoliListNotReady, FascicoliListQuery, install_schema, install_source_events
from tests.test_condivisioni_sql_repository import SQLFactory
from web.services.fascicoli_list_projection import native_sort_values, native_summary_values


@pytest.fixture(params=['sqlite', 'postgresql'])
def catalog(request):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato.')
    factory = SQLFactory(request.param)
    try:
        db = factory.new()
        db.backend_kind = request.param
        if request.param == 'sqlite':
            db.conn.row_factory = sqlite3.Row
        install_schema(db.conn, postgres=request.param == 'postgresql')
        db.conn.execute("INSERT INTO fascicoli_list_owner VALUES (1,'studio',1)")
        from datetime import date
        from pct.fascicoli_list_clock import initialize_clock
        initialize_clock(db.conn, 'studio', date.today().isoformat())
        repo = FascicoliListQuery(db, 'studio')
        for number in range(61):
            item = dict(id=f'F{number:03}', client=f'Cliente {number:03}', title=f'Pratica {number:03}',
                        type='civile', status='in_corso', rg=f'{number}/2026', rgYear=2026,
                        notes='100%_prova' if number == 40 else '',
                        court='Tribunale di Milano', paymentSummary={'stato': 'completo'})
            repo.project(db.conn, item=item, revision=f'rev-{number}', source_order=number,
                         sort_values=native_sort_values(item), summary_values=native_summary_values(item))
        factory.commit(db)
        yield db, repo
    finally:
        factory.close()


def test_pagina_trasferisce_solo_righe_richieste_e_conteggio_intero(catalog, monkeypatch):
    _db, repo = catalog
    import pct.fascicoli_list_query as module
    decoded = []
    original = module.json.loads

    def decode(value):
        decoded.append(value)
        return original(value)

    monkeypatch.setattr(module.json, 'loads', decode)
    result = repo.list_page(page=2, page_size=25)
    assert len(decoded) == 25
    assert result['pagination'] == dict(page=2, pageSize=25, total=61, pages=3)
    assert [row['id'] for row in result['items']] == [f'F{n:03}' for n in range(25, 50)]


def test_ricerca_trova_cliente_fuori_prima_pagina_e_escape_letterale(catalog):
    _db, repo = catalog
    assert [row['id'] for row in repo.list_page(client='040')['items']] == ['F040']
    assert [row['id'] for row in repo.list_page(query='100%_')['items']] == ['F040']
    assert repo.list_page(field_filters={'notes': '100%_'})['pagination']['total'] == 1
    assert repo.list_page(query="' OR 1=1 --")['pagination']['total'] == 0


def test_tutti_i_filtri_sql_concordano_con_le_regole_native(catalog):
    from pct.fascicoli_list_query import FIELD_KEYS, PAYMENT_FIELDS
    from web.services.react_fascicoli_bridge import _matches_list_filters
    db, repo = catalog
    item = dict(id='TARGET',client='Cliente condiviso',title='Titolo completo',type='lavoro',
        status='da_archiviare',alerts=1,unreadCommunications=2,rgMissing=True,duplicateCount=2,
        paymentSummary={'stato':'parziale','parcelleDaEmettere':1,
            'items':{kind:{'status':'pagato'} for kind in PAYMENT_FIELDS}})
    for name, field in FIELD_KEYS.items():
        item.setdefault(field,'Contenuto '+name+' 100%_ StraßE')
    item.update(value=1234.56,rgYear=2026,openedAt='2025-01-01',closedAt='2026-01-01')
    repo.project(db.conn,item=item,revision='completo',source_order='9999',
        sort_values=native_sort_values(item),summary_values=native_summary_values(item))
    source=repo.list_page(page_size=100)['items']
    filters=[{'field_filters':{name:str(item[field])[:4] if name in {'opened_year','archived_year'} else str(item[field])}}
        for name,field in FIELD_KEYS.items()]
    filters += [{'payment_filters':{kind:status}} for kind in PAYMENT_FIELDS for status in ('pagato','da_registrare','tutti')]
    filters += [{'payment_filters':{'parcella':'da_emettere'}},{'status':'definito'},{'query':'100%_'},
        {'client':'condiviso'},{'rg':'2026'},{'court':'tribunale'},{'type_filter':'lavoro'},
        *[{key:True} for key in ('alerts_only','communications_only','payments_only','missing_rg_only','duplicates_only')]]
    renamed={'client':'client_filter','rg':'rg_filter','status':'status_filter'}
    for params in filters:
        reference={renamed.get(key,key):value for key,value in params.items()}
        expected={row['id'] for row in source if _matches_list_filters(row,**reference)}
        actual={row['id'] for row in repo.list_page(page_size=100,**params)['items']}
        assert actual==expected,params


def test_cambio_tenant_non_espone_catalogo_altrui(catalog):
    db, _repo = catalog
    with pytest.raises(FascicoliListNotReady):
        FascicoliListQuery(db, 'altro').list_page()


def test_scrittori_della_stessa_proiezione_si_serializzano(catalog):
    from web.services.fascicoli_list_writer import FascicoliListWriter
    db, _repo = catalog
    writer=object.__new__(FascicoliListWriter)
    writer.database,writer.tenant=db,'studio'
    writer._lock(db.conn,'case:F000')
    if db.backend_kind=='sqlite':
        path=db.conn.execute('PRAGMA database_list').fetchone()[2]
        second=sqlite3.connect(path,timeout=0.01)
        try:
            with pytest.raises(sqlite3.OperationalError,match='locked'):
                second.execute('UPDATE fascicoli_list_owner SET version=version WHERE singleton=1')
            db.conn.rollback()
            second.execute('UPDATE fascicoli_list_owner SET version=version WHERE singleton=1')
            second.rollback()
        finally:
            second.close()
    else:
        import psycopg2
        second=psycopg2.connect(db.raw_conn.dsn,password=os.environ['AUDIT_POSTGRES_PASSWORD'])
        try:
            with second.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s),hashtext(%s))',('studio','list:case:F000'))
                assert cursor.fetchone()[0] is False
                db.raw_conn.rollback()
                cursor.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s),hashtext(%s))',('studio','list:case:F000'))
                assert cursor.fetchone()[0] is True
            second.rollback()
        finally:
            second.close()


def test_recupero_conferma_solo_errori_osservati_prima_della_proiezione(catalog):
    from pct.transactional_outbox import OutboxEvent, enqueue
    from pct.fascicoli_list_query import AGGREGATE, EVENT_TYPE
    from web.services.fascicoli_list_writer import FascicoliListWriter
    db, _repo = catalog
    def failed(key, token):
        event = OutboxEvent(tenant_id='studio', aggregate_type=AGGREGATE,
            aggregate_id=key, aggregate_version=1, event_type=EVENT_TYPE,
            idempotency_key=token, payload={}, actor_id='test')
        enqueue(db.conn, event)
        row = db.conn.execute('SELECT id FROM transactional_outbox WHERE idempotency_key=?', (token,)).fetchone()
        db.conn.execute("UPDATE transactional_outbox SET status='FAILED',last_error='Causa conservata' WHERE id=?", (row[0],))
        return row[0]
    previous = failed('case:F000', 'precedente')
    unrelated = failed('case:F001', 'estraneo')
    writer = object.__new__(FascicoliListWriter)
    writer.tenant = 'studio'
    created = []
    writer._project_event = lambda _conn, _key: created.append(failed('case:F000', 'successivo'))
    writer.handle_event(db.conn, 'case:F000')
    rows = {row[0]: (row[1], row[2]) for row in db.conn.execute('SELECT id,status,last_error FROM transactional_outbox').fetchall()}
    assert rows[previous][0] == 'PROCESSED' and rows[previous][1].startswith('Causa conservata')
    assert rows[unrelated][0] == rows[created[0]][0] == 'FAILED'


def test_cambio_giorno_accoda_solo_termini_interessati_con_cursore_finito(catalog, monkeypatch):
    from datetime import date
    import pct.fascicoli_list_clock as clock
    db, _repo = catalog
    class Tomorrow(date):
        @classmethod
        def today(cls):
            return cls(2099, 1, 2)
    monkeypatch.setattr(clock, 'date', Tomorrow)
    db.conn.execute("UPDATE fascicoli_list_clock SET event_day='2099-01-01' WHERE tenant_key='studio'")
    for key, day in (('gia-critico','2099-01-03'), ('A','2099-01-05'), ('B','2099-01-06'),
                     ('C','2099-01-09'), ('lontano','2099-01-20')):
        db.conn.execute('INSERT INTO fascicoli_list_deadlines VALUES (?,?,?,?,?,?)',
            ('studio',key,'F000',day,'sintetico','{}'))
    assert not clock.clock_ready(db.conn, 'studio')
    assert clock.refresh_clock(db.conn, 'studio', postgres=db.backend_kind == 'postgresql', limit=2) == 2
    assert not clock.clock_ready(db.conn, 'studio')
    assert clock.refresh_clock(db.conn, 'studio', postgres=db.backend_kind == 'postgresql', limit=2) == 1
    assert clock.clock_ready(db.conn, 'studio')
    keys = [row[0] for row in db.conn.execute('SELECT aggregate_id FROM transactional_outbox ORDER BY aggregate_id').fetchall()]
    assert keys == ['deadline:A','deadline:B','deadline:C']
    assert clock.refresh_clock(db.conn, 'studio', postgres=db.backend_kind == 'postgresql', limit=2) == 0
    with pytest.raises(ValueError, match='proprietario'):
        clock.refresh_clock(db.conn, 'estraneo')


def test_cambio_giorno_non_sovrascrive_un_cursore_avanzato(catalog, monkeypatch):
    from datetime import date
    import pct.fascicoli_list_clock as clock
    db, _repo = catalog
    class Tomorrow(date):
        @classmethod
        def today(cls):
            return cls(2099, 1, 2)
    monkeypatch.setattr(clock, 'date', Tomorrow)
    db.conn.execute("UPDATE fascicoli_list_clock SET event_day='2099-01-01' WHERE tenant_key='studio'")
    db.conn.execute('INSERT INTO fascicoli_list_deadlines VALUES (?,?,?,?,?,?)',
        ('studio','A','F000','2099-01-05','sintetico','{}'))
    original = clock.enqueue
    def advance(connection, event):
        result = original(connection, event)
        connection.execute("UPDATE fascicoli_list_clock SET after_key='avanzato' WHERE tenant_key='studio'")
        return result
    monkeypatch.setattr(clock, 'enqueue', advance)
    with pytest.raises(RuntimeError, match='concorrente'):
        clock.refresh_clock(db.conn, 'studio', postgres=db.backend_kind == 'postgresql')
    assert db.conn.execute("SELECT after_key FROM fascicoli_list_clock WHERE tenant_key='studio'").fetchone()[0] == 'avanzato'


def test_pagina_inesistente_e_ultimo_gruppo_non_creano_righe(catalog):
    _db, repo = catalog
    result = repo.list_page(page=999, page_size=25)
    assert result['pagination'] == dict(page=3, pageSize=25, total=61, pages=3)
    assert len(result['items']) == 11
    assert repo.list_page(client='assente')['pagination']['total'] == 0
    with pytest.raises(ValueError):
        repo.list_page(page_size=1000)


def test_evento_nativo_blocca_catalogo_vecchio_e_conserva_chiave_scadenza(catalog):
    db, repo = catalog
    for table in ('fascicoli', 'scadenze', 'parcelle', 'clienti'):
        db.conn.execute('CREATE TABLE ' + table + ' (id TEXT PRIMARY KEY,id_fascicolo TEXT)')
    install_source_events(db.conn, postgres=db.backend_kind == 'postgresql')
    db.conn.execute("INSERT INTO scadenze VALUES ('S1','F001')")
    with pytest.raises(FascicoliListNotReady):
        repo.list_page()
    db.conn.execute("UPDATE transactional_outbox SET status='PROCESSED'")
    db.conn.execute("UPDATE scadenze SET id_fascicolo='F002' WHERE id='S1'")
    keys = {row[0] for row in db.conn.execute(
        "SELECT aggregate_id FROM transactional_outbox WHERE status='PENDING'").fetchall()}
    assert keys == {'deadline:S1'}
    db.conn.execute("UPDATE transactional_outbox SET status='PROCESSED'")
    assert repo.list_page()['pagination']['total'] == 61
    existing = db.conn.execute('SELECT COUNT(*) FROM transactional_outbox').fetchone()[0]
    db.conn.execute("INSERT INTO parcelle VALUES ('P1','')")
    assert db.conn.execute('SELECT COUNT(*) FROM transactional_outbox').fetchone()[0] == existing
    db.conn.execute("UPDATE parcelle SET id_fascicolo='F010' WHERE id='P1'")
    db.conn.execute("UPDATE parcelle SET id_fascicolo='' WHERE id='P1'")
    keys = {row[0] for row in db.conn.execute("SELECT aggregate_id FROM transactional_outbox WHERE status='PENDING'").fetchall()}
    assert keys == {'case:F010'}


def test_ordinamenti_e_raggruppamenti_conservano_ordine_nativo(catalog):
    db, repo = catalog
    import json
    from pct.fascicoli_list_query import SORTS, GROUPS
    from web.services.react_fascicoli_bridge import _sort_list_items, _group_list_items
    for index, client in enumerate(('Èlite', 'Zeta', 'ß', 'ss')):
        item = dict(id=f'UNICODE-{index}', client=client, title='Titolo uguale', type='civile', status='in_corso',
                    groupName=client, rgYear=2025, rgNumber=800 - index, value=123.45 + index,
                    openedAt='2025-01-01', updatedAt=f'2026-10-1{index}', documents=index)
        repo.project(db.conn, item=item, revision='unicode-proof', source_order=f'Z{index}',
                     sort_values=native_sort_values(item), summary_values=native_summary_values(item))
    item = dict(id='ROLE-MISSING', client='', title='Senza ruolo', type='civile', status='aperto',
                rgYear=0, rgNumber=0, value=0, documents=0)
    repo.project(db.conn, item=item, revision='missing-role', source_order='Z5',
                 sort_values=native_sort_values(item), summary_values=native_summary_values(item))
    originals = [json.loads(row[0]) for row in db.conn.execute(
        'SELECT payload_json FROM fascicoli_list_rows ORDER BY source_order DESC').fetchall()]
    for sort in SORTS:
        for group in ('', *sorted(GROUPS)):
            expected = _group_list_items(_sort_list_items(originals, sort, 'valore'), group)
            result = repo.list_page(page_size=100, sort=sort, secondary_sort='valore', group_by=group)
            assert [row['id'] for row in result['items']] == [row['id'] for row in expected], (sort, group)
    assert repo.aggregates(client='040')['total'] == 1
    assert repo.aggregates()['total'] == 66
    assert sum(row['count'] for row in repo.facets()) == 66


def test_repository_nativo_legge_solo_ids_del_lotto_senza_allegati(catalog, tmp_path):
    import json
    import re
    from pct.database import SCHEMA_SQL
    from pct.storage_postgres import CORE_POSTGRES_SCHEMA_SQL
    from pct.fascicoli import GestioneFascicoli
    db, _query = catalog
    schema = CORE_POSTGRES_SCHEMA_SQL if db.backend_kind == 'postgresql' else SCHEMA_SQL
    db.conn.execute('CREATE TABLE clienti(id TEXT PRIMARY KEY)')
    definition = re.search(r'CREATE TABLE IF NOT EXISTS fascicoli \(.*?\n\);', schema, re.S)
    assert definition
    db.conn.execute(definition.group())
    for index in range(30):
        payload = dict(id=f'CASE{index:02}', numero=f'2026/{index:03}', titolo='Caso controllato',
                       tipo='CIVILE', stato='APERTO', nome_cliente='Cliente controllato')
        db.conn.execute('INSERT INTO fascicoli(id,numero,dati_json,documenti_json) VALUES (?,?,?,?)',
            (payload['id'], payload['numero'], json.dumps(payload), json.dumps([{'id': f'D{n}'} for n in range(7)])))
    selected = []

    def read(sql, parameters):
        assert 'WHERE id IN (' in sql
        assert 'SELECT *' not in sql
        rows = db.conn.execute(sql, parameters).fetchall()
        selected.extend(rows)
        return rows

    db.fetchall_readonly = read
    native = GestioneFascicoli(str(tmp_path / 'fascicoli.json'), studio_db=db, carica_tutto=False)
    values = native.elenco_per_ids(['CASE25', 'CASE02'])
    assert [value.id for value in values] == ['CASE25', 'CASE02']
    assert len(selected) == 2
    assert all(value.documenti_non_caricati and not value.documenti and value.documenti_conteggio == 7 for value in values)
    assert native._fascicoli == {}
    assert db.conn.execute('SELECT COUNT(*) FROM fascicoli').fetchone()[0] == 30
    assert native.elenco_per_ids([]) == []
    with pytest.raises(ValueError):
        native.elenco_per_ids([str(n) for n in range(101)])
