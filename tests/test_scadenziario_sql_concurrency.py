"""Due snapshot del motore nativo: SQL resta la fonte confermata."""
import json
import os
from types import MethodType, SimpleNamespace

import pytest

from pct.scadenziario import GestioneScadenziario, TipoTermine
from pct.scadenziario_sql_writer import COLUMNS, ScadenziarioConflict
from pct.storage import StudioDB


@pytest.fixture
def managers(tmp_path):
    raw = None
    if os.environ.get("CTU_TEST_POSTGRES") == "1":
        import psycopg2
        from pct.storage_postgres import PostgresCompatConnection, PostgresStudioDB
        raw = psycopg2.connect(host=os.environ.get("CTU_TEST_PG_HOST", "audit-postgres"),
                              dbname=os.environ.get("AUDIT_POSTGRES_DB", "iusentra_audit"),
                              user=os.environ.get("AUDIT_POSTGRES_USER", "iusentra_audit"),
                              password=os.environ["AUDIT_POSTGRES_PASSWORD"])
        db = SimpleNamespace(raw_conn=raw)
        db.conn = PostgresCompatConnection(db)
        columns = [name + (" INTEGER" if name == "perentorio" else " TEXT") + (" PRIMARY KEY" if name == "id" else "") for name in COLUMNS]
        db.conn.execute(f"CREATE TEMP TABLE scadenze ({','.join(columns)})")
        raw.commit()
        # Stessa implementazione transazionale nativa, su tabella temporanea;
        # la lettura controllata non apre connessioni al search_path dello studio.
        db.salva_tabella = MethodType(PostgresStudioDB.salva_tabella, db)
        db.fetchall_readonly = lambda sql: db.conn.execute(sql).fetchall()
    else:
        db = StudioDB.get(str(tmp_path / "studio.db"))
    path = tmp_path / "scadenze.json"
    def open_manager():
        return GestioneScadenziario(str(path), studio_db=db)
    initial = open_manager()
    first = initial.nuova("Prima", TipoTermine.ADEMPIMENTO, "2026-12-01")
    second = initial.nuova("Seconda", TipoTermine.ADEMPIMENTO, "2026-12-02")
    try:
        yield db, path, open_manager, first.id, second.id
    finally:
        if raw is not None:
            raw.close()


def test_snapshot_distinti_non_perdono_modifiche_di_altre_scadenze(managers):
    db, path, open_manager, first, second = managers
    left, right = open_manager(), open_manager()
    left.aggiorna(first, note="Modifica del primo processo")
    right.aggiorna(second, note="Modifica del secondo processo")
    rows = {row["id"]: json.loads(row["dati_json"]) for row in db.fetchall_readonly("SELECT * FROM scadenze")}
    assert rows[first]["note"] == "Modifica del primo processo"
    assert rows[second]["note"] == "Modifica del secondo processo"
    mirror = json.loads(path.read_text(encoding="utf-8"))
    assert mirror[first]["note"] == rows[first]["note"]
    assert mirror[second]["note"] == rows[second]["note"]


def test_snapshot_superato_non_cancella_nuove_scadenze(managers):
    db, _, open_manager, _, _ = managers
    left, right = open_manager(), open_manager()
    one = left.nuova("Nuova nel primo processo", TipoTermine.ADEMPIMENTO, "2026-12-03")
    two = right.nuova("Nuova nel secondo processo", TipoTermine.ADEMPIMENTO, "2026-12-04")
    assert {row["id"] for row in db.fetchall_readonly("SELECT id FROM scadenze")} >= {one.id, two.id}


def test_stessa_scadenza_concorrente_rifiuta_sovrascrittura(managers):
    db, path, open_manager, first, _ = managers
    left, right = open_manager(), open_manager()
    left.aggiorna(first, note="Confermata")
    before_mirror = path.read_bytes()
    with pytest.raises(ScadenziarioConflict):
        right.aggiorna(first, note="Snapshot superato")
    assert db.conn.execute("SELECT note FROM scadenze WHERE id=?", (first,)).fetchone()[0] == "Confermata"
    assert path.read_bytes() == before_mirror
    assert right.get(first).note != "Snapshot superato"


def test_lotto_con_conflitto_annulla_anche_le_altre_scritture(managers):
    db, _, open_manager, first, second = managers
    left, right = open_manager(), open_manager()
    left.aggiorna(first, note="Confermata")
    right.get(first).note = "Da annullare"
    right.get(second).note = "Da annullare insieme"
    with pytest.raises(ScadenziarioConflict):
        right._salva()
    assert db.conn.execute("SELECT note FROM scadenze WHERE id=?", (second,)).fetchone()[0] == ""
    assert db.conn.execute("SELECT note FROM scadenze WHERE id=?", (first,)).fetchone()[0] == "Confermata"


def test_colonne_sql_cambiate_senza_json_impediscono_sovrascrittura(managers):
    db, _, open_manager, first, _ = managers
    stale = open_manager()
    db.conn.execute("UPDATE scadenze SET note='Aggiornamento SQL' WHERE id=?", (first,))
    getattr(db, "raw_conn", db.conn).commit()
    with pytest.raises(ScadenziarioConflict):
        stale.aggiorna(first, note="Sovrascrittura")
    assert db.conn.execute("SELECT note FROM scadenze WHERE id=?", (first,)).fetchone()[0] == "Aggiornamento SQL"


def test_errore_sql_non_importa_il_mirror_come_fonte(managers, monkeypatch):
    db, path, open_manager, _, _ = managers
    before = path.read_bytes()
    def failed(_sql):
        raise RuntimeError("Archivio indisponibile")
    monkeypatch.setattr(db, "fetchall_readonly", failed)
    with pytest.raises(RuntimeError, match="nessun dato riscritto da JSON"):
        open_manager()
    assert path.read_bytes() == before


@pytest.mark.parametrize("same_row", [False, True])
def test_due_connessioni_native_simultanee_preservano_sql(tmp_path, same_row):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4
    from pct.scadenziario import Scadenza
    from pct.scadenziario_sql_writer import encode_model, row_values, save_changes

    postgres = os.environ.get("CTU_TEST_POSTGRES") == "1"
    schema = "scadenze_test_" + uuid4().hex
    def connect():
        if postgres:
            import psycopg2
            from psycopg2 import sql
            from pct.storage_postgres import PostgresCompatConnection, PostgresStudioDB
            raw = psycopg2.connect(host=os.environ.get("CTU_TEST_PG_HOST", "audit-postgres"),
                dbname=os.environ.get("AUDIT_POSTGRES_DB", "iusentra_audit"),
                user=os.environ.get("AUDIT_POSTGRES_USER", "iusentra_audit"),
                password=os.environ["AUDIT_POSTGRES_PASSWORD"])
            with raw.cursor() as cursor:
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            raw.commit()
            db = SimpleNamespace(raw_conn=raw)
            db.conn = PostgresCompatConnection(db)
            db.salva_tabella = MethodType(PostgresStudioDB.salva_tabella, db)
            return db, raw
        db = StudioDB(str(tmp_path / "concorrenza.db"), initialize_schema=False)
        return db, db.conn

    if not postgres:
        import sqlite3
        sqlite3.connect(tmp_path / "concorrenza.db").close()
    owner, raw = connect()
    try:
        if postgres:
            from psycopg2 import sql
            with raw.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            raw.commit()
        columns = [name + (" INTEGER" if name == "perentorio" else " TEXT") + (" PRIMARY KEY" if name == "id" else "") for name in COLUMNS]
        owner.conn.execute(f"CREATE TABLE scadenze ({','.join(columns)})")
        originals = [Scadenza(titolo="Scadenza controllata", data_scadenza="2026-12-01") for _ in range(2)]
        for item in originals:
            owner.conn.execute(f"INSERT INTO scadenze VALUES ({','.join('?' for _ in COLUMNS)})", row_values(item))
        raw.commit()
        barrier = Barrier(2)
        def attempt(index):
            db, connection = connect()
            try:
                item = originals[0 if same_row else index]
                found = db.conn.execute("SELECT * FROM scadenze WHERE id=?", (item.id,)).fetchone()
                snapshot = dict(found)
                # End the read transaction before both independent writers start.
                connection.commit()
                current = Scadenza.from_dict(item.to_dict())
                current.note = f"Processo {index}"
                barrier.wait(timeout=10)
                try:
                    save_changes(db, original_rows={item.id: snapshot},
                        original_models={item.id: encode_model(item)}, current={item.id: current})
                    return "registrato"
                except ScadenziarioConflict:
                    return "conflitto"
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, range(2)))
        rows = {row["id"]: row["note"] for row in owner.conn.execute("SELECT * FROM scadenze").fetchall()}
        assert len(rows) == 2
        if same_row:
            assert sorted(results) == ["conflitto", "registrato"]
            assert rows[originals[0].id] in {"Processo 0", "Processo 1"}
            assert rows[originals[1].id] == ""
        else:
            assert results == ["registrato", "registrato"]
            assert rows == {item.id: f"Processo {index}" for index, item in enumerate(originals)}
    finally:
        if postgres:
            raw.rollback()
            with raw.cursor() as cursor:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            raw.commit()
        raw.close()


def test_scrittore_composto_non_committa_se_la_consegna_successiva_fallisce(managers):
    from pct.scadenziario import Scadenza
    from pct.scadenziario_sql_writer import write_changes
    db, path, open_manager, first, _ = managers
    manager = open_manager()
    before_mirror = path.read_bytes()
    current = Scadenza.from_dict(manager.get(first).to_dict())
    current.note = "Modifica da annullare con la consegna"
    raw = getattr(db, "raw_conn", db.conn)
    if getattr(db, "raw_conn", None) is None:
        db.conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(RuntimeError, match="Consegna non registrata"):
            assert write_changes(db.conn, original_rows=manager._sql_rows,
                original_models=manager._sql_models,
                current={**manager._scadenze, first: current}) == 1
            assert db.conn.execute("SELECT note FROM scadenze WHERE id=?", (first,)).fetchone()[0] == current.note
            raise RuntimeError("Consegna non registrata")
    finally:
        raw.rollback()
    assert db.conn.execute("SELECT note FROM scadenze WHERE id=?", (first,)).fetchone()[0] == ""
    assert path.read_bytes() == before_mirror
