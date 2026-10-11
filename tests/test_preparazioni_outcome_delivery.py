"""Consegna nativa atomica; guardrail distinti dalla prova UI reale."""
import json
from datetime import date
from uuid import uuid4

import pytest

from pct.agenda import Appuntamento, TipoAppuntamento
from pct.agenda_sql_writer import COLUMNS, row_values
from pct.fascicoli import Fascicolo, GestioneFascicoli, TipoFascicolo
from pct.udienze.delivery import deliver_outcome
from pct.udienze.repository import PreparazioneConflict
from tests.test_preparazioni_sql_repository import adopted, database as database, record

TODAY = date(2026, 10, 10)


@pytest.fixture
def context(database):
    item = record()
    fascicolo = Fascicolo(id="F1", numero="PROVA/1", titolo="Udienza controllata", tipo=TipoFascicolo.CIVILE,
                          data_prossima_udienza="2026-10-09")
    payload = GestioneFascicoli._dati_json_snello(fascicolo.to_dict())
    payload["metadata_da_preservare"] = {"decisione": "manuale"}
    database.conn.execute("INSERT INTO fascicoli (id,numero,stato,dati_json,attivita_json,documenti_json,modificato_il) VALUES (?,?,?,?,?,?,?)",
        ("F1", fascicolo.numero, fascicolo.stato.value, json.dumps(payload), "[]", '[{"id":"D1","fonte":"originale"}]', fascicolo.modificato_il))
    app = Appuntamento(id="A1", titolo="Udienza controllata", tipo=TipoAppuntamento.UDIENZA,
                      data_ora="2026-10-09T15:00:00", durata_minuti=60, luogo="Ufficio controllato")
    database.conn.execute(f"INSERT INTO appuntamenti ({','.join(COLUMNS)}) VALUES ({','.join('?' for _ in COLUMNS)})", row_values(app))
    database.conn.commit()
    return database, adopted(database, records=[item]), item


def intent():
    return {"esito": "rinvio", "rinvioData": "2026-12-16", "rinvioOra": "15:00", "noteVerbale": "Verbale controllato",
            "azioni": "Preparare note", "termini": [{"descrizione": "Note assegnate", "data": "2026-12-10", "perentorio": True}]}


def deliver(repo, item, values, *, revision=0, command=None):
    return repo.execute(item["id"], "esito", values, command_key=command or str(uuid4()), expected_revision=revision,
        apply=lambda conn, session, incoming: deliver_outcome(conn, session, incoming, tenant="studio", actor="avvocato", today=TODAY))


def test_native_outcome_all_effects_confirmed_and_replay(context):
    db, repo, item = context
    command = str(uuid4())
    result = deliver(repo, item, intent(), command=command)
    assert result["record"]["stato"] == "completato"
    assert db.conn.execute("SELECT stato FROM appuntamenti WHERE id='A1'").fetchone()[0] == "COMPLETATO"
    assert db.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 2
    linked = json.loads(db.conn.execute("SELECT dati_json FROM appuntamenti WHERE id<>'A1'").fetchone()[0])
    assert linked["id_fascicolo"] == "F1"
    assert db.conn.execute("SELECT count(*) FROM scadenze WHERE id_fascicolo='F1'").fetchone()[0] == 1
    row = db.conn.execute("SELECT dati_json,attivita_json,documenti_json FROM fascicoli WHERE id='F1'").fetchone()
    payload = json.loads(row[0])
    assert payload["data_prossima_udienza"] == "2026-12-16"
    assert payload["metadata_da_preservare"] == {"decisione": "manuale"}
    assert len(json.loads(row[1])) == 1
    assert row[2] == '[{"id":"D1","fonte":"originale"}]'
    assert deliver(repo, item, intent(), command=command) == result
    assert repo.get(item["id"])["revision"] == 1


def test_activity_keeps_professional_name_separate_from_audit_actor(context):
    db, repo, item = context
    def named_session(conn, session, values):
        session.avvocato = "Professionista controllato"
        return {"kind": "passo", "status": "confirmed"}
    repo.execute(item["id"], "passo", {}, command_key=str(uuid4()), expected_revision=0, apply=named_session)
    deliver(repo, item, intent(), revision=1)
    activity = json.loads(db.conn.execute("SELECT attivita_json FROM fascicoli WHERE id='F1'").fetchone()[0])[0]
    assert activity["avvocato"] == "Professionista controllato"
    # Il recapito responsabile della scadenza conserva invece l'identità macchina.
    deadline = json.loads(db.conn.execute("SELECT dati_json FROM scadenze LIMIT 1").fetchone()[0])
    assert deadline["id_utente_responsabile"] == "avvocato"


def test_postponed_case_link_survives_deleting_preparation(context):
    from web.services.preparazione_udienza_commands import execute_command
    db, repo, item = context
    result = deliver(repo, item, intent())
    execute_command(repo, item["id"], "elimina", {}, command_key=str(uuid4()),
                    expected_revision=1, today=TODAY)
    assert repo.get(item["id"]) is None
    postponed = Appuntamento.from_dict(json.loads(db.conn.execute(
        "SELECT dati_json FROM appuntamenti WHERE id=?", (result["record"]["id_appuntamento_rinvio"],)).fetchone()[0]))
    assert postponed.id_fascicolo == "F1"
    assert db.conn.execute("SELECT count(*) FROM scadenze WHERE id_fascicolo='F1'").fetchone()[0] == 1


def test_new_command_same_fact_does_not_duplicate(context):
    db, repo, item = context
    first = deliver(repo, item, intent())
    second = deliver(repo, item, intent(), revision=1)
    assert second["effects"]["created"] == []
    assert second["effects"]["rinvio_id"] == first["effects"]["rinvio_id"]
    assert second["effects"]["deadline_ids"] == first["effects"]["deadline_ids"]
    assert db.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 2
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 1
    assert len(json.loads(db.conn.execute("SELECT attivita_json FROM fascicoli").fetchone()[0])) == 1


def test_audit_failure_rolls_back_all_native_effects(context):
    db, repo, item = context
    before = tuple(db.conn.execute("SELECT stato,dati_json,attivita_json,documenti_json FROM fascicoli").fetchone())
    db.conn.execute("CREATE TRIGGER fail_outcome_audit BEFORE INSERT ON audit_log WHEN NEW.azione='udienza.esito' BEGIN SELECT RAISE(ABORT,'audit non disponibile'); END")
    db.conn.commit()
    with pytest.raises(Exception, match="audit non disponibile"):
        deliver(repo, item, intent())
    assert tuple(db.conn.execute("SELECT stato,dati_json,attivita_json,documenti_json FROM fascicoli").fetchone()) == before
    assert db.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 1
    assert db.conn.execute("SELECT stato FROM appuntamenti").fetchone()[0] != "COMPLETATO"
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 0
    assert repo.get(item["id"])["revision"] == 0
    assert db.conn.execute("SELECT count(*) FROM preparazioni_commands").fetchone()[0] == 0


@pytest.mark.parametrize("change", [{"rinvioOra": "99:90"}, {"termini": [{"descrizione": "", "data": "2026-12-10"}]},
    {"termini": [{"descrizione": "Note", "data": "2026-12-10"}] * 11}, {"extra": "non ignorare"}])
def test_invalid_rows_never_discarded(context, change):
    db, repo, item = context
    with pytest.raises(ValueError):
        deliver(repo, item, {**intent(), **change})
    assert db.conn.execute("SELECT count(*) FROM appuntamenti").fetchone()[0] == 1
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 0
    assert repo.get(item["id"])["revision"] == 0


def test_foreign_deadline_reference_rejected(context):
    db, repo, item = context
    values = intent()
    values["termini"][0]["id_scadenza"] = "termine-di-altra-preparazione"
    with pytest.raises(ValueError, match="estraneo"):
        deliver(repo, item, values)
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 0


def test_manual_deadline_change_not_overwritten(context):
    db, repo, item = context
    first = deliver(repo, item, intent())
    deadline = first["effects"]["deadline_ids"][0]
    raw = db.conn.execute("SELECT dati_json FROM scadenze WHERE id=?", (deadline,)).fetchone()[0]
    payload = json.loads(raw)
    payload["titolo"] = "Decisione successiva dell'avvocato"
    db.conn.execute("UPDATE scadenze SET titolo=?,dati_json=? WHERE id=?", (payload["titolo"], json.dumps(payload), deadline))
    db.conn.commit()
    with pytest.raises(PreparazioneConflict, match="preservata"):
        deliver(repo, item, intent(), revision=1)
    assert db.conn.execute("SELECT titolo FROM scadenze WHERE id=?", (deadline,)).fetchone()[0] == payload["titolo"]
    assert repo.get(item["id"])["revision"] == 1


def test_outcome_note_updates_same_native_activity(context):
    db, repo, item = context
    first = deliver(repo, item, intent())
    second = deliver(repo, item, {**intent(), "noteVerbale": "Verbale rettificato"}, revision=1)
    assert second["effects"]["activity_id"] == first["effects"]["activity_id"]
    activities = json.loads(db.conn.execute("SELECT attivita_json FROM fascicoli").fetchone()[0])
    assert len(activities) == 1 and "Verbale rettificato" in activities[0]["descrizione"]


def test_sql_column_discordance_cannot_be_normalized_away(context):
    db, repo, item = context
    db.conn.execute("UPDATE appuntamenti SET stato='ANNULLATO' WHERE id='A1'")
    db.conn.commit()
    with pytest.raises(PreparazioneConflict, match="Colonne SQL"):
        deliver(repo, item, intent())
    assert db.conn.execute("SELECT stato FROM appuntamenti WHERE id='A1'").fetchone()[0] == "ANNULLATO"
    assert repo.get(item["id"])["revision"] == 0


def test_cancelled_postponement_stays_cancelled(context):
    db, repo, item = context
    first = deliver(repo, item, intent())
    key = first["effects"]["rinvio_id"]
    payload = json.loads(db.conn.execute("SELECT dati_json FROM appuntamenti WHERE id=?", (key,)).fetchone()[0])
    payload["stato"] = "ANNULLATO"
    db.conn.execute("UPDATE appuntamenti SET stato='ANNULLATO',dati_json=? WHERE id=?", (json.dumps(payload), key))
    db.conn.commit()
    with pytest.raises(PreparazioneConflict, match="rinvio"):
        deliver(repo, item, intent(), revision=1)
    assert db.conn.execute("SELECT stato FROM appuntamenti WHERE id=?", (key,)).fetchone()[0] == "ANNULLATO"
    assert repo.get(item["id"])["revision"] == 1


def test_changed_deadline_updates_same_open_reference(context):
    db, repo, item = context
    first = deliver(repo, item, intent())
    values = intent()
    values["termini"][0].update(id_scadenza=first["effects"]["deadline_ids"][0], data="2026-12-11")
    second = deliver(repo, item, values, revision=1)
    assert second["effects"]["deadline_ids"] == first["effects"]["deadline_ids"]
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 1
    assert db.conn.execute("SELECT data_scadenza FROM scadenze").fetchone()[0] == "2026-12-11"


def test_completed_deadline_cannot_be_reopened_by_outcome(context):
    db, repo, item = context
    first = deliver(repo, item, intent())
    key = first["effects"]["deadline_ids"][0]
    payload = json.loads(db.conn.execute("SELECT dati_json FROM scadenze WHERE id=?", (key,)).fetchone()[0])
    payload["stato"] = "COMPLETATO"
    db.conn.execute("UPDATE scadenze SET stato='COMPLETATO',dati_json=? WHERE id=?", (json.dumps(payload), key))
    db.conn.commit()
    values = intent()
    values["termini"][0].update(id_scadenza=key, data="2026-12-11")
    with pytest.raises(PreparazioneConflict, match="già lavorato"):
        deliver(repo, item, values, revision=1)
    assert db.conn.execute("SELECT stato,data_scadenza FROM scadenze WHERE id=?", (key,)).fetchone()[0] == "COMPLETATO"
    assert repo.get(item["id"])["revision"] == 1
