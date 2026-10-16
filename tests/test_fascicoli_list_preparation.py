"""Preparazione nativa e richiesta primaria su soli dati sintetici."""
import json

from tests.test_react_shell import _app
from tests.test_fascicoli_pagination import _seed_fascicoli


def test_catalogo_fonti_assente_resta_errore_esplicito_senza_creazione_nella_get(tmp_path):
    from tests.fascicoli_list_test_support import prepare_list_catalog
    app = _app(tmp_path, sql_fascicoli_list=True)
    _seed_fascicoli(app, 1)
    registry = tmp_path / 'intelligence' / 'registro_letture.db'
    assert not registry.exists()
    with app.test_client() as client:
        response = client.get('/api/v1/ui/fascicoli', headers={'X-API-Key': 'react-test-key'})
        assert response.status_code == 503
        payload = response.get_json()
        assert payload['code'] == 'fascicoli_catalog_not_ready'
        assert 'items' not in payload and str(tmp_path) not in json.dumps(payload)
        assert not registry.exists()
        prepare_list_catalog(app)
        response = client.get('/api/v1/ui/fascicoli', headers={'X-API-Key': 'react-test-key'})
        assert response.status_code == 200
        assert response.get_json()['pagination']['total'] == 1


def test_preparazione_backup_persistenza_e_pagina_primaria(tmp_path, monkeypatch):
    from web.services.document_intelligence_runtime import document_ai_tenant_id
    from web.services.fascicoli_list_preparation import prepare_catalog
    from web.services.registro_letture_runtime import registro_corrente
    from web.services.studio_readonly import worker_studio_writer
    from web.services import react_fascicoli_bridge as bridge

    app = _app(tmp_path, sql_fascicoli_list=True)
    _seed_fascicoli(app, 31)
    anchor = app.config['FASCICOLI_DB']
    with app.test_request_context('/__prepare-controlled-catalog'):
        registro_corrente()  # schema della fonte sintetica prima del backup
        tenant = document_ai_tenant_id()
        with worker_studio_writer(anchor) as database:
            result = prepare_catalog(database, tenant=tenant, anchor=anchor,
                destination=tmp_path / 'backup' / 'list', limit=10)
            assert result['phase'] == 'COMPLETED'
            proof = json.loads((tmp_path / 'backup' / 'list' / 'catalog-source-proof.json').read_text())
            assert proof['before'] == proof['after']
            assert database.conn.execute('SELECT COUNT(*) FROM fascicoli').fetchone()[0] == 31
            resumed = prepare_catalog(database, tenant=tenant, anchor=anchor,
                destination=tmp_path / 'backup' / 'list', limit=10)
            assert resumed == dict(phase='COMPLETED', prepared=False)

    def forbidden(*_args, **_kwargs):
        raise AssertionError('La GET non deve ricostruire tutti i fascicoli.')
    monkeypatch.setattr(bridge, 'build_react_fascicoli_payload', forbidden)
    with app.test_client() as client:
        response = client.get('/api/v1/ui/fascicoli?page=2&page_size=25&view=operativa',
            headers={'X-API-Key': 'react-test-key'})
        assert response.status_code == 200, response.get_json()
        payload = response.get_json()
        assert payload['pagination'] == dict(page=2, pageSize=25, total=31, pages=2)
        assert len(payload['items']) == 6
        economic = client.get('/api/v1/ui/fascicoli?page=2&page_size=25&view=economica',
            headers={'X-API-Key': 'react-test-key'})
        assert economic.status_code == 200, economic.get_json()
        assert economic.get_json()['pagination'] == payload['pagination']
        assert [item['id'] for item in economic.get_json()['items']] == [item['id'] for item in payload['items']]
        with app.test_request_context('/__change-controlled-source'):
            with worker_studio_writer(anchor) as database:
                row = database.conn.execute('SELECT id,dati_json FROM fascicoli ORDER BY id LIMIT 1').fetchone()
                source = json.loads(row[1])
                source['titolo'] = 'Titolo aggiornato soltanto sulla fonte'
                database.conn.execute('UPDATE fascicoli SET dati_json=? WHERE id=?',
                    (json.dumps(source), row[0]))
                database.conn.commit()
        pending = client.get('/api/v1/ui/fascicoli?page=1&page_size=25',
            headers={'X-API-Key': 'react-test-key'})
        assert pending.status_code == 503
        assert 'items' not in pending.get_json()
        with app.test_request_context('/__deliver-controlled-source'):
            from web.services.fascicoli_list_events_runtime import resume_owner_events
            with worker_studio_writer(anchor) as database:
                result = resume_owner_events(database, tenant, anchor)
                assert result['delivered'] >= 1 and result['failed'] == 0
        refreshed = client.get('/api/v1/ui/fascicoli?q=Titolo+aggiornato+soltanto',
            headers={'X-API-Key': 'react-test-key'})
        assert refreshed.status_code == 200, refreshed.get_json()
        assert refreshed.get_json()['pagination']['total'] == 1
