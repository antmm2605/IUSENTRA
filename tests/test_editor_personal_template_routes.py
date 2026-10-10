"""Persistenza SQL e autorizzazione dei modelli; guardrail prima della prova UI."""
from types import SimpleNamespace
from uuid import uuid4

from flask import Flask, g, jsonify

from pct.template_atti_repository import GestioneTemplateRepository
from web.bootstrap.editor_personal_template_routes import register_editor_personal_template_routes


def test_sql_model_api_replay_refill_permissions_and_invalid_input(tmp_path):
    repo = GestioneTemplateRepository(str(tmp_path / 'models.db'))
    app = Flask(__name__)
    permissions = {'fascicoli.leggi', 'fascicoli.scrivi'}

    @app.before_request
    def context():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda name: name in permissions)

    def resolve(identifier):
        if identifier != 'F2':
            return jsonify(ok=False), 404
        return jsonify(fields=[{'id': 'cliente.nome', 'value': 'Seconda persona', 'available': True}], matterId='F2', clientId='C2')

    register_editor_personal_template_routes(app, audit=lambda *a, **kw: None, get_repository=lambda: repo, resolve_context=resolve)
    client = app.test_client()
    payload = {'command_id': str(uuid4()), 'titolo': 'Modello controllato', 'html': '<p><span data-iu-linked-field="cliente.nome" data-iu-linked-client="C1">Prima persona</span></p>'}
    result = client.post('/api/editor/modelli-personali', json=payload)
    assert result.status_code == 201
    identifier = result.json['id']
    assert client.post('/api/editor/modelli-personali', json=payload).json == result.json
    model = client.get('/api/editor/modelli-personali/' + identifier).json['html']
    assert 'Prima persona' not in model and 'C1' not in model
    filled = client.get('/api/editor/F2/modelli-personali/' + identifier + '/compila')
    assert filled.status_code == 200 and 'Seconda persona' in filled.json['html']
    assert 'data-iu-linked-client="C2"' in filled.json['html']
    assert client.get('/api/editor/ALTRO/modelli-personali/' + identifier + '/compila').status_code == 404
    assert client.post('/api/editor/modelli-personali', json=['invalid']).status_code == 400
    assert client.post('/api/editor/modelli-personali', json={**payload, 'html': '<a href="javascript:alert(1)">Collegamento</a>'}).status_code == 400
    assert client.post('/api/editor/modelli-personali', json={**payload, 'html': '<p>Modificato</p>'}).status_code == 409
    permissions.clear()
    assert client.post('/api/editor/modelli-personali', json=payload).status_code == 403
    assert client.get('/api/editor/modelli-personali').status_code == 403
