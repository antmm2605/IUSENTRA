"""Selezione cliente limitata e senza inventario, SQLite/PostgreSQL."""
import os
from types import SimpleNamespace

import pytest

from pct.clienti import cerca_clienti_sql
from tests.test_condivisioni_sql_repository import SQLFactory
from web.services.react_redazione_guidata_bridge import build_redazione_clienti_payload


@pytest.fixture(params=['sqlite', 'postgresql'])
def client_search_db(request):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato')
    factory = SQLFactory(request.param)
    db = factory.new()
    db.conn.execute('CREATE TABLE clienti (id TEXT PRIMARY KEY,tipo TEXT,cognome TEXT,nome TEXT,ragione_sociale TEXT,codice_fiscale TEXT,partita_iva TEXT)')
    db.conn.execute('CREATE TABLE fascicoli (id TEXT PRIMARY KEY,id_cliente TEXT,stato TEXT)')
    db.conn.execute('CREATE INDEX redazione_fascicoli_cliente ON fascicoli(id_cliente,stato)')
    db.conn.execute('INSERT INTO clienti VALUES (?,?,?,?,?,?,?)',('cliente','PERSONA_FISICA','Rossi','Mario','','RSSMRA70B10G288K',''))
    for key,state in [('attivo','APERTO'),('chiuso','DEFINITO'),('archivio','ARCHIVIATO')]:
        db.conn.execute('INSERT INTO fascicoli VALUES (?,?,?)',(key,'cliente',state))
    factory.commit(db)
    try:
        yield db, factory
    finally:
        factory.close()


def test_ricerca_vuota_non_consulta_archivi():
    class Forbidden:
        @property
        def conn(self):
            pytest.fail('Accesso SQL non richiesto')
    for value in ('', ' ', 'R'):
        assert cerca_clienti_sql(Forbidden(), value) == {'clienti': [], 'altriRisultati': False}
    assert build_redazione_clienti_payload()['clienti'] == []
    with pytest.raises(ValueError, match='Archivio SQL'):
        cerca_clienti_sql(None, 'Rossi')


def test_nome_ordine_inverso_codice_e_fascicoli_sql(client_search_db):
    db, _ = client_search_db
    for query in ('Rossi', 'Mario Rossi', 'ROSSI MARIO', 'rssmra70'):
        result = cerca_clienti_sql(db, query)
        assert [item['id'] for item in result['clienti']] == ['cliente']
        assert result['clienti'][0]['label'] == 'Rossi Mario'
        assert result['clienti'][0]['fascicoli'] == 2
        assert not result['altriRisultati']


def test_risultati_limitati_e_caratteri_letterali(client_search_db):
    db, factory = client_search_db
    for i in range(30):
        db.conn.execute('INSERT INTO clienti VALUES (?,?,?,?,?,?,?)',(f'c{i}','PERSONA_FISICA','Rossi',f'Controllo {i}','','',''))
    db.conn.execute('INSERT INTO clienti VALUES (?,?,?,?,?,?,?)',('societa','PERSONA_GIURIDICA','','','ALFA 100%_TEST','','01234567890'))
    factory.commit(db)
    result = cerca_clienti_sql(db, 'Rossi')
    assert len(result['clienti']) == 20 and result['altriRisultati']
    assert cerca_clienti_sql(db, 'non presente')['clienti'] == []
    assert [item['id'] for item in cerca_clienti_sql(db, '%_')['clienti']] == ['societa']
    assert cerca_clienti_sql(db, "' OR 1=1 --")['clienti'] == []


def test_consultazione_usa_solo_select_e_non_carica_tutti_i_clienti(client_search_db):
    db, _ = client_search_db
    class ReadOnly:
        def execute(self, sql, parameters):
            assert sql.lstrip().startswith('SELECT')
            assert 'LIMIT ?' in sql
            return db.conn.execute(sql, parameters)
    result = build_redazione_clienti_payload(ricerca='Rossi', studio_db=SimpleNamespace(conn=ReadOnly()))
    assert result['totale'] == 1


def test_nessuna_cache_o_fonte_condivisa_fra_database_degli_studi(client_search_db):
    db, factory = client_search_db
    other = SQLFactory(factory.backend)
    try:
        other_db = other.new()
        other_db.conn.execute('CREATE TABLE clienti (id TEXT PRIMARY KEY,tipo TEXT,cognome TEXT,nome TEXT,ragione_sociale TEXT,codice_fiscale TEXT,partita_iva TEXT)')
        other_db.conn.execute('CREATE TABLE fascicoli (id TEXT PRIMARY KEY,id_cliente TEXT,stato TEXT)')
        other_db.conn.execute('INSERT INTO clienti VALUES (?,?,?,?,?,?,?)',('cliente','PERSONA_FISICA','Rossi','Anna','','',''))
        other.commit(other_db)
        assert cerca_clienti_sql(db, 'Rossi')['clienti'][0]['label'] == 'Rossi Mario'
        isolated = cerca_clienti_sql(other_db, 'Rossi')['clienti'][0]
        assert isolated['label'] == 'Rossi Anna' and isolated['fascicoli'] == 0
        assert cerca_clienti_sql(db, 'Rossi')['clienti'][0]['fascicoli'] == 2
    finally:
        other.close()
