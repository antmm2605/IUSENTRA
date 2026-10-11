"""Adozione controllata con backup SQLite reale; nessun dato di studio."""
import json
import sqlite3
from types import SimpleNamespace

import pytest

from pct.termini_transition import read_marker, source_lock
from scripts.migra_termini_sql import apply_adoption, read_source, verify_backup
from pct.termini_processuali_repository import DeadlineSqlRepository


def database(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE _meta(chiave TEXT PRIMARY KEY,valore TEXT)")
    conn.execute("CREATE TABLE audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                 "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
    conn.commit()
    return SimpleNamespace(conn=conn, db_path=str(path))


def test_controlled_adoption_backup_and_exact_replay(tmp_path):
    source = tmp_path / "termini.json"
    source.write_text(json.dumps({"guida_pratica_terms": [{"historical": True}]}), encoding="utf-8")
    original = source.read_bytes()
    db = database(tmp_path / "studio.db")
    try:
        with source_lock(source):
            result = apply_adoption(db, source, destination=tmp_path / "backup", tenant_key="studio", actor_key="migrazione")
        assert source.read_bytes() == original
        assert (tmp_path / "backup" / "termini-original.json").read_bytes() == original
        assert read_marker(source)["phase"] == "committed"
        assert verify_backup(tmp_path / "backup", result)["sha256"]
        with source_lock(source):
            replay = apply_adoption(db, source, destination=tmp_path / "backup", tenant_key="studio", actor_key="migrazione")
        assert replay["receipt"]["already_present"]
        assert db.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
    finally:
        db.conn.close()


def test_invalid_source_does_not_create_backup_or_marker(tmp_path):
    source = tmp_path / "termini.json"
    source.write_text('{"audit_logs":"errato"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Righe"):
        read_source(source)
    assert read_marker(source) is None


def test_adoption_replay_preserves_audited_revision_but_rejects_unexplained_change(tmp_path):
    source = tmp_path / "termini.json"
    source.write_text("{}", encoding="utf-8")
    db = database(tmp_path / "studio.db")
    destination = tmp_path / "backup"
    try:
        with source_lock(source):
            result = apply_adoption(db, source, destination=destination, tenant_key="studio", actor_key="migrazione")
        repo = DeadlineSqlRepository(db, "studio", source=source, actor_key="avvocato",
                                     expected_adoption=(result["source_sha256"], str(destination.resolve())))
        old = repo.get_template_payload("CIV_APPELLO_BREVE")
        replacement = {**old, "version": old["version"] + 1}
        repo.revise_template(old["code"], expected=old, replacement=replacement,
                             revision="controllata", reason="Prova", source="fonte-controllata")
        with source_lock(source):
            assert apply_adoption(db, source, destination=destination, tenant_key="studio",
                                  actor_key="migrazione")["receipt"]["already_present"]
        assert repo.get_template_payload(old["code"]) == replacement
        db.conn.execute("UPDATE audit_log SET dettagli='{}' WHERE azione='termini.revisione'")
        db.conn.commit()
        with source_lock(source), pytest.raises(RuntimeError, match="non concordante"):
            apply_adoption(db, source, destination=destination, tenant_key="studio", actor_key="migrazione")
    finally:
        db.conn.close()


def test_backup_source_corruption_is_not_accepted(tmp_path):
    source = tmp_path / "termini.json"
    source.write_text("{}", encoding="utf-8")
    db = database(tmp_path / "studio.db")
    try:
        with source_lock(source):
            result = apply_adoption(db, source, destination=tmp_path / "backup", tenant_key="studio", actor_key="migrazione")
        (tmp_path / "backup" / "termini-original.json").write_text('{"alterato":true}', encoding="utf-8")
        with pytest.raises(RuntimeError, match="Fonte originale"):
            verify_backup(tmp_path / "backup", result)
    finally:
        db.conn.close()


def test_explicit_missing_source_provision_records_absence_and_never_overwrites(tmp_path):
    from scripts.migra_termini_sql import initialize_missing_source
    source = tmp_path / "termini.json"
    with source_lock(source):
        payload = initialize_missing_source(source, tenant_key="studio", actor_key="migrazione")
    assert payload["initial_provision"]["source_previously_absent"] is True
    assert payload["initial_provision"]["tenant"] == "studio"
    templates = [row for row in payload["templates"] if row.get("metadata", {}).get("codice_guida") == "411003"]
    assert len(templates) == 1 and templates[0]["base_value"] == 10
    original = source.read_bytes()
    with source_lock(source), pytest.raises(ValueError, match="già presente"):
        initialize_missing_source(source, tenant_key="studio", actor_key="migrazione")
    assert source.read_bytes() == original
