"""Consultazioni isolate sui backend nativi, senza inizializzare dati reali."""
import os
import sqlite3
from types import SimpleNamespace

import pytest

from pct.core_storage_backend import build_core_storage_backend
from pct.storage import StudioDB
from pct.storage_postgres import PostgresStudioDB
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def controlled_reader(request, monkeypatch):
    kind = request.param
    if kind == 'postgresql' and not os.environ.get('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato in questa esecuzione.')
    factory = SQLFactory(kind)
    reader = None
    try:
        writer = factory.new()
        writer.conn.execute('CREATE TABLE proof_rows (id TEXT PRIMARY KEY, value TEXT NOT NULL)')
        writer.conn.execute('INSERT INTO proof_rows VALUES (?,?)', ('one', 'alpha'))
        SQLFactory.commit(writer)

        def forbidden(*args, **kwargs):
            raise AssertionError('Una consultazione non prepara o aggiorna lo schema')

        if kind == 'sqlite':
            monkeypatch.setattr(StudioDB, '_ensure_schema', forbidden)
            monkeypatch.setattr(StudioDB, '_configure_journal_mode', forbidden)
            reader = StudioDB(str(factory.temp.name) + '/controlled.db', initialize_schema=False, readonly=True)
            blocked_write = sqlite3.OperationalError
        else:
            import psycopg2
            from psycopg2.extensions import make_dsn

            monkeypatch.setattr(PostgresStudioDB, '_ensure_schema', forbidden)
            dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
            reader = PostgresStudioDB(dsn, initialize_schema=False, readonly=True)
            blocked_write = psycopg2.errors.ReadOnlySqlTransaction
        yield reader, writer, blocked_write
    finally:
        if reader is not None:
            reader.chiudi()
        factory.close()


def test_reader_reads_but_cannot_change_persisted_rows(controlled_reader):
    reader, writer, blocked_write = controlled_reader
    assert reader.conn.execute('SELECT value FROM proof_rows WHERE id=?', ('one',)).fetchone()[0] == 'alpha'
    with pytest.raises(blocked_write):
        reader.conn.execute('INSERT INTO proof_rows VALUES (?,?)', ('two', 'forbidden'))
    assert writer.conn.execute('SELECT COUNT(*) FROM proof_rows').fetchone()[0] == 1


def test_closing_reader_does_not_change_writer_session(controlled_reader):
    reader, writer, _ = controlled_reader
    reader.conn.execute('SELECT value FROM proof_rows').fetchall()
    reader.chiudi()
    writer.conn.execute('UPDATE proof_rows SET value=? WHERE id=?', ('beta', 'one'))
    SQLFactory.commit(writer)
    assert reader.conn.execute('SELECT value FROM proof_rows WHERE id=?', ('one',)).fetchone()[0] == 'beta'


def test_missing_sqlite_stays_missing(tmp_path):
    path = tmp_path / 'missing.db'
    reader = StudioDB(str(path), initialize_schema=False, readonly=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            reader.conn.execute('SELECT 1')
        with pytest.raises(PermissionError):
            reader._conn_per_scrittura()
        assert not path.exists()
    finally:
        reader.chiudi()


@pytest.mark.parametrize('backend,anchor', [(StudioDB, 'unused.db'), (PostgresStudioDB, 'unused-dsn')])
def test_readonly_never_initializes_schema(backend, anchor):
    if backend is None:
        pytest.skip('Backend PostgreSQL sostituito dagli stub unitari: serve lo stack nativo.')
    with pytest.raises(ValueError, match='inizializzare'):
        backend(anchor, readonly=True)


def test_default_writer_and_readonly_factory_are_separate(tmp_path):
    path = str(tmp_path / 'controlled.db')
    config = SimpleNamespace(mode='SQLITE')
    writer = build_core_storage_backend(config, studio_db_path=path)
    writer.conn.execute('CREATE TABLE proof_rows (id TEXT PRIMARY KEY)')
    writer.conn.execute('INSERT INTO proof_rows VALUES (?)', ('first',))
    writer.conn.commit()
    reader = build_core_storage_backend(config, studio_db_path=path, readonly=True)
    try:
        assert reader is not writer
        assert reader.conn.execute('SELECT id FROM proof_rows').fetchone()[0] == 'first'
        with pytest.raises(PermissionError):
            reader._conn_per_scrittura()
    finally:
        reader.chiudi()
    writer.conn.execute('INSERT INTO proof_rows VALUES (?)', ('second',))
    writer.conn.commit()
    assert writer.conn.execute('SELECT COUNT(*) FROM proof_rows').fetchone()[0] == 2
    writer.chiudi()
