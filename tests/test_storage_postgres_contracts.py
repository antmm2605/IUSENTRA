"""Contratti DB-API PostgreSQL: sessioni, transazioni e profili, senza dati reali."""
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

# Caricare il sorgente reale in un oggetto isolato: il conftest Lex può avere
# registrato un modulo sostitutivo globale. Non promuoverlo a prova del backend.
spec = importlib.util.spec_from_file_location("pct.storage_postgres", Path(__file__).resolve().parents[1] / "pct/storage_postgres.py")
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


@pytest.fixture(autouse=True)
def controlled_driver(monkeypatch):
    driver = SimpleNamespace(connect=lambda dsn: None, extras=SimpleNamespace(RealDictCursor=object))
    monkeypatch.setattr(storage, "psycopg2", driver)


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=()):
        self.connection.calls.append((sql, tuple(params)))
        self.rows = self.connection.respond(sql, tuple(params))
        self.description = bool(self.rows)

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, respond=None):
        self.calls = []
        self.respond = respond or (lambda sql, params: [])
        self.commits = self.rollbacks = self.closed = 0
        self.readonly = None

    def cursor(self, **kwargs):
        return Cursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1

    def set_session(self, *, readonly):
        self.readonly = readonly


def backend(monkeypatch, connection, **kwargs):
    monkeypatch.setattr(storage.psycopg2, "connect", lambda dsn: connection)
    return storage.PostgresStudioDB("controlled-not-a-server", initialize_schema=False, **kwargs)


def test_dsn_encodes_credentials_and_ssl():
    assert storage.build_postgres_dsn(host="localhost", port=5432, db_name="studio prova", user="a+b", password="p@ss", ssl=True) == "postgresql://a%2Bb:p%40ss@localhost:5432/studio+prova?sslmode=require"


def test_compatibility_preserves_parameters_and_rows(monkeypatch):
    connection = Connection(lambda sql, params: [{"id": params[0], "value": "record"}] if sql.startswith("SELECT") else [])
    db = backend(monkeypatch, connection)
    result = db.conn.execute("SELECT id,value FROM items WHERE id=?", ["separate-id"])
    assert result.fetchone()[0] == "separate-id"
    assert result.fetchone()["value"] == "record"
    assert list(result) == result.fetchall()
    assert connection.calls[-1] == ("SELECT id,value FROM items WHERE id=%s", ("separate-id",))
    assert db.conn.execute("BEGIN;").fetchone() is None
    db.conn.execute("COMMIT")
    db.conn.execute("ROLLBACK;")
    assert (connection.commits, connection.rollbacks) == (1, 1)
    assert db.conn.execute("UPDATE items SET value=?", ["other"]).fetchall() == []


def test_readonly_session_is_cached_and_closed(monkeypatch):
    connection = Connection(lambda sql, params: [{"id": "one"}])
    db = backend(monkeypatch, connection, readonly=True)
    assert db.raw_conn is db.raw_conn and connection.readonly is True
    assert db.fetchall_readonly("SELECT id FROM items") == [{"id": "one"}]
    db.chiudi()
    db.chiudi()
    assert connection.closed == 1
    assert db.raw_conn is connection
    db.chiudi()
    assert connection.closed == 2


def test_readonly_session_failure_closes_connection(monkeypatch):
    connection = Connection()
    def reject(**kwargs):
        raise PermissionError("session not accepted")
    connection.set_session = reject
    db = backend(monkeypatch, connection, readonly=True)
    with pytest.raises(PermissionError):
        _ = db.raw_conn
    assert connection.closed == 1
    assert not hasattr(db._local, "_conn")


def test_metadata_pragma_and_json_rows(monkeypatch):
    def respond(sql, params):
        if "information_schema.columns" in sql:
            return [{"column_name": "id"}, {"column_name": "dati_json"}]
        if "COUNT(*)" in sql:
            return [{"n": 2}]
        return [{"dati_json": '{"id":"one"}'}, {"dati_json": "invalid", "id": "preserved"}]
    db = backend(monkeypatch, Connection(respond))
    assert db.table_columns("items") == ["id", "dati_json"]
    columns = db.conn.execute("PRAGMA table_info('items')").fetchall()
    assert [x["name"] for x in columns] == ["id", "dati_json"]
    assert [x["pk"] for x in columns] == [1, 0]
    assert db.conn.execute("PRAGMA journal_mode").fetchall() == []
    assert db.carica_tabella("items") == [{"id": "one"}, {"dati_json": "invalid", "id": "preserved"}]
    assert db.ha_dati("items") is True
    db.raw_conn.respond = lambda sql, params: []
    assert db.ha_dati("items") is False
    def failure(sql, params):
        raise RuntimeError("query failed")
    db.raw_conn.respond = failure
    assert db.carica_tabella("items") == [] and db.ha_dati("items") is False


def test_save_commits_once_after_receipt_and_rolls_back_failures(monkeypatch):
    connection = Connection()
    db = backend(monkeypatch, connection)
    seen = []
    def insert(conn, row):
        conn.execute("INSERT INTO items VALUES (?)", (row,))
    db.salva_tabella("items", ["one", "two"], insert, before_commit=lambda conn: seen.append(connection.commits))
    assert seen == [0] and connection.commits == 1
    assert connection.calls[0][0] == "DELETE FROM items"
    connection.calls.clear()
    def receipt_failure(conn):
        raise RuntimeError("receipt rejected")
    with pytest.raises(RuntimeError, match="receipt rejected"):
        db.salva_tabella("items", ["three"], insert, delete_all=False, before_commit=receipt_failure)
    assert connection.commits == 1 and connection.rollbacks == 1
    assert not any(sql.startswith("DELETE") for sql, params in connection.calls)


def test_schema_preparation_is_explicit_and_records_backend(monkeypatch):
    connection = Connection()
    db = backend(monkeypatch, connection)
    monkeypatch.setattr(db, "_backfill_deposit_profiles", lambda conn: None)
    db._ensure_schema()
    assert connection.commits == 1
    assert connection.calls[0][0] == storage.CORE_POSTGRES_SCHEMA_SQL
    assert connection.calls[-1][1] == ("backend", "postgresql")
    storage._instances.clear()
    monkeypatch.setattr(storage.PostgresStudioDB, "_ensure_schema", lambda self: None)
    import pct.operational_live as live
    import pct.email_mailbox_query_events as events
    monkeypatch.setattr(live, "ensure_live_schema", lambda conn, **kwargs: None)
    monkeypatch.setattr(events, "install_query_events", lambda conn, **kwargs: None)
    assert storage.PostgresStudioDB.get("controlled-cache") is storage.PostgresStudioDB.get("controlled-cache")
    storage._instances.clear()


@pytest.mark.parametrize("payload_column", [False, True])
def test_profile_backfill_preserves_identity_and_payload(monkeypatch, payload_column):
    import pct.deposito_profile_backfill as profiles
    monkeypatch.setattr(profiles, "CORE_DEPOSIT_PROFILE_TABLES", [("fascicoli", "id")])
    monkeypatch.setattr(profiles, "build_deposit_profile_for_record", lambda *args, **kwargs: ({"state": "new"}, {"id": "case-one", "keep": "value"}))
    monkeypatch.setattr(profiles, "deposit_profile_needs_update", lambda old, new: old != new)
    monkeypatch.setattr(profiles, "merge_profile_into_payload", lambda payload, profile: dict(payload, profile=profile))
    columns = ["id", "profilo_deposito_json"] + (["dati_json"] if payload_column else [])
    records = [{"id": "", "profilo_deposito_json": "{}"}, {"id": "case-one", "profilo_deposito_json": "invalid"}, {"id": "already", "profilo_deposito_json": '{"state":"new"}'}]
    def respond(sql, params):
        if "information_schema" in sql:
            return [{"column_name": name} for name in columns]
        return records if sql.startswith("SELECT *") else []
    connection = Connection(respond)
    db = backend(monkeypatch, connection)
    db.repair_deposit_profiles()
    updates = [(sql, values) for sql, values in connection.calls if sql.strip().startswith("UPDATE")]
    assert len(updates) == 1 and updates[0][1][-1] == "case-one"
    assert json.loads(updates[0][1][0]) == {"state": "new"}
    if payload_column:
        assert json.loads(updates[0][1][1])["keep"] == "value"
    assert connection.commits == 1
