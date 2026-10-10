"""Contratto HTTP della versione Agenda; SQL reale, Flask come guardrail."""
from types import SimpleNamespace

import pytest
from flask import Flask, g
from pct.agenda import Agenda, TipoAppuntamento
from pct.storage import StudioDB
from pct.scadenziario import GestioneScadenziario
from web.bootstrap.dashboard_routes import register_dashboard_routes


@pytest.fixture
def context(tmp_path):
    db = StudioDB.get(str(tmp_path / "studio.db"))
    path = str(tmp_path / "agenda.json")
    def open_agenda():
        return Agenda(path, studio_db=db)
    app = Flask(__name__)
    app.secret_key = "controlled-http-test"
    @app.before_request
    def current_user():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda permission: True)
    actions = []
    def unused():
        return None
    register_dashboard_routes(app, get_agenda=open_agenda,
        get_scadenziario=lambda: GestioneScadenziario(str(tmp_path / "scadenze.json"), studio_db=db),
        get_fascicoli=unused, get_clienti=unused, get_timesheet=unused, get_preventivi=unused,
        get_fatturazione=unused, get_pagamenti=unused, get_condivisioni=unused,
        get_workspace_intelligente=unused, get_calendar_sync=unused,
        audit=lambda *args, **kwargs: actions.append(args),
        sync_pubblica=lambda *args: actions.append(args), track_recente=lambda *args: None)
    item = open_agenda().aggiungi("Appuntamento controllato", TipoAppuntamento.ALTRO, "2026-12-15T10:00:00")
    return app.test_client(), open_agenda, item.id, actions


def body(version=None):
    value = {"titolo": "Modifica controllata", "tipo": "ALTRO", "data": "2026-12-15", "ora": "10:00"}
    if version is not None:
        value["expected_version"] = version
    return value


def test_single_record_exposes_version(context):
    client, agenda, identifier, _ = context
    response = client.get(f"/api/agenda/{identifier}")
    assert response.status_code == 200
    assert response.json["expected_version"] == agenda().revision_token(identifier)


def test_day_availability_api_retains_existing_appointment(context):
    client, _, identifier, _ = context
    response = client.get("/api/agenda?da=2026-12-15&a=2026-12-15")
    assert response.status_code == 200
    assert [record["id"] for record in response.json] == [identifier]


def test_json_write_requires_loaded_version(context):
    client, agenda, identifier, actions = context
    response = client.post(f"/agenda/{identifier}/modifica", data=body(), headers={"Accept": "application/json"})
    assert response.status_code == 409
    assert response.json["conflict"] is True
    assert agenda().get(identifier).titolo == "Appuntamento controllato"
    assert not actions


def test_stale_browser_version_is_explicit_conflict(context):
    client, agenda, identifier, actions = context
    version = client.get(f"/api/agenda/{identifier}").json["expected_version"]
    agenda().modifica(identifier, titolo="Aggiornamento concorrente")
    response = client.post(f"/agenda/{identifier}/modifica", data=body(version), headers={"Accept": "application/json"})
    assert response.status_code == 409
    assert agenda().get(identifier).titolo == "Aggiornamento concorrente"
    assert not actions


def test_current_browser_version_is_persisted(context):
    client, agenda, identifier, actions = context
    version = client.get(f"/api/agenda/{identifier}").json["expected_version"]
    response = client.post(f"/agenda/{identifier}/modifica", data=body(version), headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json["ok"] is True
    assert agenda().get(identifier).titolo == "Modifica controllata"
    assert actions
