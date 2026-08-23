import sqlite3

import pytest

from pct.data_consistency import build_sql_consistency_snapshot, reconcile_sql_backends
from pct.storage import StudioDB
from pct.storage_migration import _copy_transactional_outbox
from pct.transactional_outbox import OutboxEvent, enqueue, ensure_outbox_schema


def test_outbox_e_idempotente_e_non_esegue_commit():
    conn = sqlite3.connect(":memory:")
    ensure_outbox_schema(conn)
    conn.execute("BEGIN")
    event = OutboxEvent("tenant-a", "fascicolo", "F-1", 1, "fascicolo.creato", "key-1", {"id": "F-1"}, "utente-a")
    first = enqueue(conn, event)
    second = enqueue(conn, event)
    assert first != second
    assert conn.execute("SELECT COUNT(*) FROM transactional_outbox").fetchone()[0] == 1
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM transactional_outbox").fetchone()[0] == 0


def test_outbox_rifiuta_evento_senza_tenant_o_versione():
    conn = sqlite3.connect(":memory:")
    ensure_outbox_schema(conn)
    with pytest.raises(ValueError, match="Tenant"):
        enqueue(conn, OutboxEvent("", "fascicolo", "F-1", 1, "x", "key", {}, "utente-a"))
    with pytest.raises(ValueError, match="versione"):
        enqueue(conn, OutboxEvent("tenant-a", "fascicolo", "F-1", 0, "x", "key", {}, "utente-a"))
    with pytest.raises(ValueError, match="Attore"):
        enqueue(conn, OutboxEvent("tenant-a", "fascicolo", "F-1", 1, "x", "key", {}, ""))


def test_migrazione_outbox_preserva_chiave_idempotenza(tmp_path):
    source = StudioDB.get(str(tmp_path / "source.db"))
    target = StudioDB.get(str(tmp_path / "target.db"))
    enqueue(source.conn, OutboxEvent("tenant-a", "fascicolo", "F-1", 1, "fascicolo.creato", "key-1", {}, "utente-a"))
    source.conn.commit()
    _copy_transactional_outbox(source, target)
    row = target.conn.execute("SELECT tenant_id, idempotency_key, actor_id FROM transactional_outbox").fetchone()
    assert tuple(row) == ("tenant-a", "key-1", "utente-a")


def test_riconciliazione_sql_segnala_divergenza_senza_leggere_json(tmp_path):
    source = StudioDB.get(str(tmp_path / "source-consistency.db"))
    target = StudioDB.get(str(tmp_path / "target-consistency.db"))
    source.conn.execute("INSERT INTO clienti (id, dati_json) VALUES ('c-1', '{}')")
    source.conn.commit()
    report = reconcile_sql_backends(source, target, tables=("clienti",))
    assert report["source_of_truth"] == "sql"
    assert report["ok"] is False
    assert report["tables"][0]["status"] == "MISMATCH"


def test_snapshot_coerenza_legge_solo_tabelle_sql_del_backend(tmp_path):
    backend = StudioDB.get(str(tmp_path / "consistency.db"))
    backend.conn.execute("INSERT INTO clienti (id, dati_json) VALUES ('c-1', '{}')")
    backend.conn.commit()

    snapshot = build_sql_consistency_snapshot(backend)

    assert snapshot["ok"] is True
    assert snapshot["source_of_truth"] == "sqlite"
    assert snapshot["contracts"] == {
        "writes": "none",
        "json_scanned": False,
        "fallback_used": False,
        "source_of_truth": "sql",
    }
    clienti = next(domain for domain in snapshot["domains"] if domain["id"] == "anagrafiche")
    assert clienti["records"] == 1
