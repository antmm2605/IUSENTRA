"""Guardrail su database controllati, mai sui dati operativi dello studio."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from pct.condivisioni_repository import CondivisioniConflict, CondivisioniRepository
from pct.condivisione import GestioneCondivisioni, RuoloCondivisione


class SQLFactory:
    def __init__(self, backend):
        self.backend = backend
        self.temp = tempfile.TemporaryDirectory()
        self.connections = []
        self.schema = "test_condivisioni_" + uuid.uuid4().hex
        if backend == "postgresql":
            import psycopg2
            from psycopg2 import sql
            self.pg_parameters = {
                "host": os.environ.get("CONDIVISIONI_TEST_PG_HOST", "audit-postgres"),
                "dbname": os.environ.get("AUDIT_POSTGRES_DB", "iusentra_audit"),
                "user": os.environ.get("AUDIT_POSTGRES_USER", "iusentra_audit"),
                "password": os.environ["AUDIT_POSTGRES_PASSWORD"],
            }
            self.admin = psycopg2.connect(**self.pg_parameters)
            self.admin.autocommit = True
            with self.admin.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        try:
            db = self.new()
            db.conn.execute("CREATE TABLE moduli_dati (nome TEXT PRIMARY KEY)")
            db.conn.execute("CREATE TABLE moduli_json_records (modulo TEXT,record_key TEXT,payload_json TEXT)")
            db.conn.execute("INSERT INTO moduli_dati (nome) VALUES (?)", ("condivisioni",))
            self.commit(db)
        except Exception:
            self.close()
            raise

    def new(self):
        if self.backend == "sqlite":
            raw = sqlite3.connect(str(Path(self.temp.name) / "controlled.db"))
            db = SimpleNamespace(conn=raw)
        else:
            import psycopg2
            from pct.storage_postgres import PostgresCompatConnection
            raw = psycopg2.connect(**self.pg_parameters, options=f"-c search_path={self.schema}")
            db = SimpleNamespace(raw_conn=raw)
            db.conn = PostgresCompatConnection(db)
        self.connections.append(raw)
        return db

    @staticmethod
    def commit(db):
        (getattr(db, "raw_conn", None) or db.conn).commit()

    def close(self):
        for conn in self.connections:
            conn.close()
        if self.backend == "postgresql":
            from psycopg2 import sql
            assert self.schema.startswith("test_condivisioni_") and len(self.schema) == 50
            with self.admin.cursor() as cur:
                cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
            self.admin.close()
        self.temp.cleanup()


class RepositoryChecks(unittest.TestCase):
    backend = "sqlite"

    @classmethod
    def setUpClass(cls):
        cls.factory = SQLFactory(cls.backend)

    @classmethod
    def tearDownClass(cls):
        cls.factory.close()

    def setUp(self):
        self.tenant = uuid.uuid4().hex
        self.path = Path(self.factory.temp.name) / f"{self.tenant}.json"

    def repo(self, tenant=None):
        repo = CondivisioniRepository(self.factory.new(), tenant or self.tenant, self.path)
        repo.load()
        return repo

    @staticmethod
    def data(**items):
        return {"cartelle": items, "fascicoli": {}, "link": {}}

    def test_sql_empty_never_adopts_stale_json(self):
        self.path.write_text(json.dumps(self.data(stale={"version": 99})))
        self.assertEqual(self.repo().load(), self.data())

    def test_sql_remains_primary_after_mirror_changes(self):
        self.repo().save(self.data(current={"version": 1}))
        self.path.write_text(json.dumps(self.data(stale={"version": 99})))
        self.assertEqual(self.repo().load(), self.data(current={"version": 1}))

    def test_same_record_conflict_preserves_latest(self):
        self.repo().save(self.data(case={"version": 1}))
        first, second = self.repo(), self.repo()
        first.save(self.data(case={"version": 2}))
        with self.assertRaises(CondivisioniConflict):
            second.save(self.data(case={"version": 3}))
        self.assertEqual(self.repo().load()["cartelle"]["case"]["version"], 2)

    def test_independent_changes_merge_without_lost_access(self):
        first, second = self.repo(), self.repo()
        first.save(self.data(first={"version": 1}))
        second.save(self.data(second={"version": 1}))
        self.assertEqual(set(self.repo().load()["cartelle"]), {"first", "second"})

    def test_conflict_rolls_back_entire_command(self):
        self.repo().save(self.data(case={"version": 1}))
        first, second = self.repo(), self.repo()
        first.save(self.data(case={"version": 2}))
        with self.assertRaises(CondivisioniConflict):
            second.save(self.data(case={"version": 3}, added={"version": 1}))
        self.assertEqual(self.repo().load(), self.data(case={"version": 2}))

    def test_tenant_isolation(self):
        self.repo().save(self.data(private={"version": 1}))
        self.assertEqual(self.repo(uuid.uuid4().hex).load(), self.data())

    def test_sql_failure_does_not_read_mirror(self):
        repo = self.repo()
        self.path.write_text(json.dumps(self.data(stale={"version": 99})))
        repo.db.conn.execute("INSERT INTO condivisioni_records VALUES (?,?,?,?,?)", (self.tenant,"cartelle","broken","invalid","now"))
        self.factory.commit(repo.db)
        with self.assertRaises(json.JSONDecodeError):
            repo.load()

    def test_manager_grant_revoke_and_links_keep_domain_behavior(self):
        db = self.factory.new()
        manager = GestioneCondivisioni(str(self.path), "controlled-test-secret", studio_db=db, tenant_key=self.tenant)
        manager.condividi("controlled-client", "controlled-user", "prova", "Collaboratore prova", RuoloCondivisione.LETTURA, "prova")
        again = GestioneCondivisioni(str(self.path), "controlled-test-secret", studio_db=self.factory.new(), tenant_key=self.tenant)
        self.assertTrue(again.ha_accesso("controlled-user", "controlled-client"))
        self.assertFalse(again.ha_accesso("controlled-user", "controlled-client", RuoloCondivisione.SCRITTURA))
        self.assertTrue(again.revoca("controlled-client", "controlled-user"))
        token, link = again.crea_link_temporaneo("controlled-client", "prova")
        self.assertIsNotNone(again.verifica_link_temporaneo(token))
        self.assertTrue(again.revoca_link_temporaneo(link.id))
        self.assertIsNone(again.verifica_link_temporaneo(token))


if __name__ == "__main__":
    if "--postgresql" in sys.argv:
        sys.argv.remove("--postgresql")
        RepositoryChecks.backend = "postgresql"
    unittest.main(verbosity=2)
