"""Synthetic SQL/device/case data only. Shardable, no archive access."""

import base64
import os
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from pct.offline.crypto import digest
from pct.offline.notes import NoteSync

PG_DATABASES = []


@pytest.fixture(autouse=True)
def release_synthetic_postgres():
    yield
    for raw, schema in PG_DATABASES:
        from psycopg2 import sql

        raw.rollback()
        with raw.cursor() as cursor:
            cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        raw.commit()
        raw.close()
    PG_DATABASES.clear()


def make_repo(db=None, tenant="studio-a", actor="lawyer-a", clock=None):
    if db is None and os.environ.get("OFFLINE_TEST_DSN"):
        import psycopg2
        from psycopg2 import sql
        from psycopg2.extensions import parse_dsn

        from pct.storage_postgres import PostgresCompatConnection

        dsn = os.environ["OFFLINE_TEST_DSN"]
        if parse_dsn(dsn).get("dbname") != "offline_synthetic":
            raise ValueError("Only the disposable offline_synthetic database is permitted.")
        raw = psycopg2.connect(dsn)
        schema = "offline_test_" + uuid4().hex
        with raw.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        raw.commit()
        PG_DATABASES.append((raw, schema))
        db = SimpleNamespace(raw_conn=raw)
        db.conn = PostgresCompatConnection(db)
    db = db or SimpleNamespace(conn=sqlite3.connect(":memory:"))
    repo = NoteSync(db, tenant, actor, **({"clock": clock} if clock else {}))
    repo.ensure_schema()
    return repo


def credential():
    key = ec.generate_private_key(ec.SECP256R1())
    public = base64.b64encode(
        key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    ).decode()
    return key, public


def signed(key, challenge):
    der = key.sign(challenge["message"].encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return {
        "challenge": challenge["challenge"],
        "signature": base64.b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode(),
    }


def approved(repo):
    key, public = credential()
    device = repo.register("Computer di prova", public)
    repo.prove(device["id"], signed(key, repo.challenge(device["id"], "enroll")))
    repo.change_status(device["id"], "approve", device["fingerprint"])
    return device["id"], key


def operation(note=None, base=0, text="Nota sintetica", deleted=False):
    return {
        "command": str(uuid4()),
        "id": note or str(uuid4()),
        "base": base,
        "deleted": deleted,
        "payload": {
            "fascicolo_id": "synthetic-case",
            "title": "Test",
            "text": text,
            "attachment": {"name": "sintetico.txt", "text": "Documento sintetico, nessun dato reale."},
        },
    }


def sync(repo, device, key, ops=None, cursor=0, read=lambda _: True, write=lambda _: True):
    intent = {"cursor": cursor, "operations": ops or []}
    proof = signed(key, repo.challenge(device, "sync:" + digest(intent)))
    return repo.exchange(device, proof, intent, can_read=read, can_write=write)


def test_registration_requires_possession_and_verified_fingerprint():
    repo = make_repo()
    key, public = credential()
    device = repo.register("A", public)
    with pytest.raises(ValueError):
        repo.change_status(device["id"], "approve", device["fingerprint"])
    with pytest.raises(PermissionError):
        repo.challenge(device["id"], "sync:a")
    repo.prove(device["id"], signed(key, repo.challenge(device["id"], "enroll")))
    with pytest.raises(ValueError):
        repo.change_status(device["id"], "approve", "wrong")
    repo.change_status(device["id"], "approve", device["fingerprint"])
    assert sync(repo, device["id"], key)["changes"] == []


def test_incremental_documents_lost_response_retry_and_tombstone():
    repo = make_repo()
    device, key = approved(repo)
    op = operation()
    first = sync(repo, device, key, [op])
    retry = sync(repo, device, key, [op])
    assert first["results"] == retry["results"]
    assert len(retry["changes"]) == 1
    assert retry["changes"][0]["payload"]["attachment"]["text"].startswith("Documento sintetico")
    assert sync(repo, device, key, cursor=first["cursor"])["changes"] == []
    removal = operation(op["id"], first["results"][0]["version"], deleted=True)
    result = sync(repo, device, key, [removal], first["cursor"])
    assert result["changes"][0]["deleted"]
    assert len(repo.events()) == 9  # registry 3, mutations 2, exchanges 4


def test_concurrent_devices_conflict_requires_new_explicit_command():
    repo = make_repo()
    first, key = approved(repo)
    second, key2 = approved(repo)
    initial = operation()
    result = sync(repo, first, key, [initial])
    version = result["results"][0]["version"]
    a = operation(initial["id"], version, "Versione A")
    b = operation(initial["id"], version, "Versione B")
    saved = sync(repo, first, key, [a])
    conflict = sync(repo, second, key2, [b])
    assert conflict["results"][0]["status"] == "conflict"
    assert conflict["results"][0]["current"]["payload"]["text"] == "Versione A"
    assert sync(repo, second, key2, [b])["results"] == conflict["results"]
    resolved = operation(initial["id"], saved["results"][0]["version"], "Versione B")
    assert sync(repo, second, key2, [resolved])["results"][0]["status"] == "accepted"


def test_nonce_replay_payload_substitution_wrong_key_and_expiry():
    now = [1000]
    repo = make_repo(clock=lambda: now[0])
    device, key = approved(repo)
    intent = {"cursor": 0, "operations": []}
    proof = signed(key, repo.challenge(device, "sync:" + digest(intent)))
    repo.exchange(device, proof, intent, can_read=lambda _: True, can_write=lambda _: True)
    with pytest.raises(PermissionError):
        repo.exchange(device, proof, intent, can_read=lambda _: True, can_write=lambda _: True)
    proof = signed(key, repo.challenge(device, "sync:" + digest(intent)))
    with pytest.raises(PermissionError):
        repo.exchange(
            device, proof, {"cursor": 0, "operations": [operation()]}, can_read=lambda _: True, can_write=lambda _: True
        )
    other, _ = credential()
    with pytest.raises(PermissionError):
        repo.prove(device, signed(other, repo.challenge(device, "enroll")))
    proof = signed(key, repo.challenge(device, "enroll"))
    now[0] += 121
    with pytest.raises(PermissionError):
        repo.prove(device, proof)


def test_tenant_identity_isolation_and_revocation_between_challenge_and_sync():
    repo = make_repo()
    device, key = approved(repo)
    sync(repo, device, key, [operation()])
    for tenant, actor in [("studio-b", "lawyer-a"), ("studio-a", "lawyer-b")]:
        other = make_repo(repo.db, tenant, actor)
        assert other.list_devices() == []
        with pytest.raises(PermissionError):
            other.challenge(device, "enroll")
    intent = {"cursor": 0, "operations": []}
    proof = signed(key, repo.challenge(device, "sync:" + digest(intent)))
    repo.change_status(device, "revoke")
    with pytest.raises(PermissionError):
        repo.exchange(device, proof, intent, can_read=lambda _: True, can_write=lambda _: True)
    with pytest.raises(ValueError):
        repo.change_status(device, "approve", repo.list_devices()[0]["fingerprint"])


def test_permission_loss_and_atomic_invalid_batch():
    repo = make_repo()
    device, key = approved(repo)
    op = operation()
    sync(repo, device, key, [op])
    invisible = sync(repo, device, key, read=lambda _: False)
    assert invisible["changes"] == [] and invisible["authorized_ids"] == []
    with pytest.raises(PermissionError):
        sync(repo, device, key, [operation()], write=lambda _: False)
    fresh = operation()
    invalid = operation()
    invalid["base"] = -1
    with pytest.raises(ValueError):
        sync(repo, device, key, [fresh, invalid])
    assert len(sync(repo, device, key)["changes"]) == 1


def test_pagination_resume_no_gaps_or_repeated_content():
    repo = make_repo()
    device, key = approved(repo)
    for _ in range(3):
        sync(repo, device, key, [operation() for _ in range(40)])
    first = sync(repo, device, key)
    second = sync(repo, device, key, cursor=first["cursor"])
    assert first["has_more"] and not second["has_more"]
    assert len(first["changes"]) == 100 and len(second["changes"]) == 20
    assert not ({r["id"] for r in first["changes"]} & {r["id"] for r in second["changes"]})


def test_schema_parity_is_explicit():
    root = Path(__file__).parents[1] / "pct/sql"
    assert (root / "20261011_offline.sql").read_text() == (root / "20261011_offline_postgres.sql").read_text()


def test_parallel_writers_only_one_can_commit_same_base(tmp_path):
    path = str(tmp_path / "synthetic.db")
    repo = make_repo() if os.environ.get("OFFLINE_TEST_DSN") else make_repo(SimpleNamespace(conn=sqlite3.connect(path)))
    device, key = approved(repo)
    original = operation()
    version = sync(repo, device, key, [original])["results"][0]["version"]
    second, key2 = approved(repo)
    outcomes = []
    errors = []

    def write(device_id, signing, text):
        try:
            if getattr(repo.db, "raw_conn", None) is not None:
                import psycopg2
                from psycopg2 import sql

                from pct.storage_postgres import PostgresCompatConnection

                schema = repo.db.conn.execute("SELECT current_schema()").fetchone()[0]
                raw = psycopg2.connect(os.environ["OFFLINE_TEST_DSN"])
                with raw.cursor() as cursor:
                    cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                raw.commit()
                database = SimpleNamespace(raw_conn=raw)
                database.conn = PostgresCompatConnection(database)
            else:
                raw = sqlite3.connect(path)
                database = SimpleNamespace(conn=raw)
            local = NoteSync(database, "studio-a", "lawyer-a")
            outcomes.append(
                sync(local, device_id, signing, [operation(original["id"], version, text)])["results"][0]["status"]
            )
        except Exception as exc:  # noqa: BLE001 — preserve worker error for the joining test
            errors.append(exc)
        finally:
            if "raw" in locals():
                raw.close()

    threads = [threading.Thread(target=write, args=args) for args in [(device, key, "A"), (second, key2, "B")]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == [] and sorted(outcomes) == ["accepted", "conflict"]


def test_core_sqlite_schema_installs_offline_tables_without_json_fallback(tmp_path):
    from pct.storage import StudioDB

    db = StudioDB(str(tmp_path / "synthetic-studio.db"))
    tables = {row[0] for row in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {
        "offline_devices",
        "offline_notes",
        "offline_audit",
        "offline_commands",
        "offline_challenges",
        "offline_state",
    } <= tables
    db.chiudi()


def test_mapping_rows_preserve_device_values_instead_of_column_names():
    class IndexedMapping(dict):
        def __getitem__(self, key):
            return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = lambda cursor, values: IndexedMapping(zip([column[0] for column in cursor.description], values))
    repo = make_repo(SimpleNamespace(conn=conn))
    device, key = approved(repo)
    assert repo.list_devices()[0]["id"] == device
    assert repo.list_devices()[0]["status"] == "approved"
    assert sync(repo, device, key)["generation"] == 1
