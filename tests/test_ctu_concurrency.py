"""Due connessioni native: CAS e replay senza scritture sui dati dello studio."""
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest

from pct.ctu import IncaricoCtu
from pct.ctu_repository import CtuConflict, CtuRejected, CtuRepository


@pytest.fixture
def connections(tmp_path):
    schema = "ctu_test_" + uuid4().hex
    postgres = os.environ.get("CTU_TEST_POSTGRES") == "1"

    def connect():
        if postgres:
            import psycopg2
            from psycopg2 import sql
            from pct.storage_postgres import PostgresCompatConnection
            raw = psycopg2.connect(host=os.environ.get("CTU_TEST_PG_HOST", "audit-postgres"),
                dbname=os.environ.get("AUDIT_POSTGRES_DB", "iusentra_audit"),
                user=os.environ.get("AUDIT_POSTGRES_USER", "iusentra_audit"),
                password=os.environ["AUDIT_POSTGRES_PASSWORD"])
            with raw.cursor() as cursor:
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            raw.commit()
            db = SimpleNamespace(raw_conn=raw)
            db.conn = PostgresCompatConnection(db)
            return db, raw
        raw = sqlite3.connect(tmp_path / "concorrenza.db", timeout=15)
        return SimpleNamespace(conn=raw), raw

    db, raw = connect()
    try:
        if postgres:
            from psycopg2 import sql
            with raw.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            raw.commit()
        CtuRepository(db, "prova", actor_key="prova").ensure_schema()
        db.conn.execute("CREATE TABLE audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                        "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
        raw.commit()
        CtuRepository(db, "prova", actor_key="prova").initialize({}, source_sha256="a" * 64, backup_reference="controllato")
        yield connect
    finally:
        if postgres:
            raw.rollback()
            with raw.cursor() as cursor:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            raw.commit()
        raw.close()


@pytest.mark.parametrize("same_command", [False, True])
def test_concorrenza_reale_preserva_un_solo_esito(connections, same_command):
    barrier = Barrier(2)
    items = [IncaricoCtu(fascicolo_id="F1", nome_ctu="Prova").to_dict() for _ in range(2)]
    keys = [str(uuid4()) for _ in range(2)]
    if same_command:
        items[1], keys[1] = items[0], keys[0]

    def write(index):
        db, raw = connections()
        try:
            repo = CtuRepository(db, "prova", actor_key="prova")
            repo.load()
            command = repo.command(keys[index], "nuovo", {"nome": "Prova"}, 0)
            barrier.wait(timeout=10)
            try:
                return repo.save({items[index]["id"]: items[index]}, command=command)
            except CtuConflict:
                return "conflitto"
        finally:
            raw.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, range(2)))
    if same_command:
        assert results[0] == results[1] and results[0]["revision"] == 1
    else:
        assert results.count("conflitto") == 1
    db, raw = connections()
    try:
        assert db.conn.execute("SELECT revision FROM ctu_state").fetchone()[0] == 1
        for table in ("ctu_records", "ctu_commands"):
            assert db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1
        assert db.conn.execute("SELECT COUNT(*) FROM ctu_audit WHERE revision=1").fetchone()[0] == 1
        assert db.conn.execute("SELECT COUNT(*) FROM audit_log WHERE azione='ctu.nuovo'").fetchone()[0] == 1
    finally:
        raw.close()


def test_rifiuto_e_scrittura_concorrenti_hanno_un_solo_esito(connections):
    barrier = Barrier(2)
    key = str(uuid4())
    item = IncaricoCtu(fascicolo_id="F1", nome_ctu="Prova").to_dict()

    def attempt(reject):
        db, raw = connections()
        try:
            repo = CtuRepository(db, "prova", actor_key="prova")
            repo.load()
            cmd = repo.command(key, "nuovo", {"nome": "Prova"}, 0)
            barrier.wait(timeout=10)
            try:
                return repo.reject(cmd, code="validation", message="Dati non validi.") if reject else repo.save({item["id"]: item}, command=cmd)
            except CtuRejected as exc:
                return exc.result
        finally:
            raw.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, [True, False]))
    assert results[0] == results[1]
    db, raw = connections()
    try:
        successes = db.conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0]
        rejections = db.conn.execute("SELECT COUNT(*) FROM ctu_command_rejections").fetchone()[0]
        assert successes + rejections == 1
        assert db.conn.execute("SELECT COUNT(*) FROM ctu_records").fetchone()[0] == successes
        assert db.conn.execute("SELECT revision FROM ctu_state").fetchone()[0] == successes
    finally:
        raw.close()
