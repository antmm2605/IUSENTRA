"""La cattura deve condividere commit e rollback con il repository nativo."""
import pytest

from pct.offline_change_log import append_change, ensure_schema, read_changes
from pct.storage import StudioDB


def test_postgres_owner_keeps_callback_inside_its_commit_and_rollback():
    """Banco SQL locale del confine transazionale, non prova del dialetto PG.

    La parità del dialetto è provata separatamente con PostgreSQL reale.
    Qui si verifica che il proprietario PostgreSQL non confermi anticipatamente
    il dato applicativo quando il registro della stessa operazione fallisce.
    """
    import sqlite3
    import importlib.util
    from contextlib import closing
    from pathlib import Path
    from types import SimpleNamespace

    # conftest può predisporre uno stub Lex del modulo PostgreSQL: caricare il
    # sorgente proprietario sotto un alias privato, senza alterare gli stub
    # condivisi degli altri test né richiedere una connessione esterna.
    source = Path(__file__).resolve().parents[1] / 'pct/storage_postgres.py'
    spec = importlib.util.spec_from_file_location('controlled_postgres_atomic_owner', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    PostgresStudioDB = module.PostgresStudioDB

    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE controlled_changes(id TEXT PRIMARY KEY)')
    raw = SimpleNamespace(cursor=lambda: closing(connection.cursor()),
                          commit=connection.commit, rollback=connection.rollback)
    owner = SimpleNamespace(conn=connection, raw_conn=raw)

    def write(conn, key):
        conn.execute('INSERT INTO controlled_changes(id) VALUES (?)', (key,))

    def fail(conn):
        assert conn.in_transaction
        write(conn, 'journal-unconfirmed')
        raise ValueError('Registro non confermato')

    try:
        with pytest.raises(ValueError, match='Registro non confermato'):
            PostgresStudioDB.salva_tabella(owner, 'controlled_changes', ['business-unconfirmed'], write,
                                          delete_all=False, before_commit=fail)
        assert list(connection.execute('SELECT id FROM controlled_changes')) == []
        PostgresStudioDB.salva_tabella(owner, 'controlled_changes', ['business-confirmed'], write,
                                      delete_all=False, before_commit=lambda conn: write(conn, 'journal-confirmed'))
        assert not connection.in_transaction
        assert {row[0] for row in connection.execute('SELECT id FROM controlled_changes')} == {
            'business-confirmed', 'journal-confirmed'}
    finally:
        connection.close()


def test_native_save_and_sync_record_commit_or_rollback_together(tmp_path):
    backend = StudioDB(str(tmp_path / "studio.db"))
    conn = backend.conn
    ensure_schema(conn)
    conn.commit()

    def insert(connection, row):
        connection.execute("INSERT INTO clienti(id,dati_json) VALUES (?,?)", row)

    def journal(connection):
        append_change(connection, tenant="studio-a", operation_id="op-1", domain="clienti",
                      resource_id="c-1", actor="test", source_device="pc-test", base_revision="",
                      content={"after": {"id": "c-1"}}, allowed_domains=frozenset({"clienti"}))

    def fail_after_journal(connection):
        journal(connection)
        raise ValueError("Errore prima del commit")

    def page():
        return read_changes(conn, tenant="studio-a", after=0, domains=frozenset({"clienti"}),
                            authorized_resource=lambda domain, resource: True)

    try:
        with pytest.raises(ValueError, match="prima del commit"):
            backend.salva_tabella("clienti", [("c-1", '{"id":"c-1"}')], insert,
                                  delete_all=False, before_commit=fail_after_journal)
        assert conn.execute("SELECT id FROM clienti WHERE id='c-1'").fetchone() is None
        assert page()["items"] == []
        backend.salva_tabella("clienti", [("c-1", '{"id":"c-1"}')], insert,
                              delete_all=False, before_commit=journal)
        assert conn.execute("SELECT id FROM clienti WHERE id='c-1'").fetchone()[0] == "c-1"
        assert page()["items"][0]["resource_id"] == "c-1"
    finally:
        backend.chiudi()
