"""Guardrail del comando SQL; la prova del prodotto richiede il browser reale."""
import copy
import json
import sqlite3
from uuid import uuid4

import pytest

from pct.storage import StudioDB
from pct.udienze.repository import PreparazioneConflict, PreparazioneRejected, PreparazioniRepository, validate_record
from pct.wizard_pro import SessioneWizardPro


@pytest.fixture
def database(tmp_path):
    db = StudioDB(str(tmp_path / "studio.db"))
    repo = PreparazioniRepository(db, "studio", actor="avvocato")
    repo.ensure_schema()
    yield db
    db.chiudi()


def adopted(db, *, tenant="studio", records=None):
    repo = PreparazioniRepository(db, tenant, actor="avvocato")
    repo.initialize(records or [], source_sha256="a" * 64, backup_reference="backup-verificato")
    return repo


def record(hearing="A1"):
    return SessioneWizardPro.nuova("F1", "Udienza tecnica", id_appuntamento=hearing).to_dict()


def save(repo, item, *, command=None, version=0, text="Nota", apply=None):
    def update(conn, session, intent):
        session.step1_note = intent["text"]
        return {"kind": "passo", "confirmed": True}
    return repo.execute(item["id"], "passo", {"text": text}, command_key=command or str(uuid4()),
                        expected_revision=version, apply=apply or update)


def test_constructor_does_not_create_or_import(tmp_path):
    sqlite3.connect(tmp_path / "empty.db").close()
    db = StudioDB(str(tmp_path / "empty.db"), initialize_schema=False)
    try:
        repo = PreparazioniRepository(db, "studio")
        assert db.conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'preparazioni_%'").fetchall() == []
        with pytest.raises(sqlite3.OperationalError):
            repo.list()
        assert db.conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'preparazioni_%'").fetchall() == []
    finally:
        db.chiudi()


def test_missing_adoption_is_not_an_empty_archive(database):
    with pytest.raises(RuntimeError, match="non adottate"):
        PreparazioniRepository(database, "studio").list()


def test_source_unknown_fields_and_duplicates_not_discarded(database):
    raw = record()
    with pytest.raises(ValueError, match="Campi"):
        validate_record({**raw, "unknown": "da preservare"})
    with pytest.raises(ValueError, match="duplicate"):
        adopted(database, records=[raw, copy.deepcopy(raw)])
    with pytest.raises(ValueError, match="stessa udienza"):
        adopted(database, records=[raw, record()])
    assert database.conn.execute("SELECT COUNT(*) FROM preparazioni_state").fetchone()[0] == 0


def test_replay_does_not_repeat_effects(database):
    item, command = record(), str(uuid4())
    repo = adopted(database, records=[item])
    first = save(repo, item, command=command)
    def forbidden(*args):
        raise AssertionError("Gli effetti non devono ripetersi")
    second = save(repo, item, command=command, apply=forbidden)
    assert first == second
    assert repo.get(item["id"])["revision"] == 1
    assert database.conn.execute("SELECT COUNT(*) FROM preparazioni_commands").fetchone()[0] == 1


def test_reused_command_with_changed_intent_rejected(database):
    item, command = record(), str(uuid4())
    repo = adopted(database, records=[item])
    save(repo, item, command=command)
    with pytest.raises(ValueError, match="contenuto"):
        save(repo, item, command=command, text="Intento diverso")
    assert repo.get(item["id"])["record"]["step1_note"] == "Nota"


def test_stale_tab_cannot_run_effects(database):
    item = record()
    repo = adopted(database, records=[item])
    save(repo, item, text="Confermata")
    def forbidden(*args):
        raise AssertionError("La bozza superata non deve generare effetti")
    with pytest.raises(PreparazioneConflict):
        save(repo, item, text="Bozza vecchia", apply=forbidden)
    assert repo.get(item["id"])["record"]["step1_note"] == "Confermata"


def test_independent_sessions_do_not_block_each_other(database):
    first, second = record("A1"), record("A2")
    repo = adopted(database, records=[first, second])
    save(repo, first)
    save(repo, second)
    assert [row["revision"] for row in repo.list()] == [1, 1]


def test_effect_failure_rolls_back_session_and_native_rows(database):
    item = record()
    repo = adopted(database, records=[item])
    def fail(conn, session, intent):
        conn.execute("INSERT INTO appuntamenti (id,titolo,data_ora) VALUES (?,?,?)",
                     ("test-preparazione", "Rinvio tecnico", "2026-12-16T15:00:00"))
        session.step1_note = "Mai confermata"
        raise RuntimeError("seconda consegna non riuscita")
    with pytest.raises(RuntimeError, match="consegna"):
        save(repo, item, apply=fail)
    assert repo.get(item["id"])["revision"] == 0
    assert repo.get(item["id"])["record"]["step1_note"] == ""
    assert database.conn.execute("SELECT COUNT(*) FROM appuntamenti WHERE id=?", ("test-preparazione",)).fetchone()[0] == 0
    assert database.conn.execute("SELECT COUNT(*) FROM preparazioni_commands").fetchone()[0] == 0


def test_missing_audit_prevents_replay(database):
    item, command = record(), str(uuid4())
    repo = adopted(database, records=[item])
    first = save(repo, item, command=command)
    row = database.conn.execute("SELECT audit_id FROM preparazioni_commands WHERE command_key=?", (command,)).fetchone()
    database.conn.execute("DELETE FROM audit_log WHERE id=?", (row[0],))
    database.conn.commit()
    with pytest.raises(RuntimeError, match="audit"):
        save(repo, item, command=command)
    assert repo.get(item["id"])["revision"] == first["revision"]


def test_audit_with_wrong_actor_prevents_replay(database):
    item, command = record(), str(uuid4())
    repo = adopted(database, records=[item])
    save(repo, item, command=command)
    database.conn.execute("UPDATE audit_log SET id_utente='altro' WHERE id IN (SELECT audit_id FROM preparazioni_commands WHERE command_key=?)", (command,))
    database.conn.commit()
    with pytest.raises(RuntimeError, match="audit"):
        save(repo, item, command=command)


def test_other_tenant_cannot_read_or_replay(database):
    item, command = record(), str(uuid4())
    repo = adopted(database, records=[item])
    save(repo, item, command=command)
    other = adopted(database, tenant="altro-studio")
    assert other.list() == []
    assert other.get(item["id"]) is None
    with pytest.raises(ValueError, match="non trovata"):
        save(other, item, command=command)


def test_source_and_sql_identity_discordance_is_explicit(database):
    item = record()
    repo = adopted(database, records=[item])
    changed = {**item, "id_fascicolo": "ALTRO"}
    database.conn.execute("UPDATE preparazioni_sessions SET payload_json=? WHERE session_key=?", (json.dumps(changed), item["id"]))
    database.conn.commit()
    with pytest.raises(RuntimeError, match="Identità"):
        repo.get(item["id"])


def test_live_revision_only_follows_confirmed_commit(database):
    from pct.operational_live import ensure_live_schema, read_live_revisions
    ensure_live_schema(database.conn)
    item = record()
    repo = adopted(database, records=[item])
    before = read_live_revisions(database, {"agenda"})
    def fail(conn, session, intent):
        raise RuntimeError("Effetto non confermato")
    with pytest.raises(RuntimeError):
        save(repo, item, apply=fail)
    assert read_live_revisions(database, {"agenda"}) == before
    command = str(uuid4())
    save(repo, item, command=command)
    confirmed = read_live_revisions(database, {"agenda"})
    assert confirmed["agenda"] > before["agenda"]
    save(repo, item, command=command)
    assert read_live_revisions(database, {"agenda"}) == confirmed


def test_repeated_start_preserves_work_and_returns_same_session(database):
    repo = adopted(database)
    item = record()
    def create(conn, session, intent):
        session.step1_note = "Preparazione iniziale"
        return {"status": "created"}
    intent = {"id_fascicolo": "F1", "id_appuntamento": "A1"}
    first = repo.execute(item["id"], "avvio", intent, command_key=str(uuid4()), expected_revision=0,
                         apply=create, initial_record=item)
    save(repo, item, version=1, text="Lavoro successivo")
    def forbidden(*args):
        raise AssertionError("Un secondo avvio non deve ricreare il lavoro")
    second = repo.execute(item["id"], "avvio", intent, command_key=str(uuid4()), expected_revision=0,
                          apply=forbidden, initial_record=item)
    assert second["record"]["id"] == first["record"]["id"]
    assert second["record"]["step1_note"] == "Lavoro successivo"
    assert second["effects"]["status"] == "already_present"
    assert len(repo.list()) == 1


def test_failed_start_does_not_leave_half_a_session(database):
    repo = adopted(database)
    item = record()
    def fail(*args):
        raise RuntimeError("Checklist non verificata")
    with pytest.raises(RuntimeError, match="Checklist"):
        repo.execute(item["id"], "avvio", {"id_fascicolo": "F1", "id_appuntamento": "A1"}, command_key=str(uuid4()), expected_revision=0,
                     apply=fail, initial_record=item)
    assert repo.list() == []
    assert database.conn.execute("SELECT COUNT(*) FROM preparazioni_commands").fetchone()[0] == 0


def test_start_replay_uses_original_receipt_when_derived_source_changes(database):
    repo = adopted(database)
    item, command = record(), str(uuid4())
    intent = {"id_fascicolo": "F1", "id_appuntamento": "A1"}
    first = repo.execute(item["id"], "avvio", intent, command_key=command, expected_revision=0,
                         apply=lambda *args: {"status": "created"}, initial_record=item)
    changed = {**item, "titolo": "Titolo aggiornato nella fonte", "creato_il": "2026-10-11T10:00:00"}
    def forbidden(*args):
        raise AssertionError("Un retry non deve ricreare la checklist")
    second = repo.execute(item["id"], "avvio", intent, command_key=command, expected_revision=0,
                          apply=forbidden, initial_record=changed)
    assert second == first


def test_same_hearing_cannot_create_another_session(database):
    first, second = record(), record()
    repo = adopted(database, records=[first])
    with pytest.raises(PreparazioneConflict, match="altra sessione"):
        repo.execute(second["id"], "avvio", {"id_fascicolo": "F1", "id_appuntamento": "A1"},
                     command_key=str(uuid4()), expected_revision=0, apply=lambda *args: {}, initial_record=second)
    assert len(repo.list()) == 1


def test_rejected_intent_cannot_write_after_source_changes(database):
    item, command = record(), str(uuid4())
    repo = adopted(database, records=[item])
    receipt = repo.reject(item["id"], "passo", {"text": "Nota"}, command_key=command,
                          expected_revision=0, code="validation", message="Presupposto non dimostrato")
    save(repo, item, text="Nuovo riscontro")
    with pytest.raises(PreparazioneRejected) as rejected:
        save(repo, item, command=command)
    assert rejected.value.result == receipt
    assert repo.get(item["id"])["record"]["step1_note"] == "Nuovo riscontro"


def test_late_rejection_returns_success_already_committed(database):
    item, command = record(), str(uuid4())
    repo = adopted(database, records=[item])
    confirmed = save(repo, item, command=command)
    rejected = repo.reject(item["id"], "passo", {"text": "Nota"}, command_key=command,
                           expected_revision=0, code="conflict", message="Risposta tardiva")
    assert rejected == confirmed


def test_rejection_does_not_emit_a_data_change(database):
    from pct.operational_live import ensure_live_schema, read_live_revisions
    ensure_live_schema(database.conn)
    item = record()
    repo = adopted(database, records=[item])
    before = read_live_revisions(database, {"agenda"})
    repo.reject(item["id"], "passo", {"text": "Nota"}, command_key=str(uuid4()),
                expected_revision=0, code="conflict", message="Bozza superata")
    assert read_live_revisions(database, {"agenda"}) == before
    assert repo.get(item["id"])["revision"] == 0
