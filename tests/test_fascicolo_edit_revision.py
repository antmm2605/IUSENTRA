import json

import pytest
from flask import Flask, jsonify

from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli
from pct.fascicolo_edit_revision import edit_revision
from pct.soggetti import GestioneSoggetti
from tests.test_offline_case_capture import case_state as sql_case_state  # noqa: F401 - fixture SQL condivisa
from web.bootstrap.fascicoli_management_routes import register_fascicoli_management_routes


@pytest.fixture
def form_api(request, tmp_path):
    db, case, _ = request.getfixturevalue('sql_case_state')
    calls = []
    app = Flask(__name__)
    app.secret_key = 'controlled-session-only'
    app.add_url_rule('/fascicoli', endpoint='lista_fascicoli', view_func=lambda: 'controlled')
    app.add_url_rule('/fascicoli/<id_fasc>', endpoint='dettaglio_fascicolo',
                     view_func=lambda id_fasc: jsonify(id=id_fasc))

    def cases():
        return GestioneFascicoli(str(tmp_path / 'fascicoli.json'), studio_db=db)

    def subjects():
        calls.append('subjects')
        return GestioneSoggetti(str(tmp_path / 'soggetti.json'), str(tmp_path / 'parti.json'), studio_db=db)

    register_fascicoli_management_routes(
        app, get_fascicoli=cases,
        get_clienti=lambda: GestioneClienti(str(tmp_path / 'clienti.json'), studio_db=db),
        get_soggetti=subjects, get_preventivi=lambda: None, get_fatturazione=lambda: None,
        get_scadenziario=lambda: None, get_agenda=lambda: None, get_config_studio=lambda: None,
        get_telematico=lambda: None, cliente_accessibile=lambda *a, **kw: True,
        audit=lambda *a, **kw: calls.append('audit'), sync_pubblica=lambda *a, **kw: None,
        build_responsabile_conformita_fascicolo=lambda *a, **kw: {},
        fascicolo_form_correction_context=lambda: {})
    yield app.test_client(), cases, db, case, calls


def post(client, case, revision=None, **fields):
    payload = {'titolo': case.titolo, 'tipo': case.tipo.value, **fields}
    if revision is not None:
        payload['base_revision'] = revision
    return client.post(f'/fascicoli/{case.id}/modifica', data=payload,
                       headers={'Accept': 'application/json'})


def test_edit_revision_ignores_background_work_and_generated_defaults():
    source = {'id': 'case-test', 'tipo': 'ALTRO', 'titolo': 'Prova'}
    first = edit_revision(source, row={'data_apertura': '2024-01-01'})
    assert edit_revision({**source, 'documenti': [{'id': 'new-doc'}], 'modificato_il': 'later',
                          'letture': {'done': True}, 'creato_il': 'generated-later'},
                         row={'data_apertura': '2024-01-01'}) == first
    assert edit_revision({**source, 'note': 'Modifica di un altro avvocato'},
                         row={'data_apertura': '2024-01-01'}) != first
    assert edit_revision({**source, 'id': 'another-case'}, row={'data_apertura': '2024-01-01'}) != first


def test_controlled_detail_route_never_interprets_identifier_as_html(form_api):
    client, _, _, _, _ = form_api
    identifier = '<img src=x onerror=alert(1)>'
    result = client.get('/fascicoli/' + identifier)
    assert result.status_code == 200 and result.mimetype == 'application/json'
    assert result.json == {'id': identifier}


def test_sql_form_without_known_revision_never_writes(form_api):
    client, cases, db, case, calls = form_api
    result = post(client, case, note='Non deve essere salvata')
    assert result.status_code == 409 and result.json['ok'] is False
    assert cases().get(case.id).note == case.note
    assert calls == []
    assert db.conn.execute('SELECT count(*) FROM fascicoli').fetchone()[0] == 1


def test_stale_form_rejected_then_current_form_saves_without_lost_change(form_api):
    client, cases, _, case, calls = form_api
    revision = cases().get(case.id).revisione_modifica
    cases().aggiorna(case.id, note='Nota già confermata')
    failed = post(client, case, revision, titolo='Titolo dalla scheda vecchia')
    assert failed.status_code == 409 and failed.json['ok'] is False
    assert 'restano nel modulo' in failed.json['message']
    assert calls == []
    current = cases().get(case.id)
    assert current.note == 'Nota già confermata' and current.titolo == case.titolo
    saved = post(client, current, current.revisione_modifica,
                 titolo='Titolo dalla scheda aggiornata', note=current.note)
    assert saved.status_code == 200 and saved.json['ok'] is True
    final = cases().get(case.id)
    assert final.titolo == 'Titolo dalla scheda aggiornata' and final.note == current.note


def test_background_metadata_does_not_block_form_or_get_overwritten(form_api):
    client, cases, db, case, _ = form_api
    revision = cases().get(case.id).revisione_modifica
    row = db.conn.execute('SELECT dati_json FROM fascicoli WHERE id=?', (case.id,)).fetchone()
    metadata = {**json.loads(row[0]), 'controlled_background_projection': {'revision': 7}}
    db.conn.execute('UPDATE fascicoli SET dati_json=?,modificato_il=? WHERE id=?',
                    (json.dumps(metadata), 'controlled-later', case.id))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    result = post(client, case, revision, note='Nota corrente')
    assert result.status_code == 200 and result.json['ok'] is True
    stored = json.loads(db.conn.execute('SELECT dati_json FROM fascicoli WHERE id=?', (case.id,)).fetchone()[0])
    assert stored['controlled_background_projection'] == {'revision': 7}
    assert cases().get(case.id).note == 'Nota corrente'


def test_classic_conflict_renders_posted_draft_without_mutating_repository(form_api, monkeypatch):
    client, cases, _, case, calls = form_api
    revision = cases().get(case.id).revisione_modifica
    cases().aggiorna(case.id, note='Nota confermata altrove')
    rendered = {}

    def capture_template(name, **context):
        rendered.update(context)
        return 'controlled template rendering boundary'

    monkeypatch.setattr('web.bootstrap.fascicoli_management_routes.render_template', capture_template)
    response = client.post(f'/fascicoli/{case.id}/modifica', data={
        'base_revision': revision, 'tipo': case.tipo.value, 'titolo': 'Bozza dell’avvocato',
        'note': 'Testo ancora da confrontare',
    })
    assert response.status_code == 409 and rendered['edit_conflict'] is True
    assert rendered['fascicolo'].titolo == 'Bozza dell’avvocato'
    assert rendered['fascicolo'].note == 'Testo ancora da confrontare'
    assert rendered['fascicolo'].revisione_modifica == revision
    assert cases().get(case.id).note == 'Nota confermata altrove'
    assert cases().get(case.id).titolo == case.titolo
    assert calls == []
