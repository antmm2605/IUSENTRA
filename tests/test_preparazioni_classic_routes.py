"""Scrittore classico governato: bozza leggibile anche su conflitto o risposta incerta."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask, g
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from tests.test_preparazioni_outcome_delivery import context as context
from tests.test_preparazioni_sql_repository import database as database
from web.services.preparazione_udienza_sql_runtime import GestionePreparazioniSql


@pytest.fixture
def classic(context, monkeypatch):
    from web.blueprints import wizard_pro as module
    db, repo, item = context
    manager = GestionePreparazioniSql(repo)
    monkeypatch.setattr(module, "get_wizard_pro", lambda: manager)
    monkeypatch.setattr(module, "get_fascicoli", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(module, "get_agenda", lambda: SimpleNamespace(get=lambda key: None))
    app = Flask(__name__)
    app.secret_key = "prova-tecnica"
    app.jinja_loader = ChoiceLoader([DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(str(Path(__file__).parents[1] / "web/templates"))])
    permissions = {"agenda.leggi", "agenda.scrivi", "scadenziario.scrivi", "fascicoli.scrivi"}
    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(id="avvocato", username="avvocato", nome_completo="Avvocato controllato",
                                           ha_permesso=lambda permission: permission in permissions)
    app.register_blueprint(module.wizard_pro_bp)
    with app.test_client() as client:
        yield client, db, repo, item, manager, permissions


def test_classic_save_replay_conflict_preserves_submitted_text(classic):
    client, _, repo, item, _, _ = classic
    url = f'/wizard-pro/{item["id"]}/step/3'
    body = {"commandKey": str(uuid4()), "expectedRevision": "0", "note_preparazione": "Prima nota"}
    assert client.post(url, data=body).status_code == 302
    assert client.post(url, data=body).status_code == 302
    assert repo.get(item["id"])["revision"] == 1
    rejected = client.post(url, data={**body, "commandKey": str(uuid4()), "note_preparazione": '<script>Bozza non salvata</script>'})
    assert rejected.status_code == 409
    html = rejected.get_data(as_text=True)
    assert "Bozza non salvata" in html and "&lt;script&gt;" in html
    assert "Recupera lo stesso salvataggio" not in html
    assert repo.get(item["id"])["record"]["note_preparazione"] == "Prima nota"


def test_classic_uncertain_response_retries_original_command(classic, monkeypatch):
    client, _, repo, item, manager, _ = classic
    body = {"commandKey": str(uuid4()), "expectedRevision": "0", "note_preparazione": "Nota da recuperare"}
    def unavailable(*args, **kwargs):
        raise RuntimeError("Guasto controllato")
    monkeypatch.setattr(manager, "execute", unavailable)
    result = client.post(f'/wizard-pro/{item["id"]}/step/3', data=body)
    html = result.get_data(as_text=True)
    assert result.status_code == 503
    assert "Recupera lo stesso salvataggio" in html and body["commandKey"] in html
    assert 'name="expectedRevision" value="0"' in html
    assert "Nota da recuperare" in html
    assert repo.get(item["id"])["revision"] == 0


def test_classic_esito_requires_both_permissions(classic):
    client, _, repo, item, _, permissions = classic
    permissions.remove("scadenziario.scrivi")
    result = client.post(f'/wizard-pro/{item["id"]}/step/5', data={"commandKey": str(uuid4()), "expectedRevision": "0"})
    assert result.status_code == 403 and repo.get(item["id"])["revision"] == 0

def test_classic_esito_requires_fascicolo_permission(classic):
    client, _, repo, item, _, permissions = classic
    permissions.remove("fascicoli.scrivi")
    response = client.post(f'/wizard-pro/{item["id"]}/step/5', data={"commandKey": str(uuid4()), "expectedRevision": "0"})
    assert response.status_code == 403 and repo.get(item["id"])["revision"] == 0
