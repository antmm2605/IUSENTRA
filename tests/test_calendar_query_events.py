import os

import pytest

from pct.agenda_sql_writer import COLUMNS as AGENDA_COLUMNS
from pct.calendar_query_schema import install_calendar_query_events
from pct.scadenziario_sql_writer import COLUMNS as DEADLINE_COLUMNS
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.mark.parametrize('backend', ['sqlite', 'postgresql'])
def test_eventi_calendario_solo_per_mutazioni_e_proprietario_registrato(backend):
    if backend == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato in questa esecuzione.')
    factory = SQLFactory(backend)
    try:
        db = factory.new()
        for table, columns in [('appuntamenti', AGENDA_COLUMNS + ('modificato_il',)), ('scadenze', DEADLINE_COLUMNS)]:
            db.conn.execute(f"CREATE TABLE {table} (" + ','.join(key + ' TEXT' + (' PRIMARY KEY' if key == 'id' else '') for key in columns) + ')')
        install_calendar_query_events(db.conn, postgres=backend == 'postgresql')
        db.conn.execute("INSERT INTO appuntamenti(id,titolo) VALUES ('before-owner','Prima')")
        assert db.conn.execute('SELECT COUNT(*) FROM transactional_outbox').fetchone()[0] == 0
        db.conn.execute("INSERT INTO calendar_query_owner VALUES (1,'studio-controllato',1)")
        db.conn.execute("UPDATE appuntamenti SET titolo=titolo WHERE id='before-owner'")
        assert db.conn.execute('SELECT COUNT(*) FROM transactional_outbox').fetchone()[0] == 0
        db.conn.execute("UPDATE appuntamenti SET dati_json='{}' WHERE id='before-owner'")
        db.conn.execute("UPDATE appuntamenti SET modificato_il='2026-10-16T12:00:00' WHERE id='before-owner'")
        db.conn.execute("INSERT INTO scadenze(id,titolo) VALUES ('termine','Controllato')")
        db.conn.execute("DELETE FROM scadenze WHERE id='termine'")
        rows = db.conn.execute('SELECT tenant_id,aggregate_type,aggregate_id,event_type FROM transactional_outbox').fetchall()
        assert len(rows) == 4
        assert {row[0] for row in rows} == {'studio-controllato'}
        assert {row[1] for row in rows} == {'calendar_query:agenda', 'calendar_query:deadlines'}
        assert {row[3] for row in rows} == {'calendar_query.refresh_requested'}
        factory.commit(db)
    finally:
        factory.close()
