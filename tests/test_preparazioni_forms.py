"""Checklist del modulo classico: un solo commit e rifiuto delle bozze superate."""
from uuid import uuid4

import pytest
from werkzeug.datastructures import MultiDict

from pct.udienze.repository import PreparazioneRejected
from pct.wizard_pro import DocumentoChecklist
from tests.test_preparazioni_outcome_delivery import context as context
from tests.test_preparazioni_sql_repository import database as database
from web.services.preparazione_udienza_form_commands import save_form
from web.services.preparazione_udienza_sql_runtime import GestionePreparazioniSql


def form(**kwargs):
    return MultiDict({"commandKey": str(uuid4()), "expectedRevision": "0", "documentCount": "1",
        "doc_id_0": "D1", "doc_label_0": "Documento controllato", **kwargs})


def test_classic_checklist_notes_extra_and_confirmation_one_commit(context):
    db, repo, item = context
    from pct.udienze.repository import encode
    item["checklist_documenti"] = [DocumentoChecklist("D1", "Documento controllato", "ALTRO", False, "da_portare").to_dict()]
    db.conn.execute("UPDATE preparazioni_sessions SET payload_json=?", (encode(item),))
    db.conn.commit()
    manager = GestionePreparazioniSql(repo)
    session = manager.carica(item["id"])
    submitted = form(doc_stato_0="pronto", doc_note_0="Originale verificato", doc_extra_label="Copia di cortesia")
    first = save_form(manager, session, 2, submitted)
    assert first["record"]["step2_confermato"] and first["record"]["step_corrente"] == 3
    assert first["record"]["checklist_documenti"][0]["note"] == "Originale verificato"
    assert first["record"]["checklist_documenti"][0]["stato"] == "pronto"
    assert len(first["record"]["checklist_documenti"]) == 2
    # Simula POST ripetuto con lo stesso modulo, anche se la sessione ora ha un'altra riga.
    assert save_form(manager, manager.carica(item["id"]), 2, submitted) == first
    assert db.conn.execute("SELECT count(*) FROM preparazioni_commands").fetchone()[0] == 1


def test_classic_invalid_document_rolls_back_notes_extra_and_step(context):
    db, repo, item = context
    from pct.udienze.repository import encode
    item["checklist_documenti"] = [DocumentoChecklist("D1", "Documento controllato", "ALTRO", False, "da_portare").to_dict()]
    db.conn.execute("UPDATE preparazioni_sessions SET payload_json=?", (encode(item),))
    db.conn.commit()
    manager = GestionePreparazioniSql(repo)
    with pytest.raises(PreparazioneRejected):
        save_form(manager, manager.carica(item["id"]), 2, form(doc_stato_0="sconosciuto", doc_note_0="Non salvare", doc_extra_label="Non aggiungere"))
    current = repo.get(item["id"])
    assert current["revision"] == 0 and not current["record"]["step2_confermato"]
    assert current["record"]["checklist_documenti"][0]["note"] == ""
    assert len(current["record"]["checklist_documenti"]) == 1
