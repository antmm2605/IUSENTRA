import importlib
import json
import os
from dataclasses import replace

import pytest

from pct.agenda import Appuntamento, TipoAppuntamento
from pct.calendar_sql_records import appointment_from_row, deadline_from_row
from pct.scadenziario import Scadenza
from pct.storage import StudioDB


@pytest.fixture
def calendar_database(tmp_path):
    factory = None
    if os.environ.get('OFFLINE_RECEIVE_TEST_POSTGRES') == '1':
        from psycopg2.extensions import make_dsn
        from pct.storage_postgres import PostgresStudioDB
        from tests.test_condivisioni_sql_repository import SQLFactory
        factory = SQLFactory('postgresql')
        db = PostgresStudioDB(make_dsn(**factory.pg_parameters,
            options=f'-c search_path={factory.schema}'))
    else:
        db = StudioDB(str(tmp_path / 'controlled-calendar.db'))
    try:
        yield db
    finally:
        db.chiudi()
        if factory is not None:
            factory.close()


def transaction(db):
    return getattr(db, 'raw_conn', None) or db.conn


@pytest.mark.parametrize('module,table,reader,model', [
    ('pct.agenda_sql_writer', 'appuntamenti', appointment_from_row,
     Appuntamento('controlled-calendar', 'Collaudo', TipoAppuntamento.ALTRO, '2026-12-01T10:00:00', 30, 'Studio')),
    ('pct.scadenziario_sql_writer', 'scadenze', deadline_from_row,
     Scadenza(id='controlled-deadline', titolo='Collaudo', data_scadenza='2026-12-01')),
])
def test_native_edit_preserves_historical_json_extensions_and_stale_snapshot_guard(calendar_database, module, table, reader, model):
    db = calendar_database
    writer = importlib.import_module(module)
    writer.save_changes(db, original_rows={}, original_models={}, current={model.id: model})
    original = json.loads(db.conn.execute(f'SELECT dati_json FROM {table} WHERE id=?', (model.id,)).fetchone()[0])
    extension = {'source': 'controlled-import', 'history': [{'id': 'source-one', 'revision': 7}], 'flags': {'retained': True}}
    original['controlled_legacy_extension'] = extension
    db.conn.execute(f'UPDATE {table} SET dati_json=? WHERE id=?', (json.dumps(original), model.id))
    transaction(db).commit()
    row = dict(db.conn.execute(f'SELECT * FROM {table} WHERE id=?', (model.id,)).fetchone())
    projected = reader(row)
    transaction(db).rollback()
    changed = replace(projected, note='Nota aggiornata dal motore nativo')
    writer.save_changes(db, original_rows={model.id: row},
        original_models={model.id: writer.encode_model(projected)}, current={model.id: changed})
    stored = json.loads(db.conn.execute(f'SELECT dati_json FROM {table} WHERE id=?', (model.id,)).fetchone()[0])
    assert stored['controlled_legacy_extension'] == extension
    assert stored['note'] == changed.note
    transaction(db).rollback()
    with pytest.raises(RuntimeError, match='altro processo'):
        writer.save_changes(db, original_rows={model.id: row},
            original_models={model.id: writer.encode_model(projected)},
            current={model.id: replace(projected, note='Bozza superata')})
    stored = json.loads(db.conn.execute(f'SELECT dati_json FROM {table} WHERE id=?', (model.id,)).fetchone()[0])
    assert stored['note'] == changed.note and stored['controlled_legacy_extension'] == extension
