import json
import os
from pathlib import Path

import pytest

from pct.fascicoli import Fascicolo, GestioneFascicoli, StatoFascicolo, TipoFascicolo
from pct.fascicoli_clienti_index import install_client_index
from tools.prepare_fascicoli_client_index import prepare_sqlite
import sqlite3
from pct.storage import StudioDB
from pct.storage_postgres import PostgresStudioDB
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def indexed_cases(request, tmp_path, monkeypatch):
    if request.param == 'postgresql' and not os.environ.get('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato')
    factory = SQLFactory(request.param)
    backend = None
    try:
        if request.param == 'postgresql':
            from psycopg2.extensions import make_dsn
            backend = PostgresStudioDB(make_dsn(**factory.pg_parameters,
                options=f'-c search_path={factory.schema}'), initialize_schema=False)
        else:
            backend = StudioDB(str(Path(factory.temp.name) / 'controlled.db'), initialize_schema=False)
        backend.conn.execute('CREATE TABLE _meta(chiave TEXT PRIMARY KEY,valore TEXT)')
        backend.conn.execute('CREATE TABLE fascicoli(id TEXT PRIMARY KEY,id_cliente TEXT,numero TEXT,'
            'dati_json TEXT,documenti_json TEXT,attivita_json TEXT,scadenze_json TEXT,'
            'tipo TEXT,stato TEXT,titolo TEXT)')
        for index, (key, scalar, modeled, variant) in enumerate([
            ('F1', 'C1', 'C1', 'normal'), ('F2', 'C2', 'C2', 'archived'),
            ('F3', 'C9', 'C1', 'normal'), ('F4', 'C1', 'C1', 'legacy'),
            ('F5', 'C1', 'C2', 'duplicate'), ('F6', 'C9', 'C1', 'escaped'),
            ('F7', 'C-bad', 'C-bad', 'invalid')], 1):
            case = Fascicolo(id=key, numero=f'2026/{index:03}', titolo=key,
                tipo=TipoFascicolo.CIVILE, id_cliente=modeled,
                stato=StatoFascicolo.ARCHIVIATO if variant == 'archived' else StatoFascicolo.APERTO)
            raw = json.dumps(case.to_dict())
            if variant == 'duplicate':
                raw = raw.replace('"id_cliente": "C2"', '"id_cliente": "C1", "id_cliente": "C2"')
            elif variant == 'escaped':
                raw = raw.replace('"id_cliente": "C1"', '"id_\\u0063liente": "\\u0043\\u0031"')
            elif variant == 'legacy':
                raw = None
            elif variant == 'invalid':
                raw = '{broken'
            backend.conn.execute('INSERT INTO fascicoli VALUES (?,?,?,?,?,?,?,?,?,?)',
                (key, scalar, case.numero, raw, '[]', '[]', '[]', case.tipo.value, case.stato.value, case.titolo))
        commit(backend)
        manager = GestioneFascicoli(db_path=str(tmp_path / 'historical.json'),
            documents_dir=str(tmp_path / 'documents'), studio_db=backend, carica_tutto=False)
        def forbidden(*_, **__):
            raise AssertionError('La ricerca cliente non deve caricare o riscrivere tutti i fascicoli')
        monkeypatch.setattr(manager, '_carica', forbidden)
        monkeypatch.setattr(manager, '_salva', forbidden)
        monkeypatch.setattr(manager, '_allinea_stato_dalle_prove', forbidden)
        yield manager, backend
    finally:
        if backend is not None:
            backend.chiudi()
        factory.close()


def commit(backend):
    if getattr(backend, 'backend_kind', '') == 'postgresql':
        backend.raw_conn.commit()
    else:
        backend.conn.commit()


def test_explicit_preparation_requires_backup_and_is_idempotent(tmp_path):
    path = tmp_path / 'studio.db'
    with sqlite3.connect(path) as conn:
        conn.executescript('CREATE TABLE _meta(chiave TEXT PRIMARY KEY,valore TEXT);'
                          'CREATE TABLE fascicoli(id TEXT PRIMARY KEY,id_cliente TEXT,dati_json TEXT);')
        conn.execute('INSERT INTO fascicoli VALUES (?,?,?)', ('F1', 'C1', '{"id_cliente":"C1"}'))
    with pytest.raises(ValueError, match='backup coerente'):
        prepare_sqlite(path)
    assert prepare_sqlite(path, tmp_path / 'backup') is True
    backup = list((tmp_path / 'backup').glob('*.db'))
    assert len(backup) == 1
    with sqlite3.connect(backup[0]) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert conn.execute('SELECT * FROM fascicoli').fetchall() == [('F1', 'C1', '{"id_cliente":"C1"}')]
    assert prepare_sqlite(path) is False
    assert len(list((tmp_path / 'backup').glob('*.db'))) == 1


def prepare(backend):
    result = install_client_index(backend.conn, postgres=getattr(backend, 'backend_kind', '') == 'postgresql')
    commit(backend)
    return result


def test_lookup_preserves_legacy_json_ownership_duplicate_keys_and_filters(indexed_cases):
    manager, backend = indexed_cases
    before = [dict(row) for row in backend.fetchall_readonly('SELECT * FROM fascicoli ORDER BY id')]
    assert prepare(backend)
    assert [case.id for case in manager.cerca(id_cliente='C1', archiviati=True)] == ['F6', 'F4', 'F3', 'F1']
    assert [case.id for case in manager.cerca(id_cliente='C2')] == ['F5']
    assert [case.id for case in manager.cerca(id_cliente='C2', archiviati=True)] == ['F5', 'F2']
    assert manager.cerca(id_cliente='C9', archiviati=True) == []
    assert [case.id for case in manager.cerca(id_cliente='C1', testo='F3', archiviati=True)] == ['F3']
    assert not manager._archivio_completo
    assert [dict(row) for row in backend.fetchall_readonly('SELECT * FROM fascicoli ORDER BY id')] == before
    assert prepare(backend) is False


def test_missing_catalog_is_explicit_and_does_not_start_preparation(indexed_cases):
    manager, backend = indexed_cases
    with pytest.raises(RuntimeError, match='non preparato'):
        manager.cerca(id_cliente='C1')
    assert backend.conn.execute("SELECT valore FROM _meta WHERE chiave=?",
                                ('fascicoli_clienti_index',)).fetchone() is None


def test_raw_sql_updates_deletes_and_rollback_keep_the_catalog_in_the_same_transaction(indexed_cases):
    manager, backend = indexed_cases
    prepare(backend)
    data = dict(backend.conn.execute("SELECT dati_json FROM fascicoli WHERE id='F1'").fetchone())
    payload = json.loads(data['dati_json'])
    payload['id_cliente'] = 'C3'
    backend.conn.execute('UPDATE fascicoli SET dati_json=?,id_cliente=? WHERE id=?',
                         (json.dumps(payload), 'C3', 'F1'))
    commit(backend)
    assert [case.id for case in manager.cerca(id_cliente='C3')] == ['F1']
    assert 'F1' not in [case.id for case in manager.cerca(id_cliente='C1')]
    backend.conn.execute('DELETE FROM fascicoli WHERE id=?', ('F1',))
    if getattr(backend, 'backend_kind', '') == 'postgresql':
        backend.raw_conn.rollback()
    else:
        backend.conn.rollback()
    assert [case.id for case in manager.cerca(id_cliente='C3')] == ['F1']
    backend.conn.execute('DELETE FROM fascicoli WHERE id=?', ('F1',))
    commit(backend)
    assert manager.cerca(id_cliente='C3') == []


def test_an_invalid_requested_matter_is_an_error_not_a_confirmed_empty_list(indexed_cases):
    manager, backend = indexed_cases
    prepare(backend)
    backend.conn.execute('UPDATE fascicoli SET documenti_json=? WHERE id=?', ('{broken', 'F1'))
    commit(backend)
    with pytest.raises(RuntimeError, match='non coerenti'):
        manager.cerca(id_cliente='C1')


def test_corrupt_owner_metadata_is_visible_as_an_error_for_the_relevant_client(indexed_cases):
    manager, backend = indexed_cases
    prepare(backend)
    with pytest.raises(RuntimeError, match='non coerenti'):
        manager.cerca(id_cliente='C-bad')
    # Non si deve attribuire il fascicolo sulla sola colonna di appoggio.
    assert 'F7' not in manager._fascicoli
    assert [case.id for case in manager.cerca(id_cliente='C2')] == ['F5']


@pytest.mark.parametrize('raw', ['null', '[]', '"source"', '42'])
def test_non_object_owner_metadata_cannot_become_a_confirmed_empty_list(indexed_cases, raw):
    manager, backend = indexed_cases
    prepare(backend)
    backend.conn.execute('UPDATE fascicoli SET dati_json=? WHERE id=?', (raw, 'F7'))
    commit(backend)
    with pytest.raises(RuntimeError, match='non coerenti'):
        manager.cerca(id_cliente='C-bad')


def test_new_studio_prepares_the_catalog_before_any_customer_page(tmp_path):
    from pct.tenant import GestioneTenant
    from pct.fascicoli_clienti_index import INDEX_VERSION

    registry = GestioneTenant(str(tmp_path / 'tenants.json'))
    studio = registry.crea(nome='Studio sintetico catalogo SQL', slug='catalogo-controllato')
    paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
    with sqlite3.connect(paths['STUDIO_DB']) as conn:
        assert conn.execute('SELECT valore FROM _meta WHERE chiave=?',
                            ('fascicoli_clienti_index',)).fetchone() == (INDEX_VERSION,)
        assert conn.execute('SELECT COUNT(*) FROM fascicoli_clienti_lookup').fetchone() == (0,)
    assert registry.provision_storage_backend(studio.slug)['client_case_catalog_changed'] is False


def test_postgres_provision_prepares_native_core_and_catalog_before_activation(tmp_path, monkeypatch):
    if not os.environ.get('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato')
    from psycopg2.extensions import make_dsn
    from pct.tenant import GestioneTenant, DatabaseConfig, DbMode
    from pct.fascicoli_clienti_index import INDEX_VERSION

    factory = SQLFactory('postgresql')
    store = None
    try:
        dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
        registry = GestioneTenant(str(tmp_path / 'tenants.json'))
        studio = registry.crea(nome='Studio sintetico PG', slug='catalogo-postgres')
        registry.aggiorna_db_config(studio.slug, DatabaseConfig(
            mode=DbMode.POSTGRESQL, host='controlled', db_name='controlled',
            utente='controlled', connessione_ok=True))
        def selected_config(config):
            assert config.normalized_mode == DbMode.POSTGRESQL
            assert not config.core_runtime_enabled
            return dsn
        monkeypatch.setattr('pct.postgres_runtime_support.database_config_to_dsn', selected_config)
        report = registry.provision_storage_backend(studio.slug, activate_external=True)
        assert report['ok'] and report['activated']
        assert registry.get(studio.slug).database.core_runtime_enabled
        store = PostgresStudioDB.get(dsn)
        assert store.conn.execute('SELECT valore FROM _meta WHERE chiave=?',
            ('fascicoli_clienti_index',)).fetchone()['valore'] == INDEX_VERSION
        assert store.conn.execute('SELECT COUNT(*) AS n FROM fascicoli_clienti_lookup').fetchone()['n'] == 0
    finally:
        if store is not None:
            store.chiudi()
        factory.close()
