"""La conferma HTTP deve corrispondere a un unico incasso SQL reale."""
from types import SimpleNamespace
from uuid import uuid4

from flask import Flask, g
import pytest

from pct.fatturazione import parcella_revision
from tests.test_fatturazione import invoice_status_db as invoice_status_db
from tests.test_parcella_incassi_repository import invoice_receipts as invoice_receipts


@pytest.fixture
def receipt_client(invoice_receipts, monkeypatch):
    repo, cash, manager, invoice_id = invoice_receipts
    from web.bootstrap.invoice_receipts_routes import register_invoice_receipts_routes
    repo._factory_read_modes = []
    def factory(*, readonly=False):
        repo._factory_read_modes.append(readonly)
        return repo
    monkeypatch.setattr('web.services.invoice_receipts_runtime.current_invoice_receipts', factory)
    app = Flask(__name__)
    app.config['TESTING'] = True
    permissions = {'fatturazione.leggi', 'fatturazione.scrivi'}

    @app.before_request
    def user():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda key: key in permissions)

    register_invoice_receipts_routes(app)
    body = dict(operation='receipt', amount_cents=40000, paid_on='2026-10-19',
        method='banca', note='Incasso controllato', command_key=str(uuid4()),
        expected_revision=parcella_revision(manager.get(invoice_id)))
    from web.services.invoice_receipts_runtime import receipt_command_scope
    body['scope'] = receipt_command_scope(repo, invoice_id)
    return app.test_client(), repo, cash, invoice_id, body, permissions


def test_read_is_consultative_and_repeated_write_has_one_cash_movement(receipt_client):
    client, repo, cash, invoice_id, body, _ = receipt_client
    href = f'/api/fatturazione/{invoice_id}/incassi'
    original = repo.summary(invoice_id)
    page = client.get(href)
    assert page.status_code == 200 and page.json['summary']['paid_cents'] == 0
    assert repo._factory_read_modes == [True]
    assert len(page.json['summary']['command_scope']) == 64
    assert repo.summary(invoice_id) == original and cash.load() == {}
    first = client.post(href, json=body)
    assert repo._factory_read_modes[-1] is False
    assert first.status_code == 200 and first.json['summary']['status'] == 'PARTIAL'
    replay = client.post(href, json=body)
    assert replay.status_code == 200 and replay.json['already_present']
    assert replay.json['movement_id'] == first.json['movement_id']
    assert replay.json['confirmed_command'] == {'scope': body['scope'], 'command_key': body['command_key'],
        'invoice_id': invoice_id, 'expected_revision': body['expected_revision']}
    assert len(cash.load()) == 1
    assert replay.json['summary']['receipts'][0]['movement_id'] == first.json['movement_id']


def test_lost_response_after_commit_can_recover_only_the_same_command(receipt_client, monkeypatch):
    client, repo, cash, invoice_id, body, _ = receipt_client
    original = repo.register

    def lost(**fields):
        original(**fields)
        raise RuntimeError('Risposta persa dopo la conferma SQL')

    monkeypatch.setattr(repo, 'register', lost)
    href = f'/api/fatturazione/{invoice_id}/incassi'
    response = client.post(href, json=body)
    assert response.status_code == 503 and response.json['code'] == 'outcome_not_confirmed'
    assert len(cash.load()) == 1
    monkeypatch.setattr(repo, 'register', original)
    recovered = client.post(href, json=body)
    assert recovered.status_code == 200 and recovered.json['already_present']
    assert len(cash.load()) == 1


def test_permissions_future_date_and_extra_fields_do_not_write(receipt_client):
    client, _, cash, invoice_id, body, permissions = receipt_client
    href = f'/api/fatturazione/{invoice_id}/incassi'
    permissions.remove('fatturazione.scrivi')
    assert client.post(href, json=body).status_code == 403
    assert client.get(href).json['summary']['can_write'] is False
    permissions.add('fatturazione.scrivi')
    assert client.post(href, json={**body, 'scope': '0' * 64}).status_code == 409
    assert client.post(href, json={**body, 'paid_on': '2999-01-01'}).status_code == 400
    assert client.post(href, json={**body, 'tenant': 'other'}).status_code == 400
    assert client.post(href, json={**body, 'amount_cents': True}).status_code == 400
    assert client.get('/api/fatturazione/missing/incassi').status_code == 404
    assert cash.load() == {}


def test_write_permission_alone_cannot_read_or_register_receipts(receipt_client):
    client, repo, cash, invoice_id, body, permissions = receipt_client
    permissions.remove('fatturazione.leggi')
    href = f'/api/fatturazione/{invoice_id}/incassi'
    assert client.get(href).status_code == 403
    assert client.post(href, json=body).status_code == 403
    assert repo._factory_read_modes == []
    assert cash.load() == {}


def test_session_is_required_before_opening_financial_repository(receipt_client):
    client, repo, cash, invoice_id, body, _ = receipt_client

    @client.application.before_request
    def logged_out():
        g.utente_corrente = None

    href = f'/api/fatturazione/{invoice_id}/incassi'
    assert client.get(href).status_code == 401
    assert client.post(href, json=body).status_code == 401
    assert repo._factory_read_modes == []
    assert cash.load() == {}


def test_changed_invalid_retry_cannot_discard_an_already_committed_command(receipt_client):
    client, _, cash, invoice_id, body, _ = receipt_client
    href = f'/api/fatturazione/{invoice_id}/incassi'
    assert client.post(href, json=body).status_code == 200
    for change in ({'paid_on': '2999-01-01'}, {'amount_cents': True}):
        response = client.post(href, json={**body, **change})
        assert response.status_code == 409
        assert response.json['code'] == 'command_conflict'
    assert len(cash.load()) == 1
