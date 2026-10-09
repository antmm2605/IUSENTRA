"""Selezione su archivi controllati, non accettazione del browser reale."""
import sqlite3
from types import SimpleNamespace

import pytest

from pct.prima_nota_repository import PrimaNotaRepository
from pct.prima_nota_transition import prima_nota_source_lock, prepare_transition_locked, commit_transition_locked
from web.services.prima_nota_runtime import open_prima_nota_runtime


def test_legacy_senza_fence_non_apre_sql(tmp_path):
    def forbidden(*args):
        pytest.fail('Nessuna apertura SQL prima della transizione')
    path = tmp_path / 'studio.db'
    with sqlite3.connect(path):
        pass
    ledger = open_prima_nota_runtime(tmp_path / 'source.json', anchor='clienti.json', tenant_key='studio-test', actor_key='',
                                    get_profile=lambda _: SimpleNamespace(uses_sqlite=True, studio_db_path=str(path)), get_database=forbidden)
    assert ledger.registro() == []


def test_fence_perso_non_riapre_json_adottato(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b'fonte-storica-non-leggere')
    path = tmp_path / 'studio.db'
    with sqlite3.connect(path) as conn:
        repo = PrimaNotaRepository(SimpleNamespace(conn=conn), 'studio-test')
        repo.ensure_schema()
        repo.initialize({}, source_sha256='a' * 64, backup_reference='backup-controllato')
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match='assente dopo adozione SQL'):
        open_prima_nota_runtime(source, anchor='clienti.json', tenant_key='studio-test', actor_key='attore-test',
                               get_profile=lambda _: SimpleNamespace(uses_sqlite=True, studio_db_path=str(path)),
                               get_database=lambda _: pytest.fail('Nessun bootstrap'))
    assert source.read_bytes() == b'fonte-storica-non-leggere'
    assert path.read_bytes() == before


def test_backend_sqlite_esistente_non_crea_schema_ne_file(tmp_path, monkeypatch):
    from pct.storage import StudioDB
    monkeypatch.setattr(StudioDB, '_ensure_schema', lambda _: pytest.fail('Nessun DDL nella richiesta'))
    path = tmp_path / 'studio.db'
    db = StudioDB(str(path), initialize_schema=False)
    with pytest.raises(sqlite3.OperationalError):
        db.conn.execute('SELECT 1')
    assert not path.exists()
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE prova (importo INTEGER)')
        conn.execute('INSERT INTO prova VALUES (260)')
        conn.commit()
    try:
        assert db.conn.execute('SELECT importo FROM prova').fetchone()[0] == 260
        assert [row[0] for row in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")] == ['prova']
    finally:
        db.chiudi()


def test_connessione_prima_nota_chiusa_anche_dopo_errore(tmp_path, monkeypatch):
    from flask import Flask, g
    from web.services.prima_nota_runtime import get_existing_prima_nota_database, close_prima_nota_database
    import web.services.storage_runtime as storage_runtime
    path = tmp_path / 'studio.db'
    with sqlite3.connect(path):
        pass
    monkeypatch.setattr(storage_runtime, 'get_request_storage_runtime', lambda _: SimpleNamespace(uses_sqlite=True, studio_db_path=str(path)))
    with Flask(__name__).test_request_context('/'):
        db = get_existing_prima_nota_database('clienti.json')
        connection = db.conn
        with pytest.raises(sqlite3.OperationalError):
            connection.execute('SELECT * FROM tabella_assente')
        close_prima_nota_database()
        assert '_prima_nota_owned_database' not in g
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            connection.execute('SELECT 1')
        close_prima_nota_database()


@pytest.mark.parametrize('kind', ['assente', 'corrotto'])
def test_fence_assente_sql_non_verificabile_non_legge_json(tmp_path, kind):
    source = tmp_path / 'source.json'
    source.write_bytes(b'fonte-storica-non-leggere')
    path = tmp_path / 'studio.db'
    if kind == 'corrotto':
        path.write_bytes(b'non-un-database')
    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        open_prima_nota_runtime(source, anchor='clienti.json', tenant_key='studio-test', actor_key='attore-test',
                               get_profile=lambda _: SimpleNamespace(uses_sqlite=True, studio_db_path=str(path)),
                               get_database=lambda _: pytest.fail('Nessun bootstrap'))
    assert source.read_bytes() == b'fonte-storica-non-leggere'
    assert path.exists() == (kind == 'corrotto')


@pytest.mark.parametrize('tenant,phase', [('altro', 'committed'), ('', 'committed'), ('studio-test', 'prepared')])
def test_fence_discordante_non_apre_database(tmp_path, tenant, phase):
    source = tmp_path / 'source.json'
    with prima_nota_source_lock(source):
        prepare_transition_locked(source, tenant='studio-test', source_sha256='a' * 64)
        if phase == 'committed':
            commit_transition_locked(source, tenant='studio-test', source_sha256='a' * 64)
    def forbidden(*args):
        pytest.fail('Nessuna apertura SQL su contesto discordante')
    with pytest.raises(RuntimeError):
        open_prima_nota_runtime(source, anchor='clienti.json', tenant_key=tenant, actor_key='attore-test', get_profile=forbidden, get_database=forbidden)


@pytest.mark.parametrize('database_exists', [False, True])
def test_sqlite_assente_o_vuoto_non_bootstrap(tmp_path, database_exists):
    source = tmp_path / 'source.json'
    path = tmp_path / 'studio.db'
    if database_exists:
        with sqlite3.connect(path):
            pass
    with prima_nota_source_lock(source):
        prepare_transition_locked(source, tenant='studio-test', source_sha256='a' * 64)
        commit_transition_locked(source, tenant='studio-test', source_sha256='a' * 64)
    before = path.read_bytes() if path.exists() else None
    def forbidden(*args):
        pytest.fail('Il bootstrap non deve essere chiamato')
    with pytest.raises(RuntimeError, match='nessun bootstrap'):
        open_prima_nota_runtime(source, anchor=tmp_path / 'clienti' / 'anagrafica.json', tenant_key='studio-test', actor_key='attore-test',
                               get_profile=lambda _: SimpleNamespace(uses_sqlite=True, studio_db_path=str(path)), get_database=forbidden)
    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize('sha', ['a' * 64, 'b' * 64])
def test_sqlite_nativo_seleziona_solo_marker_concordante(tmp_path, sha):
    source = tmp_path / 'source.json'
    source.write_bytes(b'fonte-storica-non-rileggere')
    path = tmp_path / 'studio.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE settings_config (key TEXT)')
        conn.execute("INSERT INTO settings_config VALUES ('profilo-controllato')")
        conn.commit()
        db = SimpleNamespace(conn=conn)
        repo = PrimaNotaRepository(db, 'studio-test')
        repo.ensure_schema()
        repo.initialize({}, source_sha256=sha, backup_reference='backup-controllato')
        with prima_nota_source_lock(source):
            prepare_transition_locked(source, tenant='studio-test', source_sha256='a' * 64)
            commit_transition_locked(source, tenant='studio-test', source_sha256='a' * 64)
        args = dict(anchor=tmp_path / 'clienti' / 'anagrafica.json', tenant_key='studio-test', actor_key='attore-test',
                    get_profile=lambda _: SimpleNamespace(uses_sqlite=True, studio_db_path=str(path)), get_database=lambda _: db)
        if sha != 'a' * 64:
            with pytest.raises(RuntimeError, match='discordante'):
                open_prima_nota_runtime(source, **args)
        else:
            ledger = open_prima_nota_runtime(source, **args)
            ledger.registra(importo=260)
            assert ledger._repository.actor_key == 'attore-test'
            assert ledger._repository.revision == 1
        assert source.read_bytes() == b'fonte-storica-non-rileggere'
