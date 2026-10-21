import json
import os

import pytest

from pct.fascicoli import Fascicolo, GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.fascicoli_sql_writer import FascicoloConcurrentUpdate, encode_model, save_changes
from pct.storage import StudioDB


@pytest.fixture
def case_state(tmp_path):
    factory = None
    if os.environ.get('OFFLINE_RECEIVE_TEST_POSTGRES') == '1':
        from psycopg2.extensions import make_dsn
        from pct.storage_postgres import PostgresStudioDB
        from tests.test_condivisioni_sql_repository import SQLFactory
        factory = SQLFactory('postgresql')
        db = PostgresStudioDB(make_dsn(**factory.pg_parameters,
                                      options=f'-c search_path={factory.schema}'))
    else:
        db = StudioDB(str(tmp_path / 'studio.db'))
    manager = GestioneFascicoli(str(tmp_path / 'fascicoli.json'), studio_db=db)
    case = manager.nuovo('Collaudo SQL offline', TipoFascicolo.ALTRO)
    row = dict(db.conn.execute('SELECT * FROM fascicoli WHERE id=?', (case.id,)).fetchone())
    yield db, case, row
    db.chiudi()
    if factory:
        factory.close()


def transaction(db):
    return getattr(db, 'raw_conn', None) or db.conn


def clone(case):
    return Fascicolo.from_dict(case.to_dict())


def test_native_writer_rejects_stale_case_without_losing_confirmed_change(case_state):
    db, case, row = case_state
    first, second = clone(case), clone(case)
    original = {case.id: encode_model(case)}
    first.note = 'Prima modifica confermata'
    save_changes(db, original_rows={case.id: row}, original_models=original, current={case.id: first})
    second.titolo = 'Modifica da snapshot vecchio'
    with pytest.raises(FascicoloConcurrentUpdate):
        save_changes(db, original_rows={case.id: row}, original_models=original, current={case.id: second})
    stored = db.conn.execute('SELECT note,titolo FROM fascicoli WHERE id=?', (case.id,)).fetchone()
    assert stored[0] == first.note and stored[1] == case.titolo


def test_normal_manager_rejects_stale_save_then_reload_allows_intended_edit(case_state, tmp_path):
    db, case, _ = case_state
    args = dict(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    first, second = GestioneFascicoli(**args), GestioneFascicoli(**args)
    first.aggiorna(case.id, note='Nota confermata dal primo processo')
    with pytest.raises(FascicoloConcurrentUpdate):
        second.aggiorna(case.id, titolo='Titolo dal secondo processo')
    assert second.get(case.id).titolo == case.titolo
    reloaded = GestioneFascicoli(**args)
    updated = reloaded.aggiorna(case.id, titolo='Titolo dal secondo processo')
    assert updated.note == 'Nota confermata dal primo processo'
    final = GestioneFascicoli(**args).get(case.id)
    assert final.note == updated.note and final.titolo == updated.titolo


def test_partial_command_uses_same_snapshot_and_preserves_other_cases(case_state, tmp_path):
    db, case, _ = case_state
    args = dict(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    full = GestioneFascicoli(**args)
    other = full.nuovo('Altro fascicolo da conservare', TipoFascicolo.ALTRO)
    before = dict(db.conn.execute('SELECT * FROM fascicoli WHERE id=?', (other.id,)).fetchone())
    partial = GestioneFascicoli(**args, carica_tutto=False)
    current = partial.get(case.id)
    current.note = 'Comando puntuale'
    partial._salva_fascicoli_parziale([current], rigenera_mirror=False)
    assert dict(db.conn.execute('SELECT * FROM fascicoli WHERE id=?', (other.id,)).fetchone()) == before
    assert GestioneFascicoli(**args).get(case.id).note == current.note


def test_delete_conflict_preserves_original_files_and_reload_deletes_normally(case_state, tmp_path):
    db, case, _ = case_state
    args = dict(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    first, stale = GestioneFascicoli(**args), GestioneFascicoli(**args)
    folder = first.documents_dir / case.id
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / 'controlled.txt'
    source.write_bytes(b'original controlled source')
    first.aggiorna(case.id, note='Aggiornamento prima della cancellazione')
    with pytest.raises(FascicoloConcurrentUpdate):
        stale.elimina(case.id)
    assert source.read_bytes() == b'original controlled source'
    assert not list(first.documents_dir.glob('.iusentra-delete-*'))
    fresh = GestioneFascicoli(**args)
    assert fresh.get(case.id).note == first.get(case.id).note
    fresh.elimina(case.id)
    assert db.conn.execute('SELECT id FROM fascicoli WHERE id=?', (case.id,)).fetchone() is None
    assert not folder.exists()


def test_rename_then_normal_edit_preserves_document_and_latest_snapshot(case_state, tmp_path):
    db, case, _ = case_state
    args = dict(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    manager = GestioneFascicoli(**args)
    document = manager.aggiungi_documento(case.id, 'prima.txt', TipoDocumento.ALLEGATO, b'controlled source')
    renamed = manager.rinomina_documento(case.id, document.id, 'dopo.txt')
    manager.aggiorna(case.id, note='Dopo la rinomina')
    final = GestioneFascicoli(**args).get(case.id)
    assert final.note == 'Dopo la rinomina' and final.documenti[0].nome == 'dopo.txt'
    assert (manager.documents_dir / renamed.percorso).read_bytes() == b'controlled source'


@pytest.mark.parametrize('keep_versions,reuse_path', [(True, False), (True, True), (False, True), (False, False)])
def test_failed_replacement_restores_bytes_versions_and_sql(case_state, tmp_path, keep_versions, reuse_path):
    db, case, _ = case_state
    args = dict(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    owner = GestioneFascicoli(**args)
    document = owner.aggiungi_documento(case.id, 'originale.pdf', TipoDocumento.ALLEGATO, b'original controlled PDF')
    stale = GestioneFascicoli(**args)
    owner.aggiorna(case.id, note='Decisione già confermata')
    with pytest.raises(FascicoloConcurrentUpdate):
        stale.sostituisci_documento(case.id, document.id, document.nome, b'unconfirmed PDF',
                                   preserve_version_snapshot=keep_versions, reuse_existing_path=reuse_path)
    current = GestioneFascicoli(**args).get(case.id)
    assert current.note == 'Decisione già confermata'
    assert current.documenti[0].to_dict() == document.to_dict()
    assert (owner.documents_dir / document.percorso).read_bytes() == b'original controlled PDF'
    assert len(list((owner.documents_dir / case.id).iterdir())) == 1


def test_failed_semantic_upload_removes_only_its_unconfirmed_version(case_state, tmp_path):
    db, case, _ = case_state
    args = dict(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    owner = GestioneFascicoli(**args)
    document = owner.aggiungi_documento(case.id, 'procura.pdf', TipoDocumento.PROCURA, b'original controlled source')
    stale = GestioneFascicoli(**args)
    owner.aggiorna(case.id, note='Decisione da conservare')
    with pytest.raises(FascicoloConcurrentUpdate):
        stale.aggiungi_documento(case.id, document.nome, TipoDocumento.PROCURA, b'different controlled version')
    current = GestioneFascicoli(**args).get(case.id)
    assert current.note == 'Decisione da conservare'
    assert current.documenti[0].to_dict() == document.to_dict()
    assert (owner.documents_dir / document.percorso).read_bytes() == b'original controlled source'
    assert len(list((owner.documents_dir / case.id).iterdir())) == 1


def test_partial_in_place_write_failure_restores_original_before_returning_error(case_state, tmp_path, monkeypatch):
    from pathlib import Path

    db, case, _ = case_state
    owner = GestioneFascicoli(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    document = owner.aggiungi_documento(case.id, 'originale.pdf', TipoDocumento.ALLEGATO, b'original controlled PDF')
    before = document.to_dict()
    path = owner.documents_dir / document.percorso
    write = Path.write_bytes
    attempts = []

    def fail_once(target, content):
        if target == path and not attempts:
            attempts.append(True)
            write(target, content[:3])
            raise OSError('Scrittura interrotta nella prova controllata')
        return write(target, content)

    monkeypatch.setattr(Path, 'write_bytes', fail_once)
    with pytest.raises(OSError, match='Scrittura interrotta'):
        owner.sostituisci_documento(case.id, document.id, document.nome, b'new controlled PDF',
                                   preserve_version_snapshot=False, reuse_existing_path=True)
    assert path.read_bytes() == b'original controlled PDF'
    assert document.to_dict() == before
    assert GestioneFascicoli(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db).get(case.id).documenti[0].to_dict() == before


def test_two_file_writers_cannot_restore_over_a_confirmed_replacement(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Event

    database = str(tmp_path / 'concurrent.db')
    path = str(tmp_path / 'fascicoli.json')
    db = StudioDB(database)
    manager = GestioneFascicoli(path, studio_db=db)
    case = manager.nuovo('Collaudo concorrenza file', TipoFascicolo.ALTRO)
    document = manager.aggiungi_documento(case.id, 'fonte.pdf', TipoDocumento.ALLEGATO, b'original PDF')
    loaded = Barrier(2)
    first_wrote, release_first, second_attempted = Event(), Event(), Event()

    def replace(first):
        connection = StudioDB(database)
        try:
            owner = GestioneFascicoli(path, studio_db=connection)
            loaded.wait(timeout=10)
            if first:
                save = owner._salva

                def paused_save():
                    first_wrote.set()
                    assert release_first.wait(timeout=10)
                    save()

                owner._salva = paused_save
            else:
                assert first_wrote.wait(timeout=10)
                second_attempted.set()
            try:
                owner.sostituisci_documento(case.id, document.id, document.nome,
                                           b'confirmed first PDF' if first else b'stale second PDF',
                                           preserve_version_snapshot=False, reuse_existing_path=True)
                return 'saved'
            except FascicoloConcurrentUpdate:
                return 'conflict'
        finally:
            connection.chiudi()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(replace, True)
            second = pool.submit(replace, False)
            assert second_attempted.wait(timeout=10)
            release_first.set()
            assert first.result(timeout=10) == 'saved'
            assert second.result(timeout=10) == 'conflict'
        final = GestioneFascicoli(path, studio_db=db).get(case.id).documenti[0]
        assert (manager.documents_dir / final.percorso).read_bytes() == b'confirmed first PDF'
        import hashlib
        assert final.hash_sha256 == hashlib.sha256(b'confirmed first PDF').hexdigest()
    finally:
        release_first.set()
        db.chiudi()


def test_hydrated_partial_case_keeps_original_documents_when_saving_note(case_state, tmp_path):
    db, case, _ = case_state
    args = dict(db_path=str(tmp_path / 'fascicoli.json'), studio_db=db)
    manager = GestioneFascicoli(**args)
    document = manager.aggiungi_documento(case.id, 'fonte.txt', TipoDocumento.ALLEGATO, b'controlled source')
    light = GestioneFascicoli(**args, senza_documenti=True)
    hydrated = light.idrata_documenti(light.get(case.id))
    hydrated.note = 'Nota dopo idratazione'
    light._salva_fascicoli_parziale([hydrated], rigenera_mirror=False)
    final = GestioneFascicoli(**args).get(case.id)
    assert final.note == hydrated.note and final.documenti[0].id == document.id


def test_new_case_does_not_rewrite_unchanged_stale_cases(case_state):
    db, case, row = case_state
    db.conn.execute('UPDATE fascicoli SET note=? WHERE id=?', ('Aggiornamento esterno', case.id))
    transaction(db).commit()
    another = clone(case)
    another.id = 'another-controlled-case'
    another.numero = '2026/99999'
    confirmed = save_changes(db, original_rows={case.id: row}, original_models={case.id: encode_model(case)},
                             current={case.id: case, another.id: another})
    assert set(confirmed) == {another.id}
    assert db.conn.execute('SELECT note FROM fascicoli WHERE id=?', (case.id,)).fetchone()[0] == 'Aggiornamento esterno'


def test_mirror_never_restores_stale_unchanged_cases(case_state, tmp_path):
    from pct import cache

    db, case, _ = case_state
    path = tmp_path / 'fascicoli.json'
    args = dict(db_path=str(path), studio_db=db)
    first, stale = GestioneFascicoli(**args), GestioneFascicoli(**args)
    first.aggiorna(case.id, note='Nota più recente confermata')
    other = stale.nuovo('Altro fascicolo senza riscrivere il primo', TipoFascicolo.ALTRO)
    mirror = cache.load(path)
    assert mirror[case.id]['note'] == 'Nota più recente confermata'
    assert mirror[other.id]['titolo'] == other.titolo
    partial = GestioneFascicoli(**args, carica_tutto=False)
    current = partial.get(other.id)
    current.note = 'Comando mirato'
    partial._salva_fascicoli_parziale([current])
    assert cache.load(path)[case.id]['note'] == 'Nota più recente confermata'


def test_mirror_failure_remains_pending_and_recovers_from_sql(case_state, tmp_path, monkeypatch):
    from pct import cache
    from pct.fascicoli_sql_mirror import deliver

    db, case, _ = case_state
    path = tmp_path / 'fascicoli.json'
    owner = GestioneFascicoli(str(path), studio_db=db)
    save = cache.save

    def unavailable(*args, **kwargs):
        raise OSError('Disco indisponibile nella prova controllata')

    monkeypatch.setattr(cache, 'save', unavailable)
    owner.aggiorna(case.id, note='Salvataggio SQL realmente confermato')
    assert db.conn.execute('SELECT note FROM fascicoli WHERE id=?', (case.id,)).fetchone()[0] == owner.get(case.id).note
    assert db.conn.execute("SELECT COUNT(*) FROM _meta WHERE chiave LIKE ?", ("fascicoli-mirror:%",)).fetchone()[0] == 1
    monkeypatch.setattr(cache, 'save', save)
    assert deliver(db, path) == 1
    assert cache.load(path)[case.id]['note'] == owner.get(case.id).note
    assert db.conn.execute("SELECT COUNT(*) FROM _meta WHERE chiave LIKE ?", ("fascicoli-mirror:%",)).fetchone()[0] == 0


def test_newer_mirror_delivery_is_not_acknowledged_by_older_save(case_state, tmp_path, monkeypatch):
    from pct import cache
    from pct.fascicoli_sql_mirror import deliver, enqueue

    db, case, _ = case_state
    path = tmp_path / 'fascicoli.json'
    owner = GestioneFascicoli(str(path), studio_db=db)
    save = cache.save

    def update_while_saving(*args, **kwargs):
        save(*args, **kwargs)
        row = db.conn.execute('SELECT dati_json FROM fascicoli WHERE id=?', (case.id,)).fetchone()
        payload = {**json.loads(row[0]), 'note': 'Modifica arrivata durante il mirror'}
        db.conn.execute('UPDATE fascicoli SET note=?,dati_json=? WHERE id=?', (payload['note'], json.dumps(payload), case.id))
        enqueue(db.conn, path, case.id, 'new-controlled-revision')
        transaction(db).commit()

    monkeypatch.setattr(cache, 'save', update_while_saving)
    owner.aggiorna(case.id, note='Prima versione')
    assert db.conn.execute("SELECT valore FROM _meta WHERE chiave LIKE ?", ("fascicoli-mirror:%",)).fetchone()[0] == 'new-controlled-revision'
    monkeypatch.setattr(cache, 'save', save)
    assert deliver(db, path) == 1
    assert cache.load(path)[case.id]['note'] == 'Modifica arrivata durante il mirror'


def test_scalar_edit_preserves_unknown_metadata_and_frozen_collections(case_state):
    db, case, row = case_state
    extra = json.loads(row['dati_json'])
    extra['historical_extension'] = {'provider': 'controlled', 'revision': 7}
    original_documents = '[ {"id":"proof-a", "historical_extra":{"value":123}} ]'
    db.conn.execute('UPDATE fascicoli SET dati_json=?,documenti_json=? WHERE id=?',
                    (json.dumps(extra), original_documents, case.id))
    transaction(db).commit()
    row = dict(db.conn.execute('SELECT * FROM fascicoli WHERE id=?', (case.id,)).fetchone())
    # Il modello resta quello che il lettore precedente conosceva; i campi
    # tecnici non esposti non vanno eliminati da una modifica della nota.
    changed = clone(case)
    changed.note = 'Nota aggiornata'
    save_changes(db, original_rows={case.id: row}, original_models={case.id: encode_model(case)},
                 current={case.id: changed})
    stored = db.conn.execute('SELECT dati_json,documenti_json,scadenze_json,profilo_deposito_json FROM fascicoli WHERE id=?',
                             (case.id,)).fetchone()
    assert json.loads(stored[0])['historical_extension'] == extra['historical_extension']
    assert stored[1] == original_documents
    assert stored[2] == row['scadenze_json'] and stored[3] == row['profilo_deposito_json']


def test_failed_composite_command_rolls_back_case_and_replication_event(case_state):
    from pct.offline_capture import CaptureContext, bind_node, capture_writes, prepare_node_schema
    from pct.offline_change_log import ensure_schema
    db, case, row = case_state
    ensure_schema(db.conn)
    prepare_node_schema(db.conn)
    bind_node(db.conn, tenant='studio-test', device='pc-test')
    transaction(db).commit()
    changed = clone(case)
    changed.note = 'Da annullare'
    db.conn.execute('BEGIN')
    with capture_writes(CaptureContext('studio-test', 'user-test', 'pc-test', frozenset({'fascicoli'}))):
        save_changes(db, original_rows={case.id: row}, original_models={case.id: encode_model(case)},
                     current={case.id: changed}, connection=db.conn)
    assert db.conn.execute('SELECT count(*) FROM offline_changes').fetchone()[0] == 1
    transaction(db).rollback()
    assert db.conn.execute('SELECT note FROM fascicoli WHERE id=?', (case.id,)).fetchone()[0] == case.note
    assert db.conn.execute('SELECT count(*) FROM offline_changes').fetchone()[0] == 0
