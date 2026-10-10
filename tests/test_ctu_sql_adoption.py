"""Backup, barriera e ripresa dell'adozione CTU esplicita."""
import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from pct.ctu import IncaricoCtu
from pct.ctu_repository import CtuRepository
from pct.ctu_transition import read_marker, source_lock
from scripts.migra_ctu_sql import apply_adoption, read_source, verify_backup, verify_fascicoli


def test_backup_container_non_persistente_rifiutato(tmp_path):
    from scripts.migra_ctu_sql import verify_persistent_backup_destination
    data = tmp_path / "data"
    verify_persistent_backup_destination(data / "backups" / "ctu", data_root=data)
    with pytest.raises(ValueError, match="volume dati persistente"):
        verify_persistent_backup_destination(tmp_path / "app" / "backup", data_root=data)
    with pytest.raises(ValueError, match="volume dati persistente"):
        verify_persistent_backup_destination(data / ".." / "data-other" / "backup", data_root=data)


@pytest.fixture
def adoption(tmp_path):
    sql = tmp_path / "studio.db"
    conn = sqlite3.connect(sql)
    db = SimpleNamespace(conn=conn, db_path=str(sql))
    conn.execute("CREATE TABLE fascicoli(id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO fascicoli VALUES ('F1')")
    conn.execute("CREATE TABLE _meta(chiave TEXT PRIMARY KEY,valore TEXT)")
    conn.execute("CREATE TABLE audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                 "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
    conn.commit()
    source = tmp_path / "incarichi.json"
    record = IncaricoCtu(fascicolo_id="F1", nome_ctu="Ing. Bruni").to_dict()
    source.write_text(json.dumps({record["id"]: record}), encoding="utf-8")
    payload, sha, content = read_source(source)
    result = {"tenant": "studio", "tenant_key": "studio", "source": str(source.resolve()),
              "source_sha256": sha, "source_exists": True, "records": 1, "apply": True,
              "postgres": False, "sql_path": str(sql)}
    destination = tmp_path / "backup" / "studio"
    yield db, source, result, destination, payload, content
    conn.close()


def apply(fixture):
    db, source, result, destination, payload, content = fixture
    with source_lock(source):
        apply_adoption(db, source, result, destination=destination, payload=payload, content=content)


def test_adozione_backup_audit_segnale_e_ripresa(adoption):
    db, source, result, destination, payload, content = adoption
    apply(adoption)
    assert source.read_bytes() == content
    assert read_marker(source)["phase"] == "committed"
    assert result["sql_records"] == 1
    assert verify_backup(destination, result)["quick_check"] == "ok"
    assert db.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()[0] == 1
    repo = CtuRepository(db, "studio", actor_key="avvocato")
    repo.load()
    key = next(iter(payload))
    updated = {**payload[key], "stato": "GIURAMENTO"}
    cmd = repo.command(str(uuid4()), "aggiornamento", {"stato": "GIURAMENTO"}, 0)
    repo.save({key: updated}, command=cmd)
    apply(adoption)
    assert repo.load()[key]["stato"] == "GIURAMENTO"
    assert repo.revision == 1
    assert db.conn.execute("SELECT COUNT(*) FROM ctu_audit WHERE revision=0").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM audit_log WHERE azione='ctu.adozione'").fetchone()[0] == 1


def test_backup_corrotto_blocca_ripresa(adoption):
    db, source, result, destination, payload, content = adoption
    apply(adoption)
    (destination / "studio-ctu.db").write_bytes(b"backup non integro")
    with pytest.raises(RuntimeError, match="Backup coerente"):
        apply(adoption)
    assert read_marker(source)["phase"] == "committed"
    assert len(CtuRepository(db, "studio").load()) == 1


def test_fascicolo_estraneo_non_viene_importato(adoption):
    db, source, result, destination, payload, content = adoption
    changed = {key: {**value, "fascicolo_id": "ALTRO"} for key, value in payload.items()}
    with pytest.raises(ValueError, match="fascicolo non presente"):
        verify_fascicoli(db, changed)
    assert read_marker(source) is None
    assert not destination.exists()


@pytest.mark.parametrize("prerequisites", [[], ["--writers-drained"], ["--backup-dir", "backup"]])
def test_cli_apply_richiede_backup_e_drain(monkeypatch, tmp_path, prerequisites):
    from scripts.migra_ctu_sql import main
    monkeypatch.setattr("sys.argv", ["migra_ctu_sql", "--tenant", "studio", "--report", str(tmp_path / "report"),
                                     "--apply", *prerequisites])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2 and not (tmp_path / "backup").exists()


def test_fonte_assente_distinta_da_json_vuoto(tmp_path):
    path = tmp_path / "assente.json"
    empty, absent_sha, absent_content = read_source(path)
    assert empty == {} and absent_content is None
    path.write_text("{}", encoding="utf-8")
    empty, present_sha, present_content = read_source(path)
    assert empty == {} and present_content == b"{}" and absent_sha != present_sha


def test_backup_source_mancante_non_confermato(adoption):
    db, source, result, destination, payload, content = adoption
    apply(adoption)
    (destination / "ctu-original.json").unlink()
    with pytest.raises(RuntimeError, match="originale CTU"):
        verify_backup(destination, result)


def test_fallimento_audit_preserva_barriera_e_backup(adoption):
    db, source, result, destination, payload, content = adoption
    db.conn.execute("CREATE TRIGGER audit_failure BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT,'audit indisponibile'); END")
    db.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        apply(adoption)
    assert (destination / "studio-ctu.db").is_file()
    assert read_marker(source)["phase"] == "prepared"
    assert db.conn.execute("SELECT COUNT(*) FROM ctu_state").fetchone()[0] == 0
    assert source.read_bytes() == content
    db.conn.execute("DROP TRIGGER audit_failure")
    db.conn.commit()
    apply(adoption)
    assert read_marker(source)["phase"] == "committed" and result["sql_records"] == 1
