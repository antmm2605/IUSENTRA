import os
import sqlite3
from pathlib import Path

import pytest

from pct.agenda_sql_writer import COLUMNS as AGENDA_COLUMNS
from pct.calendar_query_preparation import prepare_calendar_query_catalog
from pct.calendar_query_repository import CalendarQueryRepository
from pct.scadenziario_sql_writer import COLUMNS as DEADLINE_COLUMNS
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def store(request):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato in questa esecuzione.')
    factory = SQLFactory(request.param)
    try:
        db = factory.new()
        db.backend_kind = request.param
        if request.param == 'sqlite':
            db.conn.row_factory = sqlite3.Row
            db.db_path = Path(factory.temp.name) / 'controlled.db'
        else:
            from psycopg2.extensions import make_dsn
            db.dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
        for table, columns in [('appuntamenti', AGENDA_COLUMNS + ('modificato_il',)), ('scadenze', DEADLINE_COLUMNS)]:
            db.conn.execute(f'CREATE TABLE {table} (' + ','.join(key + ' TEXT' + (' PRIMARY KEY' if key == 'id' else '') for key in columns) + ')')
        factory.commit(db)
        yield db
    finally:
        factory.close()


def test_nuovo_studio_ha_entrambi_i_cataloghi_con_backup_nativo(store, tmp_path, monkeypatch):
    assert prepare_calendar_query_catalog(store, tenant='controlled-study', backup_dir=tmp_path / 'backup')
    repository = CalendarQueryRepository(store, 'controlled-study')
    assert repository.list_page(domain='agenda')['rows'] == []
    assert repository.list_page(domain='deadlines')['rows'] == []
    assert all((tmp_path / 'backup' / domain / 'manifest.json').is_file() for domain in ('agenda', 'deadlines'))
    monkeypatch.setattr('pct.calendar_query_preparation.rebuild', lambda *a, **kw: pytest.fail('Preparazione già conclusa'))
    assert not prepare_calendar_query_catalog(store, tenant='controlled-study', backup_dir=tmp_path / 'backup')
    with pytest.raises(ValueError, match='altro studio'):
        prepare_calendar_query_catalog(store, tenant='another-study', backup_dir=tmp_path / 'other-backup')
