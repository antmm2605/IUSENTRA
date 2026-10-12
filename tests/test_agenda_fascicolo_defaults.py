import pytest

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.clienti import GestioneClienti, TipoCliente
from pct.storage import StudioDB
from tests.test_operational_surfaces import _cfg_web, _seed_runtime, _write_studio_config
from web.app import create_app


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv('PCT_STORAGE_MODE', 'SQLITE')
    config = _cfg_web(tmp_path)
    config['STORAGE_MODE_DEFAULT'] = 'SQLITE'
    _write_studio_config(tmp_path / 'config' / 'studio.json')
    _seed_runtime(config)
    database = StudioDB.get(config['STUDIO_DB'])
    customer = GestioneClienti(db_path=config['CLIENTI_DB'], studio_db=database).nuovo(
        TipoCliente.PERSONA_FISICA, nome='Anna', cognome='Verdi')
    matter = GestioneFascicoli(db_path=config['FASCICOLI_DB'], studio_db=database).nuovo(
        titolo='Collegamento Agenda controllato', tipo=TipoFascicolo.CIVILE,
        id_cliente=customer.id, nome_cliente=customer.nome_completo,
        numero_rg='1234', anno_rg=2026, tribunale='Tribunale di Milano')
    identifier = matter.id
    app = create_app(config)
    with app.test_client() as client:
        client.post('/login', data={'username': 'admin-operativo', 'password': 'Admin1234!'})
        yield client, identifier


def test_new_appointment_reuses_the_selected_matter_context(context):
    client, identifier = context
    response = client.get(f'/api/v1/ui/agenda/nuovo/defaults?id_fascicolo={identifier}')
    assert response.status_code == 200
    assert response.json['id_fascicolo'] == identifier
    assert response.json['cliente'] == 'Verdi Anna'
    assert response.json['id_cliente']
    assert response.json['procedimento'] == 'RG 1234/2026'
    assert response.json['tribunale'] == 'Tribunale di Milano'


def test_unknown_matter_is_not_silently_attached(context):
    client, _ = context
    response = client.get('/api/v1/ui/agenda/nuovo/defaults?id_fascicolo=missing-other-studio')
    assert response.status_code == 404
    assert response.json['ok'] is False
    assert 'id_cliente' not in response.json


def test_matter_context_requires_read_permission(context, monkeypatch):
    from web.blueprints import api_v1_react as routes

    client, identifier = context
    monkeypatch.setattr(routes, '_session_user_can', lambda permission: False)
    response = client.get(f'/api/v1/ui/agenda/nuovo/defaults?id_fascicolo={identifier}')
    assert response.status_code == 403
    assert 'cliente' not in response.json
