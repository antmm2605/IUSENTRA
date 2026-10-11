"""Avvio governato: replay, identità e rollback, distinto dalla prova UI."""
import json
from uuid import uuid4

import pytest

from tests.test_preparazioni_outcome_delivery import context as context
from tests.test_preparazioni_sql_repository import database as database
from web.services.preparazione_udienza_start import start_command


def start(repo, key=None):
    return start_command(repo, fascicolo_id="F1", appuntamento_id="A1", command_key=key or str(uuid4()),
                         avvocato="Avvocato controllato")


def fresh(context):
    db, repo, _ = context
    db.conn.execute("DELETE FROM preparazioni_sessions")
    db.conn.execute("UPDATE fascicoli SET documenti_json='[]'")
    db.conn.commit()
    return db, repo


def test_start_native_replay_and_second_start_preserve_work(context):
    db, repo = fresh(context)
    command = str(uuid4())
    first = start(repo, command)
    assert first["record"]["titolo"] == "Udienza Udienza controllata"
    assert first["record"]["avvocato"] == "Avvocato controllato"
    assert start(repo, command) == first
    from web.services.preparazione_udienza_commands import execute_command
    from datetime import date
    saved = execute_command(repo, first["record"]["id"], "passo", {"passo": 1, "campi": {"step1_note": "Bozza salvata"}},
                            command_key=str(uuid4()), expected_revision=1, today=date(2026, 10, 11))
    reopened = start(repo)
    assert reopened["record"]["step1_note"] == "Bozza salvata"
    assert reopened["revision"] == saved["revision"]
    assert reopened["effects"]["status"] == "already_present"
    assert db.conn.execute("SELECT count(*) FROM preparazioni_sessions").fetchone()[0] == 1


def test_start_client_discordance_rolls_back_session(context):
    db, repo = fresh(context)
    row = db.conn.execute("SELECT dati_json FROM appuntamenti WHERE id='A1'").fetchone()
    payload = json.loads(row[0])
    payload["id_cliente"] = "ALTRO_CLIENTE"
    db.conn.execute("UPDATE appuntamenti SET dati_json=? WHERE id='A1'", (json.dumps(payload),))
    db.conn.commit()
    command = str(uuid4())
    with pytest.raises(ValueError, match="discordante"):
        start(repo, command)
    assert repo.list() == []
    assert db.conn.execute("SELECT count(*) FROM preparazioni_commands").fetchone()[0] == 1
    payload["id_cliente"] = ""
    db.conn.execute("UPDATE appuntamenti SET dati_json=? WHERE id='A1'", (json.dumps(payload),))
    db.conn.commit()
    with pytest.raises(ValueError, match="discordante"):
        start(repo, command)
    assert repo.list() == []


def test_start_audit_failure_leaves_no_partial_preparation(context):
    db, repo = fresh(context)
    db.conn.execute("CREATE TRIGGER fail_start BEFORE INSERT ON audit_log WHEN NEW.azione='udienza.avvio' "
                    "BEGIN SELECT RAISE(ABORT,'audit indisponibile'); END")
    db.conn.commit()
    with pytest.raises(Exception, match="audit indisponibile"):
        start(repo)
    assert repo.list() == []
    assert db.conn.execute("SELECT count(*) FROM preparazioni_commands").fetchone()[0] == 0


def test_replay_start_after_delete_does_not_recreate(context):
    db, repo = fresh(context)
    command = str(uuid4())
    first = start(repo, command)
    from web.services.preparazione_udienza_commands import execute_command
    from datetime import date
    execute_command(repo, first["record"]["id"], "elimina", {}, command_key=str(uuid4()),
                    expected_revision=1, today=date(2026, 10, 11))
    assert start(repo, command) == first
    assert repo.list() == []
