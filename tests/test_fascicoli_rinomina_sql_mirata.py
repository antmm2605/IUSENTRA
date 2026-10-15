"""Rinomina sulla transazione nativa, senza riscrivere altri dati dello studio."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from pct.fascicoli import Documento, Fascicolo, GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.storage import StudioDB
from pct.storage_postgres import PostgresStudioDB
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def rename_case(request, tmp_path, monkeypatch):
    if request.param == 'postgresql' and not os.environ.get('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('Database PostgreSQL controllato non configurato')
    factory = SQLFactory(request.param)
    backend = None
    try:
        if request.param == 'postgresql':
            from psycopg2.extensions import make_dsn
            backend = PostgresStudioDB(make_dsn(**factory.pg_parameters,
                options=f'-c search_path={factory.schema}'), initialize_schema=False)
        else:
            backend = StudioDB(str(Path(factory.temp.name) / 'controlled.db'), initialize_schema=False)
        backend.conn.execute("CREATE TABLE fascicoli (id TEXT PRIMARY KEY, documenti_json TEXT "
            "CHECK(documenti_json NOT LIKE '%%vietato.pdf%%'), dati_json TEXT, modificato_il TEXT, "
            "stato TEXT, pagamenti_json TEXT)")
        content = b'Controlled source: unchanged by renaming.'
        source = tmp_path / 'docs' / 'F1' / 'prima.pdf'
        source.parent.mkdir(parents=True)
        source.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        document = Documento(id='D1', nome='prima.pdf', percorso='F1/prima.pdf',
            tipo=TipoDocumento.ALLEGATO, hash_sha256=digest, hash_contenuto_sha256=digest,
            nome_originale='originale.pdf', fonte_documento='COLLAUDO', tags=['prova'])
        fascicolo = Fascicolo(id='F1', numero='2026/1', titolo='Caso controllato',
                             tipo=TipoFascicolo.CIVILE, documenti=[document])
        data = GestioneFascicoli._dati_json_snello(fascicolo.to_dict())
        data['decisione_manuale'] = {'incasso': 'confermato', 'importo': 1300}
        values = ('F1', json.dumps([document.to_dict()]), json.dumps(data), fascicolo.modificato_il,
                  'APERTO', '{"manuale":true}')
        backend.conn.execute('INSERT INTO fascicoli VALUES (?,?,?,?,?,?)', values)
        backend.conn.execute('INSERT INTO fascicoli VALUES (?,?,?,?,?,?)',
            ('F2', '[]', '{"id":"F2","titolo":"Altro caso"}', 'prima', 'CHIUSO', '{"incasso":99}'))
        commit(backend)
        manager = GestioneFascicoli(db_path=str(tmp_path / 'mirror.json'),
            documents_dir=str(tmp_path / 'docs'), studio_db=backend, carica_tutto=False)
        def forbidden(*args, **kwargs):
            raise AssertionError('La rinomina non deve leggere o riscrivere tutto l’archivio')
        monkeypatch.setattr(manager, '_salva', forbidden)
        monkeypatch.setattr(manager, '_carica', forbidden)
        monkeypatch.setattr(manager, '_allinea_stato_dalle_prove', forbidden)
        yield manager, backend, source, digest
    finally:
        if backend is not None:
            backend.chiudi()
        factory.close()


def commit(backend):
    if getattr(backend, 'backend_kind', '') == 'postgresql':
        backend.raw_conn.commit()
    else:
        backend.conn.commit()


def row(backend, identifier='F1'):
    return dict(backend.fetchall_readonly('SELECT * FROM fascicoli WHERE id=?', (identifier,))[0])


def replace_documents(backend, documents):
    backend.conn.execute('UPDATE fascicoli SET documenti_json=? WHERE id=?',
                         (json.dumps(documents), 'F1'))
    commit(backend)


def test_rinomina_mirata_preserva_fonte_altri_fascicoli_e_ripetizione(rename_case):
    manager, backend, source, digest = rename_case
    original = row(backend)
    other = row(backend, 'F2')
    renamed = manager.rinomina_documento('F1', 'D1', 'dopo.pdf')
    assert renamed.nome == 'dopo.pdf'
    assert not source.exists()
    assert hashlib.sha256(source.with_name('dopo.pdf').read_bytes()).hexdigest() == digest
    saved = row(backend)
    documents = json.loads(saved['documenti_json'])
    assert documents[0]['nome_originale'] == 'originale.pdf'
    assert documents[0]['fonte_documento'] == 'COLLAUDO'
    assert documents[0]['hash_sha256'] == digest
    assert documents[0]['tags'] == ['prova', 'iusentra:nome-personalizzato']
    assert saved['stato'] == original['stato']
    assert saved['pagamenti_json'] == original['pagamenti_json']
    assert json.loads(saved['dati_json'])['decisione_manuale'] == json.loads(original['dati_json'])['decisione_manuale']
    assert row(backend, 'F2') == other
    manager.rinomina_documento('F1', 'D1', 'dopo.pdf')
    assert row(backend) == saved
    assert not manager.db_path.exists()


def test_rinomina_preserva_modifiche_concorrenti_ad_altri_campi(rename_case):
    manager, backend, _, _ = rename_case
    manager.get('F1')
    documents = json.loads(row(backend)['documenti_json'])
    documents[0].update(note='Nota aggiornata da un altro utente', tags=['prova', 'manuale'])
    documents.append({'id': 'D2', 'nome': 'secondo.pdf', 'percorso': 'F1/secondo.pdf'})
    replace_documents(backend, documents)
    metadata = json.loads(row(backend)['dati_json'])
    metadata['decisione_manuale']['importo'] = 1700
    backend.conn.execute('UPDATE fascicoli SET dati_json=?,pagamenti_json=? WHERE id=?',
        (json.dumps(metadata), '{"incasso":1700,"manuale":true}', 'F1'))
    commit(backend)
    manager.rinomina_documento('F1', 'D1', 'dopo.pdf')
    saved = row(backend)
    documents = json.loads(saved['documenti_json'])
    assert documents[0]['note'] == 'Nota aggiornata da un altro utente'
    assert documents[0]['tags'] == ['prova', 'manuale', 'iusentra:nome-personalizzato']
    assert documents[1]['id'] == 'D2'
    assert json.loads(saved['dati_json'])['decisione_manuale']['importo'] == 1700
    assert json.loads(saved['pagamenti_json'])['incasso'] == 1700


@pytest.mark.parametrize('change', ['hash', 'missing', 'duplicate'])
def test_fonte_cambiata_o_ambigua_blocca_e_ripristina_il_file(rename_case, change):
    manager, backend, source, _ = rename_case
    manager.get('F1')
    documents = json.loads(row(backend)['documenti_json'])
    if change == 'hash':
        documents[0]['hash_sha256'] = 'b' * 64
    elif change == 'missing':
        documents = []
    else:
        documents.append(dict(documents[0]))
    replace_documents(backend, documents)
    before = row(backend)
    with pytest.raises(ValueError):
        manager.rinomina_documento('F1', 'D1', 'dopo.pdf')
    assert source.exists()
    assert not source.with_name('dopo.pdf').exists()
    assert row(backend) == before
    assert manager.get('F1').documenti[0].nome == 'prima.pdf'


def test_errore_sql_reale_non_conferma_e_ripristina_il_file(rename_case):
    manager, backend, source, _ = rename_case
    before = row(backend)
    with pytest.raises(Exception, match='constraint|CHECK'):
        manager.rinomina_documento('F1', 'D1', 'vietato.pdf')
    assert source.exists()
    assert not source.with_name('vietato.pdf').exists()
    assert row(backend) == before


def test_scrittura_da_connessione_indipendente_durante_la_transazione(rename_case, monkeypatch):
    manager, backend, source, _ = rename_case
    postgres = getattr(backend, 'backend_kind', '') == 'postgresql'
    other = PostgresStudioDB(backend.dsn, initialize_schema=False) if postgres else StudioDB(backend.db_path, initialize_schema=False)
    original_save = backend.salva_tabella
    interrupted = []
    def manual_update():
        current = row(other)
        metadata = json.loads(current['dati_json'])
        metadata['decisione_manuale']['importo'] = 1900
        other.conn.execute('UPDATE fascicoli SET dati_json=? WHERE id=?', (json.dumps(metadata), 'F1'))
        commit(other)
    class ConnectionBoundary:
        def __init__(self, connection):
            self.connection = connection
        def execute(self, sql, params=()):
            cursor = self.connection.execute(sql, params)
            if sql.startswith('SELECT documenti_json,dati_json,modificato_il'):
                captured = cursor.fetchone()
                if not postgres:
                    other.conn.execute('PRAGMA busy_timeout=0')
                try:
                    manual_update()
                except Exception as error:
                    assert not postgres and 'locked' in str(error).lower()
                    other.conn.rollback()
                    interrupted.append(True)
                return type('Snapshot', (), {'fetchone': lambda _: captured})()
            return cursor
    monkeypatch.setattr(backend, 'salva_tabella', lambda table, rows, writer, delete_all=True:
        original_save(table, rows, lambda connection, value: writer(ConnectionBoundary(connection), value), delete_all))
    try:
        if postgres:
            with pytest.raises(ValueError, match='durante la rinomina'):
                manager.rinomina_documento('F1', 'D1', 'dopo.pdf')
            assert source.exists()
            assert not source.with_name('dopo.pdf').exists()
        else:
            manager.rinomina_documento('F1', 'D1', 'dopo.pdf')
            assert interrupted == [True]
            manual_update()
            assert source.with_name('dopo.pdf').exists()
        assert json.loads(row(backend)['dati_json'])['decisione_manuale']['importo'] == 1900
    finally:
        other.chiudi()
