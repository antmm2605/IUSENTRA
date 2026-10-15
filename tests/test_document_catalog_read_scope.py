"""Una consultazione del catalogo non deve rileggere gli altri fascicoli."""
import json
from types import SimpleNamespace

import pytest
from flask import Flask

from pct.fascicoli import Fascicolo, GestioneFascicoli, TipoFascicolo
from tests.test_fascicoli_rinomina_sql_mirata import rename_case  # noqa: F401
from web import helpers


def test_catalog_reuses_one_targeted_sql_repository(rename_case, monkeypatch, tmp_path):
    _, backend, _, _ = rename_case
    app = Flask(__name__)
    endpoint = 'api_v1_documenti_ai.catalogazione_documentale_fascicolo'
    app.add_url_rule('/catalog/F1', endpoint=endpoint, view_func=lambda: '')
    paths = {key: str(tmp_path / key) for key in
             ('FASCICOLI_DB', 'FASCICOLI_DOCS', 'FASCICOLI_ARCH')}
    monkeypatch.setattr(helpers, '_cfg', paths.__getitem__)
    monkeypatch.setattr(helpers, '_studio_db', lambda _: backend)

    def forbidden(*args, **kwargs):
        raise AssertionError('Il catalogo non deve caricare tutti i fascicoli')

    monkeypatch.setattr(GestioneFascicoli, '_carica', forbidden)
    with app.test_request_context('/catalog/F1'):
        managers = [helpers.get_fascicoli() for _ in range(4)]
        assert all(manager is managers[0] for manager in managers)
        assert managers[0].get('F1').id == 'F1'
        assert not managers[0]._archivio_completo

    # Una richiesta nuova riceve una nuova istantanea, non un oggetto globale.
    with app.test_request_context('/catalog/F1'):
        assert helpers.get_fascicoli() is not managers[0]

    # Anche una riconfigurazione del backend nella stessa richiesta invalida
    # l'oggetto precedente, pur conservando gli stessi percorsi logici.
    class ReboundBackend:
        def __getattr__(self, name):
            return getattr(backend, name)

    with app.test_request_context('/catalog/F1'):
        previous = helpers.get_fascicoli()
        rebound = ReboundBackend()
        monkeypatch.setattr(helpers, '_studio_db', lambda _: rebound)
        current = helpers.get_fascicoli()
        assert current is not previous
        assert current.get('F1').id == 'F1'


@pytest.mark.parametrize('method,endpoint', [
    ('POST', 'api_v1_documenti_ai.catalogazione_documentale_fascicolo'),
    ('POST', 'fascicolo_prepara_deposito'),
    ('GET', 'fascicolo_prepara_deposito'),
])
def test_other_commands_keep_their_existing_repository_scope(monkeypatch, tmp_path, method, endpoint):
    app = Flask(__name__)
    app.add_url_rule('/command', endpoint=endpoint, methods=[method], view_func=lambda: '')
    monkeypatch.setattr(helpers, '_cfg', lambda key: str(tmp_path / key))
    monkeypatch.setattr(helpers, '_studio_db', lambda _: object())
    created = []

    def factory(**kwargs):
        manager = SimpleNamespace(**kwargs)
        created.append(manager)
        return manager

    monkeypatch.setattr(helpers, 'GestioneFascicoli', factory)
    with app.test_request_context('/command', method=method):
        assert helpers.get_fascicoli() is not helpers.get_fascicoli()
    assert all(manager.carica_tutto for manager in created)


def test_catalog_keeps_the_explicit_historical_json_backend(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.add_url_rule('/catalog/FJSON',
                     endpoint='api_v1_documenti_ai.catalogazione_documentale_fascicolo',
                     view_func=lambda: '')
    source = tmp_path / 'fascicoli.json'
    record = Fascicolo(id='FJSON', numero='2026/9', titolo='Archivio storico controllato',
                       tipo=TipoFascicolo.CIVILE)
    source.write_text(json.dumps({record.id: record.to_dict()}), encoding='utf-8')
    paths = {'FASCICOLI_DB': str(source), 'FASCICOLI_DOCS': str(tmp_path / 'docs'),
             'FASCICOLI_ARCH': str(tmp_path / 'archive')}
    monkeypatch.setattr(helpers, '_cfg', paths.__getitem__)
    monkeypatch.setattr(helpers, '_studio_db', lambda _: None)
    with app.test_request_context('/catalog/FJSON'):
        manager = helpers.get_fascicoli()
        assert manager.get('FJSON').titolo == record.titolo
        assert manager is helpers.get_fascicoli()
