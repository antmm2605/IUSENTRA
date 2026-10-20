"""Le modifiche anagrafiche non sostituiscono archivi o collegamenti altrui."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from pct.soggetti import GestioneSoggetti, RuoloSoggetto, TipoSoggetto
from pct.soggetti import SoggettoConcurrentUpdate, soggetto_revision
from pct.storage import StudioDB
from pct.storage_postgres import PostgresStudioDB
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def subjects(request, tmp_path):
    if request.param == 'postgresql' and not os.environ.get('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato')
    factory = SQLFactory(request.param)
    backend = None
    try:
        if request.param == 'postgresql':
            from psycopg2.extensions import make_dsn
            backend = PostgresStudioDB(make_dsn(**factory.pg_parameters,
                options=f'-c search_path={factory.schema}'))
        else:
            backend = StudioDB(str(tmp_path / 'controlled.db'))
        def manager():
            return GestioneSoggetti(str(tmp_path / 'old-subjects.json'),
                                    str(tmp_path / 'old-parties.json'), studio_db=backend)
        yield backend, manager
    finally:
        if backend:
            backend.chiudi()
        factory.close()


def test_independent_subject_updates_preserve_both_and_links(subjects):
    db, manager = subjects
    first = manager()
    one = first.crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    two = first.crea(TipoSoggetto.PERSONA_FISICA, nome='Due')
    db.conn.execute("INSERT INTO fascicoli(id) VALUES (?)", ('F1',))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    party = first.aggiungi_parte('F1', one.id, RuoloSoggetto.TESTIMONE)
    stale = manager()
    stale.tutti()
    first.aggiorna(one.id, note='primo')
    stale.aggiorna(two.id, note='secondo')
    fresh = manager()
    assert fresh.get(one.id).note == 'primo'
    assert fresh.get(two.id).note == 'secondo'
    assert fresh.parti_fascicolo('F1')[0][0].id == party.id


def test_competing_subject_update_is_rejected(subjects):
    _, manager = subjects
    first = manager()
    one = first.crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    stale = manager()
    stale.tutti()
    first.aggiorna(one.id, note='confermato')
    with pytest.raises(ValueError, match='altro utente'):
        stale.aggiorna(one.id, note='obsoleto')
    assert manager().get(one.id).note == 'confermato'


def test_parties_of_other_cases_survive_stale_manager(subjects):
    db, manager = subjects
    first = manager()
    one = first.crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    for key in ('F1', 'F2'):
        db.conn.execute('INSERT INTO fascicoli(id) VALUES (?)', (key,))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    stale = manager()
    stale.parti_fascicolo('F1')
    first.aggiungi_parte('F1', one.id, RuoloSoggetto.TESTIMONE)
    stale.aggiungi_parte('F2', one.id, RuoloSoggetto.CONTROPARTE)
    fresh = manager()
    assert len(fresh.parti_fascicolo('F1')) == 1
    assert len(fresh.parti_fascicolo('F2')) == 1


def test_unknown_fields_survive_and_corruption_is_explicit(subjects):
    db, manager = subjects
    original = manager().crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    payload = json.loads(db.conn.execute('SELECT dati_json FROM soggetti WHERE id=?',
                                        (original.id,)).fetchone()['dati_json'])
    payload['provenienza_storica'] = {'decisione_manuale': True}
    payload['recapiti']['preferenza_storica'] = 'telefono'
    db.conn.execute('UPDATE soggetti SET dati_json=? WHERE id=?',
                    (json.dumps(payload), original.id))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    manager().aggiorna(original.id, note='aggiornato')
    saved = json.loads(db.conn.execute('SELECT dati_json FROM soggetti WHERE id=?',
                                     (original.id,)).fetchone()['dati_json'])
    assert saved['provenienza_storica'] == payload['provenienza_storica']
    assert saved['recapiti']['preferenza_storica'] == 'telefono'
    db.conn.execute('UPDATE soggetti SET dati_json=? WHERE id=?', ('{broken', original.id))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    same = manager()
    for _ in range(2):
        with pytest.raises(json.JSONDecodeError):
            same.tutti()


def test_browser_revision_rejects_old_form_even_with_fresh_manager(subjects):
    db, manager = subjects
    person = manager().crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    revision = soggetto_revision(person)
    saved = manager().aggiorna(person.id, expected_revision=revision, note='prima finestra')
    with pytest.raises(SoggettoConcurrentUpdate):
        manager().aggiorna(person.id, expected_revision=revision, note='bozza precedente')
    assert manager().get(person.id).note == 'prima finestra'
    current = manager().aggiorna(person.id, expected_revision=soggetto_revision(saved), note='confrontata')
    assert manager().get(person.id).note == 'confrontata'
    assert soggetto_revision(current) != revision


def test_subject_form_preserves_hidden_contact_and_client_link_and_rejects_stale_save(subjects):
    from flask import Flask
    from pct.clienti import Recapiti
    from web.bootstrap.soggetti_routes import register_soggetti_routes

    db, manager = subjects
    db.conn.execute('INSERT INTO clienti(id) VALUES (?)', ('cliente-collegato',))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    person = manager().crea(TipoSoggetto.PERSONA_FISICA, nome='Uno', cognome='Collaudo',
        id_cliente='cliente-collegato', recapiti=Recapiti(fax='fax conservato', sito_web='https://example.invalid'))
    revision = soggetto_revision(person)
    app = Flask(__name__)
    app.secret_key = 'chiave-solo-test-sintetico'
    app.config['TESTING'] = True
    events = []
    register_soggetti_routes(app, get_soggetti=manager,
        get_clienti=lambda: SimpleNamespace(tutti=lambda: []), get_fascicoli=lambda: None,
        audit=lambda *args, **kwargs: events.append(args))
    form = {'nome': 'Uno', 'cognome': 'Collaudo', 'note': 'confermata', 'expected_revision': revision}
    client = app.test_client()
    endpoint = f'/soggetti/{person.id}/modifica'
    unversioned = client.post(endpoint, data={'nome': 'bozza precedente'}, headers={'Accept': 'application/json'})
    assert unversioned.status_code == 409
    assert unversioned.json['code'] == 'soggetto_revision_required'
    assert manager().get(person.id).nome == 'Uno'
    assert not events
    response = client.post(endpoint, data=form, headers={'Accept': 'application/json'})
    assert response.status_code == 200
    current = manager().get(person.id)
    assert (current.id_cliente, current.recapiti.fax, current.recapiti.sito_web) == (
        person.id_cliente, 'fax conservato', 'https://example.invalid')
    form['note'] = 'bozza da non applicare'
    rejected = client.post(endpoint, data=form, headers={'Accept': 'application/json'})
    assert rejected.status_code == 409
    assert rejected.json['code'] == 'soggetto_concurrent_update'
    assert manager().get(person.id).note == 'confermata'
    assert len(events) == 1


def test_concurrent_same_party_returns_the_confirmed_link_without_replacing_notes(subjects):
    db, manager = subjects
    person = manager().crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    db.conn.execute('INSERT INTO fascicoli(id) VALUES (?)', ('F1',))
    (getattr(db, 'raw_conn', None) or db.conn).commit()

    def add(note):
        try:
            return manager().aggiungi_parte('F1', person.id, RuoloSoggetto.TESTIMONE, note=note)
        finally:
            db.chiudi()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add, ['prima', 'seconda']))
    assert results[0].id == results[1].id
    assert results[0].note == results[1].note
    assert len(manager().parti_fascicolo('F1')) == 1
    repeated = manager().aggiungi_parte('F1', person.id, RuoloSoggetto.TESTIMONE, note='da non sovrascrivere')
    assert (repeated.id, repeated.note) == (results[0].id, results[0].note)


def test_deleting_a_linked_subject_preserves_subject_and_party_then_allows_unlinked_delete(subjects):
    db, manager = subjects
    first = manager()
    person = first.crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    db.conn.execute('INSERT INTO fascicoli(id) VALUES (?)', ('F1',))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    party = first.aggiungi_parte('F1', person.id, RuoloSoggetto.TESTIMONE)
    with pytest.raises(ValueError, match='rimuovi prima'):
        first.elimina(person.id)
    assert first.get(person.id) is not None
    assert manager().parti_fascicolo('F1')[0][0].id == party.id
    first.rimuovi_parte('F1', party.id)
    first.elimina(person.id)
    assert manager().get(person.id) is None
    assert manager().parti_fascicolo('F1') == []


def test_party_cannot_reference_a_missing_matter_or_subject(subjects):
    db, manager = subjects
    person = manager().crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    with pytest.raises(KeyError, match='Fascicolo non trovato'):
        manager().aggiungi_parte('absent', person.id, RuoloSoggetto.TESTIMONE)
    db.conn.execute('INSERT INTO fascicoli(id) VALUES (?)', ('F1',))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    with pytest.raises(KeyError, match='Soggetto non trovato'):
        manager().aggiungi_parte('F1', 'absent', RuoloSoggetto.TESTIMONE)
    assert manager().parti_fascicolo('F1') == []


def test_party_identifier_collision_does_not_update_an_existing_role(subjects, monkeypatch):
    import sqlite3
    import psycopg2
    import uuid

    db, manager = subjects
    person = manager().crea(TipoSoggetto.PERSONA_FISICA, nome='Uno')
    db.conn.execute('INSERT INTO fascicoli(id) VALUES (?)', ('F1',))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    first = manager().aggiungi_parte('F1', person.id, RuoloSoggetto.TESTIMONE, note='da conservare')
    monkeypatch.setattr('pct.soggetti.uuid.uuid4', lambda: uuid.UUID(first.id + '0' * 24))
    error_type = psycopg2.IntegrityError if getattr(db, 'backend_kind', '') == 'postgresql' else sqlite3.IntegrityError
    with pytest.raises(error_type):
        manager().aggiungi_parte('F1', person.id, RuoloSoggetto.CONTROPARTE)
    links = manager().parti_fascicolo('F1')
    assert len(links) == 1 and links[0][0].to_dict() == first.to_dict()


def test_correction_unlinks_only_selected_revision_and_preserves_subjects(subjects):
    from flask import Flask
    from web.bootstrap.soggetti_routes import register_soggetti_routes
    from web.services.deposito_participant_correction import participant_correction_sources

    db, manager = subjects
    for fid in ('F1', 'F2'):
        db.conn.execute('INSERT INTO fascicoli(id) VALUES (?)', (fid,))
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    entity = manager().crea(TipoSoggetto.PUBBLICA_AMMINISTRAZIONE, ragione_sociale='Ente collaudo', codice_fiscale='80078750587')
    first = manager().aggiungi_parte('F1', entity.id, RuoloSoggetto.CONTROPARTE)
    other = manager().aggiungi_parte('F1', entity.id, RuoloSoggetto.INTERVENIENTE)
    manager().aggiungi_parte('F2', entity.id, RuoloSoggetto.CONTROPARTE)
    sources = participant_correction_sources(manager().parti_fascicolo('F1'), 'F1')
    assert len(sources) == 2  # stesso nome e CF: nessuna riga nascosta nella correzione
    row = next(item for item in sources if item['linkId'] == first.id)
    app = Flask(__name__)
    app.secret_key = 'solo-collaudo'
    events = []
    register_soggetti_routes(app, get_soggetti=manager,
        get_clienti=lambda: SimpleNamespace(tutti=lambda: []),
        get_fascicoli=lambda: SimpleNamespace(get=lambda fid: SimpleNamespace(id=fid) if fid in {'F1','F2'} else None),
        audit=lambda *args, **kwargs: events.append(args))
    client = app.test_client()
    headers = {'Accept': 'application/json'}
    assert client.post(row['unlinkAction'], data={}, headers=headers).status_code == 409
    assert client.post(row['unlinkAction'].replace('/F1/', '/F2/'),
        data={'expected_revision': row['revision']}, headers=headers).status_code == 409
    manager().aggiorna(entity.id, note='revisione concorrente')
    assert client.post(row['unlinkAction'], data={'expected_revision': row['revision']}, headers=headers).status_code == 409
    fresh = next(item for item in participant_correction_sources(manager().parti_fascicolo('F1'), 'F1') if item['linkId'] == first.id)
    response = client.post(fresh['unlinkAction'], data={'expected_revision': fresh['revision']}, headers=headers)
    assert response.status_code == 200 and response.json['ok'] is True
    assert [parte.id for parte, _ in manager().parti_fascicolo('F1')] == [other.id]
    assert len(manager().parti_fascicolo('F2')) == 1
    assert manager().get(entity.id).note == 'revisione concorrente'
    assert len(events) == 1
