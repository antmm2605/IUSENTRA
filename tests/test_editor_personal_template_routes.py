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
    assert client.get('/api/editor/modelli-personali/' + identifier).status_code == 403
    assert client.get('/api/editor/F2/modelli-personali/' + identifier + '/compila').status_code == 403


def test_shared_model_available_to_two_studios_and_private_models_isolated(tmp_path):
    shared = GestioneTemplateRepository(str(tmp_path / 'shared.db'))
    studios = [GestioneTemplateRepository(str(tmp_path / f'studio-{n}.db')) for n in (1, 2)]
    identifier = str(uuid4())
    body = '<p><strong><span data-iu-linked-field="cliente.nome">[Nome]</span></strong> <span data-iu-linked-field="studio.citta">[Comune studio]</span></p>'
    shared.create_shared_editor_template({'id': identifier, 'titolo': 'Condiviso', 'corpo': body, 'collezione': 'Editor condiviso', 'builtin': True})
    private_id = str(uuid4())
    studios[0].create_editor_template({'id': private_id, 'titolo': 'Privato', 'corpo': '<p>Privato</p>', 'collezione': 'Editor personale'})
    app = Flask(__name__)
    selected = [0]

    @app.before_request
    def context():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda name: True)

    def resolve(identifier):
        if identifier != f'F{selected[0]}':
            return jsonify(ok=False), 404
        return jsonify(fields=[{'id': 'cliente.nome', 'value': f'Cliente {selected[0]}', 'available': True}, {'id': 'studio.citta', 'value': f'Citta {selected[0]}', 'available': True}], matterId=identifier, clientId=f'C{selected[0]}')

    register_editor_personal_template_routes(app, audit=lambda *a, **kw: None, get_repository=lambda: studios[selected[0]], get_shared_repository=lambda: shared, resolve_context=resolve)
    client = app.test_client()
    for studio in (0, 1):
        selected[0] = studio
        listing = client.get('/api/editor/modelli-personali').json['modelli']
        assert any(m['id'] == 'shared:' + identifier and m['ambito'] == 'condiviso' for m in listing)
        assert any(m['id'] == private_id for m in listing) == (studio == 0)
        filled = client.get(f'/api/editor/F{studio}/modelli-personali/shared:{identifier}/compila')
        assert filled.status_code == 200
        assert f'Cliente {studio}' in filled.json['html'] and f'Citta {studio}' in filled.json['html']
        assert client.get('/api/editor/modelli-personali/' + identifier).status_code == 404
        assert client.get('/api/editor/modelli-personali/shared:' + private_id).status_code == 404
    assert client.get('/api/editor/modelli-personali/' + private_id).status_code == 404
    assert len(shared.list_templates()) == 1


def test_shared_catalog_reads_do_not_create_missing_database(tmp_path):
    from web.services.editor_template_fonts import shared_template_repository
    app = Flask(__name__)
    app.config['PCT_DATA_ROOT'] = str(tmp_path)
    with app.app_context():
        assert shared_template_repository() is None
    assert not (tmp_path / 'editor_shared_models').exists()


def test_shared_publication_removes_previous_bindings_and_audits_atomically(tmp_path):
    import hashlib
    import json
    import pytest
    from pct.editor_shared_models import prepare_shared_model, publish_shared_model
    repo = GestioneTemplateRepository(str(tmp_path / 'shared.db'))
    payload = {'id': str(uuid4()), 'titolo': 'Condiviso', 'corpo': '<p data-iu-font-template="old"><span data-iu-linked-field="cliente.nome" data-iu-linked-client="old-client">Primo cliente</span></p>'}
    item = prepare_shared_model(payload)
    assert 'Primo cliente' not in item['corpo'] and 'old-client' not in item['corpo'] and 'old' not in item['corpo']
    fingerprint = hashlib.sha256(json.dumps({'payload': item, 'font_source': ''}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt = publish_shared_model(repo, payload, font_source='', reviewed_sha256=fingerprint, publisher='release')
    assert publish_shared_model(repo, payload, font_source='', reviewed_sha256=fingerprint, publisher='release') == receipt
    with pytest.raises(ValueError, match='Ricevuta'):
        publish_shared_model(repo, payload, font_source='', reviewed_sha256=fingerprint, publisher='diverso')
    with repo._connection() as conn:
        stored = conn.execute('SELECT meta_value FROM template_repository_meta WHERE meta_key=?', ('editor_shared_publication:' + payload['id'],)).fetchone()
        assert json.loads(stored['meta_value']) == receipt
    with pytest.raises(ValueError, match='identificativi'):
        prepare_shared_model({**payload, 'corpo': '<p>persona@example.it</p>'})
    with pytest.raises(ValueError, match='Impronta'):
        publish_shared_model(repo, payload, font_source='', reviewed_sha256='wrong', publisher='release')


def test_editor_studio_context_never_uses_global_professional_defaults(tmp_path, monkeypatch):
    from flask import Flask
    from types import SimpleNamespace
    from pct.config_studio import ConfigStudio
    from web.blueprints import template_atti
    from web.services.editor_studio_context import studio_context_for_editor
    from pct.editor_linked_fields import linked_fields_catalog
    config = ConfigStudio()
    config.studio.nome = 'Studio tecnico separato'
    app = Flask(__name__)
    app.config.update(STUDIO_AVVOCATO='Avvocato altro studio', SMTP_FROM='altro@example.it', PCT_STUDIO_PEC='pec-altrui@example.it')
    monkeypatch.setattr(template_atti, '_get_config_studio_manager', lambda: SimpleNamespace(config=config))
    monkeypatch.setattr(template_atti, '_cfg_path', lambda *args: str(tmp_path / 'stamp.db'))
    with app.app_context():
        fields = {f['id']: f for f in linked_fields_catalog(**studio_context_for_editor())}
    assert fields['studio_timbro.studio_nome']['value'] == 'Studio tecnico separato'
    assert fields['studio_timbro.pec']['available'] is False
    assert fields['studio_timbro.nome_professionista']['available'] is False
    config.studio.avvocato = 'Avvocato dello studio tecnico'
    config.pec.indirizzo = 'tecnico@pec.example.it'
    with app.app_context():
        fields = {f['id']: f for f in linked_fields_catalog(**studio_context_for_editor())}
    assert fields['studio_timbro.pec']['value'] == 'tecnico@pec.example.it'
    assert fields['studio_timbro.nome_professionista']['value'] == 'dello studio tecnico'


def test_editor_stamp_endpoint_uses_current_tenant_settings_without_g_config(tmp_path, monkeypatch):
    from flask import g
    from types import SimpleNamespace
    from pct.config_studio import ConfigStudio
    from web.blueprints import template_atti
    from web.bootstrap.editor_finalize_routes import register_editor_finalize_routes
    from web.services.editor_studio_context import studio_context_for_editor

    config = ConfigStudio()
    config.studio.nome = 'Studio primo'
    config.studio.avvocato = 'Avv. Professionista primo'
    config.studio.cf = 'CF-PRIMO'
    config.pec.indirizzo = 'primo@pec.example.it'
    selected = {'slug': 'primo', 'config': config}
    app = Flask(__name__)
    app.config.update(STUDIO_AVVOCATO='Professionista globale errato', SMTP_FROM='globale@example.it')
    monkeypatch.setattr(template_atti, '_get_config_studio_manager', lambda: SimpleNamespace(config=selected['config']))
    monkeypatch.setattr(template_atti, '_cfg_path', lambda *args: str(tmp_path / (selected['slug'] + '.db')))
    @app.before_request
    def context():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda p: True)
        assert not hasattr(g, 'config_studio')
    register_editor_finalize_routes(app, get_fascicoli=lambda: None, audit=lambda *args: None,
                                   encrypt_doc=lambda value: value,
                                   get_timbro=lambda: studio_context_for_editor()['studio_timbro'])
    client = app.test_client()
    first = client.get('/api/editor/timbro')
    assert first.status_code == 200
    assert 'Professionista primo' in str(first.json['righe'])
    second = ConfigStudio()
    second.studio.nome = 'Studio secondo'
    second.studio.avvocato = 'Avv. Professionista secondo'
    selected.update(slug='secondo', config=second)
    reply = client.get('/api/editor/timbro')
    assert reply.status_code == 200
    assert 'Professionista secondo' in str(reply.json['righe'])
    assert 'primo' not in str(reply.json['righe'])
    assert 'globale' not in str(reply.json['righe'])
