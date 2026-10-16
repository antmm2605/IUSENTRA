import os
import sqlite3
from datetime import date

import pytest

from pct.agenda_sql_writer import COLUMNS as AGENDA_COLUMNS
from pct.calendar_query_repository import CalendarQueryNotReady, CalendarQueryRepository
from pct.calendar_query_schema import install_calendar_query_events
from pct.scadenziario_sql_writer import COLUMNS as DEADLINE_COLUMNS
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def catalog(request):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato in questa esecuzione.')
    factory = SQLFactory(request.param)
    try:
        db = factory.new()
        if request.param == 'sqlite':
            db.conn.row_factory = sqlite3.Row
        for table, columns in [('appuntamenti', AGENDA_COLUMNS + ('modificato_il',)), ('scadenze', DEADLINE_COLUMNS)]:
            db.conn.execute(f"CREATE TABLE {table} (" + ','.join(key + ' TEXT' + (' PRIMARY KEY' if key == 'id' else '') for key in columns) + ')')
        install_calendar_query_events(db.conn, postgres=request.param == 'postgresql')
        db.conn.execute("INSERT INTO calendar_query_owner VALUES (1,'study-a',1)")
        db.conn.execute("INSERT INTO calendar_query_bootstrap VALUES ('study-a','agenda',1)")
        repo = CalendarQueryRepository(db, 'study-a')
        for key in ['one', 'two', 'three']:
            db.conn.execute("INSERT INTO appuntamenti(id,titolo,tipo,stato,data_ora,durata_minuti,luogo) "
                             "VALUES (?,?,'CONSULTAZIONE','PROGRAMMATO','2026-10-13T22:30:00Z','30','Studio')", (key, key))
            row = db.conn.execute('SELECT * FROM appuntamenti WHERE id=?', (key,)).fetchone()
            repo.project_record(db.conn, domain='agenda', key=key, row=row)
        db.conn.execute("UPDATE transactional_outbox SET status='PROCESSED'")
        factory.commit(db)
        yield db, repo
    finally:
        factory.close()


def test_calendario_pagina_giorno_e_stato_senza_rilettura_globale(catalog):
    db, repo = catalog
    period = ((date(2026, 10, 14), date(2026, 10, 14)),)
    first = repo.list_page(domain='agenda', ranges=period, states=('PROGRAMMATO',), limit=2)
    assert first['has_more']
    second = repo.list_page(domain='agenda', ranges=period, states=('PROGRAMMATO',), limit=2, cursor=first['cursor'])
    assert not second['has_more']
    assert {row['id'] for row in first['rows'] + second['rows']} == {'one', 'two', 'three'}
    assert repo.list_page(domain='agenda', states=('COMPLETATO',))['rows'] == []
    assert repo.list_page(domain='agenda', ranges=((date(2026, 10, 13), date(2026, 10, 13)),))['rows'] == []


def test_mutazione_pendente_e_proprietario_discordante_non_sembrano_zero(catalog):
    db, repo = catalog
    with pytest.raises(CalendarQueryNotReady):
        CalendarQueryRepository(db, 'other-study').list_page(domain='agenda')
    db.conn.execute("UPDATE appuntamenti SET titolo='Cambiato' WHERE id='one'")
    with pytest.raises(CalendarQueryNotReady):
        repo.list_page(domain='agenda')


def test_migrazione_riprendibile_richiede_backup_autore_e_lotti_confermati(catalog):
    from pct.calendar_query_migration import begin, rebuild_batch

    db, repo = catalog
    args = dict(tenant='study-a', domain='agenda', backup_reference='controlled-backup', backup_sha256='a' * 64, actor='controlled')
    state = begin(db.conn, **args)
    with pytest.raises(CalendarQueryNotReady):
        repo.list_page(domain='agenda')
    first = rebuild_batch(db.conn, repo, domain='agenda', migration_id=state['id'], after_key='', actor='controlled', limit=1)
    assert first['processed'] == 1
    resumed = begin(db.conn, **args)
    assert resumed['after_key'] == first['after_key']
    with pytest.raises(ValueError):
        rebuild_batch(db.conn, repo, domain='agenda', migration_id=state['id'], after_key='', actor='controlled')
    with pytest.raises(ValueError):
        begin(db.conn, **dict(args, backup_sha256='b' * 64))
    state = first
    for _ in range(4):
        if state['phase'] == 'COMPLETED':
            break
        state = rebuild_batch(db.conn, repo, domain='agenda', migration_id=state['id'], after_key=state['after_key'], actor='controlled', limit=1)
    assert state['phase'] == 'COMPLETED'
    assert len(repo.list_page(domain='agenda')['rows']) == 3


def test_worker_riusa_coda_e_non_rilegge_righe_non_modificate(catalog):
    db, repo = catalog
    db.conn.execute("UPDATE appuntamenti SET titolo='Nuovo titolo' WHERE id='one'")
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    assert repo.retry_events(domain='agenda', limit=1) == dict(delivered=1, failed=0)
    assert repo.retry_events(domain='agenda', limit=1) == dict(delivered=0, failed=0)
    rows = repo.list_page(domain='agenda')['rows']
    assert next(row['titolo'] for row in rows if row['id'] == 'one') == 'Nuovo titolo'
    db.conn.execute("DELETE FROM appuntamenti WHERE id='one'")
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    assert repo.retry_events(domain='agenda') == dict(delivered=1, failed=0)
    assert len(repo.list_page(domain='agenda')['rows']) == 2


def test_indice_rimosso_non_simula_assenza_di_appuntamenti(catalog):
    db, repo = catalog
    db.conn.execute("DELETE FROM calendar_query_index WHERE tenant_key='study-a' AND domain='agenda' AND record_key='one'")
    (getattr(db, 'raw_conn', None) or db.conn).commit()
    with pytest.raises(CalendarQueryNotReady):
        repo.list_page(domain='agenda')
    assert repo.retry_events(domain='agenda') == dict(delivered=1, failed=0)
    assert len(repo.list_page(domain='agenda')['rows']) == 3


def test_proiezione_in_transazione_e_guasto_non_annullano_il_salvataggio(catalog, monkeypatch):
    from pct.calendar_query_writer import project_if_registered

    db, repo = catalog
    target = getattr(db, 'raw_conn', None) or db.conn
    db.conn.execute("UPDATE appuntamenti SET titolo='Salvato' WHERE id='one'")
    project_if_registered(db.conn, domain='agenda', keys=['one'])
    target.commit()
    assert next(row['titolo'] for row in repo.list_page(domain='agenda')['rows'] if row['id'] == 'one') == 'Salvato'
    db.conn.execute("UPDATE appuntamenti SET titolo='Fonte confermata' WHERE id='one'")
    with monkeypatch.context() as patch:
        def unavailable(*args, **kwargs):
            raise RuntimeError('Guasto controllato della proiezione')
        patch.setattr(CalendarQueryRepository, 'project_record', unavailable)
        project_if_registered(db.conn, domain='agenda', keys=['one'])
    target.commit()
    assert db.conn.execute("SELECT titolo FROM appuntamenti WHERE id='one'").fetchone()[0] == 'Fonte confermata'
    with pytest.raises(CalendarQueryNotReady):
        repo.list_page(domain='agenda')
    assert repo.retry_events(domain='agenda') == dict(delivered=1, failed=0)
