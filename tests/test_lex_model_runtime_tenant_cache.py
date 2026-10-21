"""La scelta del modello non può essere riusata da un altro studio."""

import pytest
from flask import Flask, g

from lex.providers import local_ai_service, ollama_runtime


def test_warmup_reports_failure_and_recovers_without_changing_selected_model(monkeypatch):
    app = Flask(__name__)
    selected = {'chat_model': 'iusentra-lex-v3:9b', 'keep_alive': '10m',
                'api_base_url': 'http://127.0.0.1:11434/api', 'base_url': 'http://127.0.0.1:11434'}
    monkeypatch.setattr(ollama_runtime, 'is_managed_cloud_runtime', lambda: False)
    monkeypatch.setattr(ollama_runtime, 'refresh_live_ollama_runtime', lambda: dict(selected))
    attempts = []

    class Client:
        def __init__(self, base):
            assert base == selected['api_base_url']

        def warmup_model(self, model, *, keep_alive):
            attempts.append((model, keep_alive))
            if len(attempts) == 1:
                raise ConnectionError('Servizio temporaneamente non disponibile')
            return {'load_duration': 120, 'prompt_eval_count': 0}

    monkeypatch.setattr(ollama_runtime, 'OllamaHttpClient', Client)
    with app.app_context():
        app.extensions['ollama_runtime_resolution'] = {'obsolete': True}
        failed = ollama_runtime.warm_ollama_chat_runtime(force_refresh=True)
        assert failed['status'] == 'error'
        assert 'temporaneamente' in failed['error']
        assert failed['chat_model'] == selected['chat_model']
        assert 'ollama_runtime_resolution' not in app.extensions
        recovered = ollama_runtime.warm_ollama_chat_runtime()
        assert recovered['status'] == 'ready'
        assert recovered['chat_model'] == selected['chat_model']
        assert recovered['load_duration'] == 120
    assert attempts == [(selected['chat_model'], '10m')] * 2


def test_warmup_without_selected_model_does_not_contact_service(monkeypatch):
    monkeypatch.setattr(ollama_runtime, 'is_managed_cloud_runtime', lambda: False)
    monkeypatch.setattr(ollama_runtime, 'refresh_live_ollama_runtime', lambda: {'chat_model': ''})
    monkeypatch.setattr(ollama_runtime, 'OllamaHttpClient', lambda *_: pytest.fail('Nessun modello da avviare'))
    assert ollama_runtime.warm_ollama_chat_runtime() == {'status': 'skipped', 'reason': 'missing_model'}


def test_runtime_cache_does_not_reuse_model_from_another_tenant(monkeypatch):
    app = Flask(__name__)
    app.config.update(MULTI_TENANT=True, STUDIO_CONFIG='global.json', LOCAL_AI_DB='global.db')
    calls = []
    monkeypatch.setattr(local_ai_service, '_service_key',
                        lambda app: (g.owner, 'policy', g.owner + '.db', 'root', 'models'))

    def compute(default_model):
        calls.append(g.owner)
        return ollama_runtime._chat_runtime_cache_key(default_model), {'chat_model': g.owner + '-model'}

    monkeypatch.setattr(ollama_runtime, '_compute_local_chat_runtime', compute)
    with app.app_context():
        g.owner = 'studio-a'
        first = ollama_runtime.resolved_ollama_runtime()
        g.owner = 'studio-b'
        second = ollama_runtime.resolved_ollama_runtime()
        assert first['chat_model'] == 'studio-a-model'
        assert second['chat_model'] == 'studio-b-model'
        assert calls == ['studio-a', 'studio-b']


def test_same_tenant_keeps_cached_resolution_without_new_reads(monkeypatch):
    app = Flask(__name__)
    app.config.update(MULTI_TENANT=True, STUDIO_CONFIG='global.json', LOCAL_AI_DB='global.db')
    monkeypatch.setattr(local_ai_service, '_service_key', lambda app: ('studio-a', 'policy', 'a.db', 'root', 'models'))
    calls = []

    def compute(default_model):
        calls.append(True)
        return ollama_runtime._chat_runtime_cache_key(default_model), {'chat_model': 'accepted-model'}

    monkeypatch.setattr(ollama_runtime, '_compute_local_chat_runtime', compute)
    with app.app_context():
        assert ollama_runtime.resolved_ollama_runtime() == ollama_runtime.resolved_ollama_runtime()
    assert len(calls) == 1


def test_missing_tenant_context_cannot_reuse_previously_cached_runtime(monkeypatch):
    app = Flask(__name__)
    app.config['MULTI_TENANT'] = True

    def key(app):
        if not getattr(g, 'owner', None):
            raise RuntimeError('Contesto studio non disponibile')
        return (g.owner, 'policy', 'a.db', 'root', 'models')

    monkeypatch.setattr(local_ai_service, '_service_key', key)
    monkeypatch.setattr(ollama_runtime, '_compute_local_chat_runtime',
                        lambda model: (ollama_runtime._chat_runtime_cache_key(model), {'chat_model': 'studio-a-model'}))
    with app.app_context():
        g.owner = 'studio-a'
        assert ollama_runtime.resolved_ollama_runtime()['chat_model'] == 'studio-a-model'
        del g.owner
        with pytest.raises(RuntimeError, match='Contesto studio'):
            ollama_runtime.resolved_ollama_runtime()


def test_single_tenant_key_preserves_existing_configuration_contract():
    app = Flask(__name__)
    app.config.update(STUDIO_CONFIG='studio.json', LOCAL_AI_DB='ai.db')
    with app.app_context():
        assert ollama_runtime._chat_runtime_cache_key('accepted-model') == ('accepted-model', 'studio.json', 'ai.db')
