"""Contratto HTTP su SQL reale controllato; non accettazione dell'interfaccia."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask, g

from pct import agenda_sql_writer
from pct.agenda import Appuntamento
from pct.fascicoli import GestioneFascicoli
from pct.udienze.delivery import _AgendaSnapshot, _FascicoloSnapshot, _ScadenzeSnapshot, _rows
from tests.test_preparazioni_outcome_delivery import context as context
from tests.test_preparazioni_sql_repository import database as database
from web.bootstrap.preparazione_udienza_routes import register_preparazione_udienza_routes
from web.services.preparazione_udienza_sql_runtime import GestionePreparazioniSql


@pytest.fixture
def http(context, monkeypatch):
    from web import helpers
    db, repo, item = context
    db.conn.execute("UPDATE fascicoli SET documenti_json='[]'")
    db.conn.commit()
    manager = GestionePreparazioniSql(repo)
    def cases():
        return _FascicoloSnapshot(GestioneFascicoli._row_to_fascicolo(dict(db.conn.execute("SELECT * FROM fascicoli WHERE id='F1'").fetchone())))
    def agenda():
        return _AgendaSnapshot(_rows(db.conn, "appuntamenti", agenda_sql_writer, "1=1", (), Appuntamento)[2])
    monkeypatch.setattr(helpers, "get_wizard_pro", lambda: manager)
    monkeypatch.setattr(helpers, "get_fascicoli", cases)
    monkeypatch.setattr(helpers, "get_agenda", agenda)
    monkeypatch.setattr(helpers, "get_scadenziario", lambda: _ScadenzeSnapshot({}))
    app = Flask(__name__)
    permissions = {"agenda.leggi", "agenda.scrivi", "scadenziario.scrivi", "fascicoli.scrivi"}
    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(id="avvocato", username="avvocato", nome_completo="Avvocato controllato",
                                           ha_permesso=lambda permission: permission in permissions)
    register_preparazione_udienza_routes(app, {"audit": lambda *args, **kwargs: pytest.fail("Audit esterno al comando SQL")})
    with app.test_client() as client:
        yield client, db, repo, item, permissions, manager


def test_http_preconditions_and_exact_replay(http):
    client, db, repo, item, _, manager = http
    url = f'/api/v1/ui/preparazione-udienza/{item["id"]}/passo'
    assert client.post(url, json={"passo": 1}).status_code == 428
    assert repo.get(item["id"])["revision"] == 0
    body = {"commandKey": str(uuid4()), "expectedRevision": 0, "passo": 1, "campi": {"step1_note": "Nota confermata"}}
    first = client.post(url, json=body)
    assert first.status_code == 200
    payload = first.get_json()
    assert payload["dati"]["campi"]["step1_note"] == "Nota confermata"
    assert payload["confirmedCommand"] == {"scope": manager.write_protocol["scope"], "sessionId": item["id"],
        "commandKey": body["commandKey"], "committedRevision": 1}
    assert client.post(url, json=body).get_json()["confirmedCommand"] == payload["confirmedCommand"]
    assert db.conn.execute("SELECT count(*) FROM preparazioni_commands").fetchone()[0] == 1


def test_http_conflict_persistent_and_permission_no_write(http):
    client, _, repo, item, permissions, manager = http
    url = f'/api/v1/ui/preparazione-udienza/{item["id"]}/passo'
    body = {"commandKey": str(uuid4()), "expectedRevision": 0, "passo": 1, "campi": {"step1_note": "Prima"}}
    assert client.post(url, json=body).status_code == 200
    body = {**body, "commandKey": str(uuid4()), "campi": {"step1_note": "Bozza vecchia"}}
    rejected = client.post(url, json=body)
    assert rejected.status_code == 409
    assert rejected.get_json()["rejectedCommand"]["scope"] == manager.write_protocol["scope"]
    assert rejected.get_json()["rejectedCommand"]["commandKey"] == body["commandKey"]
    assert client.post(url, json=body).get_json() == rejected.get_json()
    assert repo.get(item["id"])["record"]["step1_note"] == "Prima"
    permissions.remove("agenda.scrivi")
    assert client.post(url, json={**body, "commandKey": str(uuid4())}).status_code == 403
    assert repo.get(item["id"])["revision"] == 1


def test_http_esito_missing_second_permission_no_side_effect(http):
    client, db, repo, item, permissions, _ = http
    permissions.remove("scadenziario.scrivi")
    from tests.test_preparazioni_outcome_delivery import intent
    result = client.post(f'/api/v1/ui/preparazione-udienza/{item["id"]}/esito', json={**intent(),
        "commandKey": str(uuid4()), "expectedRevision": 0})
    assert result.status_code == 403
    assert repo.get(item["id"])["revision"] == 0
    assert db.conn.execute("SELECT count(*) FROM scadenze").fetchone()[0] == 0

def test_esito_requires_fascicolo_write_permission(http):
    client, _, repo, item, permissions, _ = http
    permissions.remove("fascicoli.scrivi")
    response = client.post(f'/api/v1/ui/preparazione-udienza/{item["id"]}/esito', json={"commandKey": str(uuid4()), "expectedRevision": 0})
    assert response.status_code == 403 and repo.get(item["id"])["revision"] == 0
