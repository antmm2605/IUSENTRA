"""Il servizio locale rispetta i percorsi della richiesta e il confine cloud."""
import pytest
from flask import Flask, g
from lex.providers import local_ai_service as provider


@pytest.fixture
def local_provider(tmp_path, monkeypatch):
    app = Flask(__name__)
    app.config.update(MULTI_TENANT=False, LOCAL_AI_DB=str(tmp_path / 'configured.db'),
                      LOCAL_AI_MODELS_DIR=str(tmp_path / 'configured-models'),
                      STUDIO_CONFIG=str(tmp_path / 'studio.json'))
    created = []
    class ControlledService:
        def __init__(self, **configuration):
            self.configuration = configuration
            created.append(self)
    monkeypatch.setattr(provider, 'LocalAIService', ControlledService)
    monkeypatch.setattr(provider, 'is_managed_cloud_runtime', lambda: False)
    return app, created


def test_local_requests_resolve_their_own_paths_and_do_not_share_another_service(local_provider, tmp_path):
    app, created = local_provider
    first_db = str(tmp_path / 'request-a.db')
    first_models = str(tmp_path / 'request-a-models')
    second_db = str(tmp_path / 'request-b.db')
    with app.test_request_context('/'):
        g.data_paths = {'LOCAL_AI_DB': first_db, 'LOCAL_AI_MODELS_DIR': first_models}
        first = provider.get_local_ai_service()
        assert first.configuration['db_path'] == first_db
        assert first.configuration['models_path'] == first_models
        assert provider.get_local_ai_service() is first
    with app.test_request_context('/'):
        g.data_paths = {'LOCAL_AI_DB': second_db}
        second = provider.get_local_ai_service()
        assert second is not first
        assert second.configuration['db_path'] == second_db
        assert second.configuration['models_path'] == app.config['LOCAL_AI_MODELS_DIR']
    with app.app_context():
        g.data_paths = {'LOCAL_AI_DB': first_db}
        outside_request = provider.get_local_ai_service()
        assert outside_request.configuration['db_path'] == app.config['LOCAL_AI_DB']
        assert outside_request is not first and outside_request is not second
    assert len(created) == 3


def test_managed_runtime_does_not_reopen_persistent_request_paths(local_provider, monkeypatch):
    app, created = local_provider
    monkeypatch.setattr(provider, 'is_managed_cloud_runtime', lambda: True)
    with app.test_request_context('/'):
        g.data_paths = {'LOCAL_AI_DB': '/persistent/studio.db',
                        'LOCAL_AI_MODELS_DIR': '/persistent/models'}
        service = provider.get_local_ai_service()
        assert service.configuration['db_path'] == app.config['LOCAL_AI_DB']
        assert service.configuration['models_path'] == app.config['LOCAL_AI_MODELS_DIR']
    assert len(created) == 1


def test_missing_tenant_context_does_not_construct_a_local_service(local_provider):
    app, created = local_provider
    app.config['MULTI_TENANT'] = True
    with app.test_request_context('/'):
        g.data_paths = {}
        with pytest.raises(RuntimeError, match='Contesto studio non disponibile'):
            provider.get_local_ai_service()
    assert created == []
