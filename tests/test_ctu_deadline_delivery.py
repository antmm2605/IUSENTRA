"""Consegna tecnica atomica: non accettazione materiale del prodotto."""
import copy
import json
from uuid import uuid4

import pytest

from pct.ctu_deadline_delivery import deliver_deadlines
from pct.scadenziario_sql_writer import COLUMNS
from tests.test_ctu_sql_repository import adopted, command, database as database, fail_audit, record


@pytest.fixture
def archive(database):
    columns = [name + (" INTEGER" if name == "perentorio" else " TEXT") + (" PRIMARY KEY" if name == "id" else "") for name in COLUMNS]
    prefix = "CREATE TEMP TABLE" if hasattr(database, "raw_conn") else "CREATE TABLE"
    database.conn.execute(f"{prefix} scadenze ({','.join(columns)})")
    getattr(database, "raw_conn", database.conn).commit()
    repo = adopted(database)
    return database, repo


def callback(conn, saved):
    return deliver_deadlines(conn, saved, tenant="studio", actor="avvocato")


def test_consegna_e_replay_non_producono_doppioni(archive):
    db, repo = archive
    item = record(termine_deposito="2026-12-01", termine_osservazioni="2026-12-10")
    cmd = command(repo)
    result = repo.save({item["id"]: item}, command=cmd, delivery=callback)
    assert result["delivery"]["created"] == 2
    assert repo.replay(cmd) == result
    assert db.conn.execute("SELECT COUNT(*) FROM scadenze").fetchone()[0] == 2
    assert db.conn.execute("SELECT COUNT(*) FROM audit_log WHERE azione='ctu.consegna_interna'").fetchone()[0] == 1


def test_audit_fallito_annulla_ctu_comando_e_scadenze(archive):
    db, repo = archive
    error = fail_audit(db)
    item = record(ruolo_studio="AUSILIARIO", termine_bozza="2026-12-01")
    with pytest.raises(error):
        repo.save({item["id"]: item}, command=command(repo), delivery=callback)
    for table in ("ctu_records", "ctu_commands", "scadenze"):
        assert db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert db.conn.execute("SELECT revision FROM ctu_state").fetchone()[0] == 0


def test_errore_dopo_scadenze_annulla_tutta_la_transazione(archive):
    db, repo = archive
    item = record(ruolo_studio="AUSILIARIO", termine_bozza="2026-12-01")
    def failed(conn, saved):
        assert callback(conn, saved)["created"] == 1
        raise RuntimeError("Consegna interrotta")
    with pytest.raises(RuntimeError, match="Consegna interrotta"):
        repo.save({item["id"]: item}, command=command(repo), delivery=failed)
    for table in ("ctu_records", "ctu_commands", "scadenze"):
        assert db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_data_aggiornata_non_sovrascrive_decisione_manuale(archive):
    db, repo = archive
    item = record(ruolo_studio="AUSILIARIO", termine_bozza="2026-12-01")
    result = repo.save({item["id"]: item}, command=command(repo), delivery=callback)
    row = db.conn.execute("SELECT id,dati_json FROM scadenze").fetchone()
    identifier, serialized = row[0], row[1]
    payload = json.loads(serialized)
    payload["stato"] = "COMPLETATO"
    db.conn.execute("UPDATE scadenze SET stato=?,dati_json=? WHERE id=?", ("COMPLETATO", json.dumps(payload), identifier))
    getattr(db, "raw_conn", db.conn).commit()
    changed = copy.deepcopy(item)
    changed["termine_bozza"] = "2026-12-02"
    changed["modificato_il"] = "2026-10-09T22:30:00"
    result = repo.save({item["id"]: changed}, command=command(repo), delivery=callback)
    assert result["delivery"]["items"][0]["status"] == "manual_preserved"
    assert db.conn.execute("SELECT data_scadenza FROM scadenze").fetchone()[0] == "2026-12-01"
    assert db.conn.execute("SELECT COUNT(*) FROM scadenze").fetchone()[0] == 1


def test_riscontro_consegna_manomesso_non_diventa_replay(archive):
    db, repo = archive
    item = record(ruolo_studio="AUSILIARIO", termine_bozza="2026-12-01")
    cmd = command(repo)
    result = repo.save({item["id"]: item}, command=cmd, delivery=callback)
    result["delivery"]["items"][0]["id"] = str(uuid4())
    db.conn.execute("UPDATE ctu_commands SET result_json=? WHERE command_key=?", (json.dumps(result), cmd["key"]))
    getattr(db, "raw_conn", db.conn).commit()
    with pytest.raises(RuntimeError, match="Audit della consegna"):
        repo.replay(cmd)


def test_audit_consegna_fallito_dopo_scrittura_scadenza_annulla_tutto(archive):
    db, repo = archive
    if hasattr(db, "raw_conn"):
        db.conn.execute("ALTER TABLE audit_log ADD CONSTRAINT delivery_indisponibile CHECK (azione!='ctu.consegna_interna')")
        from psycopg2 import IntegrityError
    else:
        db.conn.execute("CREATE TRIGGER delivery_fail BEFORE INSERT ON audit_log WHEN NEW.azione='ctu.consegna_interna' BEGIN SELECT RAISE(ABORT,'audit consegna indisponibile'); END")
        from sqlite3 import IntegrityError
    getattr(db, "raw_conn", db.conn).commit()
    item = record(ruolo_studio="AUSILIARIO", termine_bozza="2026-12-01")
    with pytest.raises(IntegrityError):
        repo.save({item["id"]: item}, command=command(repo), delivery=callback)
    for table in ("ctu_records", "ctu_commands", "scadenze"):
        assert db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert db.conn.execute("SELECT revision FROM ctu_state").fetchone()[0] == 0


def test_nuovo_comando_aggiorna_solo_la_bozza_e_riconosce_gia_presente(archive):
    db, repo = archive
    item = record(termine_osservazioni="2026-12-01")
    first = repo.save({item["id"]: item}, command=command(repo), delivery=callback)
    changed = copy.deepcopy(item)
    changed.update(termine_osservazioni="2026-12-02", modificato_il="2026-10-09T22:31:00")
    updated = repo.save({item["id"]: changed}, command=command(repo), delivery=callback)
    assert updated["delivery"]["updated"] == 1 and updated["delivery"]["created"] == 0
    assert updated["delivery"]["items"][0]["id"] == first["delivery"]["items"][0]["id"]
    changed["modificato_il"] = "2026-10-09T22:32:00"
    repeated = repo.save({item["id"]: changed}, command=command(repo), delivery=callback)
    assert repeated["delivery"]["items"][0]["status"] == "already_present"
    assert db.conn.execute("SELECT COUNT(*) FROM scadenze").fetchone()[0] == 1


def test_stato_sql_discordante_dal_payload_non_viene_sovrascritto(archive):
    db, repo = archive
    item = record(termine_osservazioni="2026-12-01")
    repo.save({item["id"]: item}, command=command(repo), delivery=callback)
    db.conn.execute("UPDATE scadenze SET stato='COMPLETATO'")
    getattr(db, "raw_conn", db.conn).commit()
    changed = copy.deepcopy(item)
    changed.update(termine_osservazioni="2026-12-02", modificato_il="2026-10-09T22:31:00")
    with pytest.raises(ValueError, match="contenuto discordanti"):
        repo.save({item["id"]: changed}, command=command(repo), delivery=callback)
    assert db.conn.execute("SELECT stato FROM scadenze").fetchone()[0] == "COMPLETATO"
    assert db.conn.execute("SELECT revision FROM ctu_state").fetchone()[0] == 1
