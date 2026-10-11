"""Guardrail del protocollo unico, non accettazione del browser."""
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from pct.udienze.repository import PreparazioneRejected
from web.services.preparazione_udienza_commands import execute_command
from tests.test_preparazioni_outcome_delivery import TODAY, context as context, intent
from tests.test_preparazioni_sql_repository import database as database


def execute(repo, item, operation, values, *, revision=0, key=None):
    return execute_command(repo, item["id"], operation, values, command_key=key or str(uuid4()), expected_revision=revision, today=TODAY)


@pytest.mark.parametrize("values", [
    {"passo": 4, "campi": {"precheck_firma_ok": "false"}},
    {"passo": 5, "campi": {}},
    {"passo": 1, "campi": {"campo_non_previsto": "non scartare"}},
    {"passo": 1, "campi": {}, "conferma": 1},
])
def test_bad_intent_persistently_rejected(context, values):
    db, repo, item = context
    key = str(uuid4())
    with pytest.raises(PreparazioneRejected) as first:
        execute(repo, item, "passo", values, key=key)
    assert first.value.result["code"] == "validation"
    assert repo.get(item["id"])["revision"] == 0
    assert db.conn.execute("SELECT esito FROM audit_log WHERE azione='udienza.passo'").fetchone()[0] == "RIFIUTATO"
    with pytest.raises(PreparazioneRejected) as second:
        execute(repo, item, "passo", values, key=key)
    assert second.value.result == first.value.result


def test_step_uses_native_rules_and_conflict_preserves_source(context):
    db, repo, item = context
    result = execute(repo, item, "passo", {"passo": 1, "campi": {"step1_note": "Prima nota"}, "conferma": True})
    assert result["record"]["step_corrente"] == 2 and result["record"]["step1_confermato"] is True
    with pytest.raises(PreparazioneRejected) as rejected:
        execute(repo, item, "passo", {"passo": 1, "campi": {"step1_note": "Sovrascrittura superata"}})
    assert rejected.value.result["code"] == "conflict"
    assert repo.get(item["id"])["record"]["step1_note"] == "Prima nota"
    assert db.conn.execute("SELECT count(*) FROM preparazioni_commands").fetchone()[0] == 2


def test_extra_document_same_fact_confirmed_already_present(context):
    _, repo, item = context
    execute(repo, item, "documento-extra", {"etichetta": "Originale procura"})
    second = execute(repo, item, "documento-extra", {"etichetta": "Originale   procura"}, revision=1)
    assert second["effects"]["status"] == "already_present"
    assert len(second["record"]["checklist_documenti"]) == 1


def test_delete_keeps_delivered_facts_and_replay_receipt(context):
    db, repo, item = context
    execute(repo, item, "esito", intent())
    key = str(uuid4())
    removed = execute(repo, item, "elimina", {}, revision=1, key=key)
    assert removed["deleted"] is True and repo.get(item["id"]) is None
    assert execute(repo, item, "elimina", {}, revision=1, key=key) == removed
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 1
    assert db.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 2
    assert db.conn.execute("SELECT count(*) FROM audit_log WHERE azione='udienza.elimina'").fetchone()[0] == 1


def test_two_operators_same_version_one_delivery_one_persistent_conflict(context):
    from pct.storage import StudioDB
    from pct.udienze.repository import PreparazioniRepository

    db, _, item = context
    gate = Barrier(2)
    def submit(actor):
        owned = StudioDB(db.db_path, initialize_schema=False)
        try:
            repo = PreparazioniRepository(owned, "studio", actor=actor)
            gate.wait(timeout=10)
            try:
                return execute(repo, item, "esito", intent())
            except PreparazioneRejected as exc:
                return exc.result
        finally:
            owned.chiudi()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ("operatore-uno", "operatore-due")))
    assert sum(result.get("status") == "rejected" for result in results) == 1
    assert next(result for result in results if result.get("status") == "rejected")["code"] == "conflict"
    assert db.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 2
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 1
    assert db.conn.execute("SELECT count(*) FROM preparazioni_commands").fetchone()[0] == 2


def test_verbal_draft_persists_without_recording_hearing_outcome(context):
    db, repo, item = context
    key = str(uuid4())
    values = {"passo": 3, "campi": {"verbale_preparazione": "L’avvocato chiede un termine per le note."}}
    result = execute(repo, item, "passo", values, key=key)
    assert repo.get(item["id"])["record"]["verbale_preparazione"] == values["campi"]["verbale_preparazione"]
    assert result["record"]["esito_note_verbale"] == ""
    assert execute(repo, item, "passo", values, key=key) == result
    assert db.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 1
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 0
    with pytest.raises(PreparazioneRejected):
        execute(repo, item, "passo", {"passo": 3, "campi": {"verbale_preparazione": "Bozza concorrente"}})
    assert repo.get(item["id"])["record"]["verbale_preparazione"] == values["campi"]["verbale_preparazione"]
