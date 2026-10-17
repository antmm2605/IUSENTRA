"""Snapshot completi dei modelli: metadati intatti e conflitti espliciti."""
import os

import pytest

from pct.template_atti_repository import GestioneTemplateRepository
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def template_sql(request, tmp_path):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato')
    factory = SQLFactory(request.param)
    options = {}
    if request.param == 'postgresql':
        from psycopg2.extensions import make_dsn
        options['postgres_dsn'] = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
    path = str(tmp_path / 'template_repository.db')
    repository = GestioneTemplateRepository(path, **options)
    try:
        yield repository, path, options
    finally:
        if repository._postgres_backend:
            repository._postgres_backend.close()
        factory.close()


def test_snapshot_conserva_formattazione_campi_date_e_riapertura(template_sql):
    repository, path, options = template_sql
    snapshot, revision = repository.read_runtime_snapshot()
    assert snapshot == [] and revision is None
    source = [dict(id='controlled', titolo='Modello controllato',
        corpo='<p style="color:#123456"><strong>È {{ cliente.nome }}</strong></p>',
        campi_guidati=[dict(name='cliente.nome', label='Cliente', type='text')],
        creato_il='2026-10-10T09:12:00', modificato_il='2026-10-11T10:00:00',
        extra=dict(font='Times New Roman', interlinea=1.6))]
    revision = repository.compare_and_save_runtime_state(source, expected_json=revision)
    reader = GestioneTemplateRepository(path, initialize_schema=False, read_only=True, **options)
    try:
        assert reader.read_runtime_snapshot() == (source, revision)
    finally:
        if reader._postgres_backend:
            reader._postgres_backend.close()


def test_scrittura_ripetuta_non_aggiorna_e_conflitto_preserva_ultimo(template_sql):
    repository, _, _ = template_sql
    first = repository.compare_and_save_runtime_state([dict(id='one', titolo='Prima')], expected_json=None)
    assert repository.compare_and_save_runtime_state([dict(id='one', titolo='Prima')], expected_json=first) == first
    second = repository.compare_and_save_runtime_state([dict(id='one', titolo='Seconda')], expected_json=first)
    with pytest.raises(RuntimeError, match='modificat'):
        repository.compare_and_save_runtime_state([dict(id='one', titolo='Obsoleta')], expected_json=first)
    assert repository.read_runtime_snapshot() == ([dict(id='one', titolo='Seconda')], second)


def test_snapshot_corrotto_non_diventa_catalogo_vuoto(template_sql):
    repository, _, _ = template_sql
    repository.compare_and_save_runtime_state([], expected_json=None)
    with repository._connection() as conn:
        conn.execute("UPDATE template_runtime_state SET templates_json=? WHERE state_id='templates'", ('{}',))
        conn.commit()
    with pytest.raises(ValueError, match='modelli'):
        repository.read_runtime_snapshot()


def test_proiezione_obsoleta_non_cancella_catalogo(template_sql):
    repository, _, _ = template_sql
    first = repository.compare_and_save_runtime_state([dict(id='one')], expected_json=None)
    latest = repository.compare_and_save_runtime_state([dict(id='two')], expected_json=first)
    before = repository.load_repository_payload()
    with pytest.raises(RuntimeError, match='modificat'):
        repository.rebuild_from_payload({}, expected_runtime_json=first)
    assert repository.load_repository_payload() == before
    assert repository.read_runtime_snapshot() == ([dict(id='two')], latest)


def test_preparazione_con_snapshot_esistente_conserva_modello_sql(template_sql, tmp_path):
    from pct.template_atti_preparation import catalog_ready, prepare_catalog

    repository, path, options = template_sql
    source = str(tmp_path / 'templates.json')
    payload = [dict(id='existing', titolo='Modello SQL', categoria='Civile',
                    corpo='<p><em>È già presente</em></p>', extra={'origine': 'SQL'})]
    repository.compare_and_save_runtime_state(payload, expected_json=None)
    assert not catalog_ready(source, **options)
    result = prepare_catalog(source, backup_dir=tmp_path / 'backup', writers_drained=True, **options)
    assert result['changed']
    assert catalog_ready(source, **options)
    stored, _ = repository.read_runtime_snapshot()
    assert stored[0]['id'] == 'existing' and stored[0]['extra'] == payload[0]['extra']


def test_prima_adozione_da_json_conserva_modelli_su_entrambi_backend(template_sql, tmp_path):
    import json

    from pct.template_atti_preparation import catalog_ready, prepare_catalog

    repository, _, options = template_sql
    source = tmp_path / 'templates.json'
    source.write_text(json.dumps({'old': dict(id='old', titolo='Modello storico',
        categoria='Civile', corpo='<p>È storico</p>', extra={'stile': 'corsivo'})}), encoding='utf-8')
    prepare_catalog(source, backup_dir=tmp_path / 'backup', writers_drained=True, **options)
    assert catalog_ready(source, **options)
    items, _ = repository.read_runtime_snapshot()
    assert items[0]['id'] == 'old' and items[0]['extra'] == {'stile': 'corsivo'}


def test_gestore_consultativo_non_legge_json_e_non_scrive(tmp_path, monkeypatch):
    import sqlite3

    from pct.template_atti import GestioneTemplateAtti

    path = str(tmp_path / 'templates.json')
    writer = GestioneTemplateAtti(path)
    custom = writer.crea('È una prova', 'Civile', '<p><strong>Cliente</strong></p>')
    before = {p.name: p.read_bytes() for p in tmp_path.glob('*.json')}
    with sqlite3.connect(writer.repository_db_path) as connection:
        sql_before = list(connection.iterdump())

    def forbidden(*args, **kwargs):
        raise AssertionError('Una consultazione non deve salvare o sincronizzare')

    monkeypatch.setattr(GestioneTemplateAtti, '_salva', forbidden)
    monkeypatch.setattr(GestioneTemplateAtti, '_sync_repository', forbidden)
    monkeypatch.setattr('pct.template_atti.json.load', forbidden)
    reader = GestioneTemplateAtti(path, read_only=True)
    assert reader.get(custom.id).corpo == custom.corpo
    for operation in (
        lambda: reader.crea('Vietato', 'Civile', 'Testo'),
        lambda: reader.aggiorna(custom.id, corpo='Vietato'),
        lambda: reader.elimina(custom.id),
        lambda: reader.import_template_repository(path),
        lambda: reader.export_template_repository(path),
    ):
        with pytest.raises(PermissionError, match='sola lettura'):
            operation()
    assert {p.name: p.read_bytes() for p in tmp_path.glob('*.json')} == before
    with sqlite3.connect(writer.repository_db_path) as connection:
        assert list(connection.iterdump()) == sql_before
