import json
import os
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from pct.pec_deposit_query_repository import PecDepositQueryRepository, install_deposit_query_events
from pct.pec_pipeline import sha256_json
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def receipts(request):
    if request.param == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato in questa esecuzione.')
    factory = SQLFactory(request.param)
    try:
        database = factory.new()
        suffix = '_postgres' if request.param == 'postgresql' else ''
        schema = (Path(__file__).resolve().parents[1] / f'pct/sql/20260521_pec_audit_pipeline{suffix}.sql').read_text(encoding='utf-8')
        if request.param == 'sqlite':
            database.conn.row_factory = sqlite3.Row
            database.conn.executescript(schema)
        else:
            with database.raw_conn.cursor() as cursor:
                cursor.execute(schema)
            database.raw_conn.commit()
        install_deposit_query_events(database.conn, postgres=request.param == 'postgresql')
        repository = PecDepositQueryRepository(database.conn, 'study-a')
        for key, stage in [('registry', 'accettazione_deposito'), ('pec', 'accettazione_pec')]:
            add_receipt(database.conn, key, stage)
            repository.project_message(database.conn, key)
        database.conn.execute("INSERT INTO pec_deposit_query_bootstrap VALUES ('study-a',1)")
        database.conn.execute("UPDATE transactional_outbox SET status='PROCESSED'")
        factory.commit(database)
        yield database, repository
    finally:
        factory.close()


def add_receipt(conn, key, stage):
    stamp = '2026-10-14T10:00:00+00:00'
    conn.execute('INSERT INTO pec_messages(id,tenant_id,account_email,folder,mime_sha256,mime_size,original_mime,received_at,ingested_at) '
                 "VALUES (?,'study-a','controlled@example.test','INBOX',?,10,?,?,?)", (key, key + '-controlled-hash', b'controlled', stamp, stamp))
    conn.execute('INSERT INTO pec_parsed_versions(id,message_id,version,parser_version,parsed_json,parsed_sha256,created_at) '
                 "VALUES (?,?,1,'controlled','{}',?,?)", (key + '-parsed', key, 'c' * 64, stamp))
    report = {'deposit_lifecycle': {'current_stage': {'id': stage}, 'final_state': 'accepted' if stage == 'accettazione_deposito' else '',
        'history_event': {'stage': stage, 'occurred_at': '2026-10-13T22:30:00Z'},
        'correlation': {'key': key + '-deposit', 'manual_review': False}}}
    conn.execute('INSERT INTO pec_validation_reports(id,message_id,parsed_version_id,event_type,report_json,report_sha256,severity,created_at) '
                 "VALUES (?,?,?,'pct_deposito',?,?,'ok',?)", (key + '-report', key, key + '-parsed', json.dumps(report), sha256_json(report), stamp))


def test_ricevute_interrogate_per_evento_reale_e_fase_senza_leggere_corpi(receipts):
    _, repo = receipts
    period = ((date(2026, 10, 14), date(2026, 10, 14)),)
    page = repo.list_page(state='ACCETTATO_CANCELLERIA', ranges=period)
    assert [row['message_id'] for row in page['rows']] == ['registry']
    assert page['rows'][0]['case_id'] == ''
    assert [row['message_id'] for row in repo.list_page(state='ACCETTATO_PEC', ranges=period)['rows']] == ['pec']
    assert repo.list_page(state='ACCETTATO_CANCELLERIA', ranges=((date(2026, 10, 13), date(2026, 10, 13)),))['rows'] == []
    assert all('report_json' not in row and 'original_mime' not in row for row in page['rows'])


def test_report_nuovo_impedisce_di_leggere_un_indice_superato(receipts):
    database, repo = receipts
    database.conn.execute("UPDATE pec_validation_reports SET event_type='altro' WHERE id='registry-report'")
    factory_commit = getattr(database, 'raw_conn', None) or database.conn
    factory_commit.commit()
    with pytest.raises(RuntimeError, match='non ancora confermato'):
        repo.list_page(state='ACCETTATO_CANCELLERIA')


@pytest.mark.parametrize('statement', [
    "UPDATE pec_parsed_versions SET version=2 WHERE id='registry-parsed'",
    "UPDATE pec_validation_reports SET created_at='2026-10-16T11:00:00Z' WHERE id='registry-report'",
])
def test_modifiche_ordinamento_invalidano_il_catalogo(receipts, statement):
    database, repo = receipts
    database.conn.execute(statement)
    (getattr(database, 'raw_conn', None) or database.conn).commit()
    with pytest.raises(RuntimeError, match='non ancora confermato'):
        repo.list_page(state='ACCETTATO_CANCELLERIA')


def test_recupero_puntuale_non_ripropone_un_report_non_piu_di_deposito(receipts):
    database, repo = receipts
    database.conn.execute("UPDATE pec_validation_reports SET event_type='altro' WHERE id='registry-report'")
    target = getattr(database, 'raw_conn', None) or database.conn
    def finish(_conn, *, rollback=False):
        target.rollback() if rollback else target.commit()
    finish(database.conn)
    repo.retry_events(finish=finish)
    assert repo.list_page(state='ACCETTATO_CANCELLERIA')['rows'] == []
    assert [row['message_id'] for row in repo.list_page(state='ACCETTATO_PEC')['rows']] == ['pec']


def test_report_non_valido_resta_esplicito_senza_bloccare_le_altre_ricevute(receipts):
    database, repo = receipts
    original = database.conn.execute("SELECT original_mime,mime_sha256 FROM pec_messages WHERE id='registry'").fetchone()
    database.conn.execute("UPDATE pec_validation_reports SET report_sha256=? WHERE id='registry-report'", ('0' * 64,))
    target = getattr(database, 'raw_conn', None) or database.conn
    def finish(_conn, *, rollback=False):
        target.rollback() if rollback else target.commit()
    finish(database.conn)
    result = repo.retry_events(finish=finish)
    assert result['failed'] == 0
    page = repo.list_page(state='ACCETTATO_PEC')
    assert [row['message_id'] for row in page['rows']] == ['pec']
    assert page['unconfirmed_source_count'] == 1
    assert page['unconfirmed_sources'][0]['message_id'] == 'registry'
    assert page['unconfirmed_sources'][0]['issue'] == 'receipt_report_not_confirmed'
    assert repo.list_page(state='ACCETTATO_CANCELLERIA')['rows'] == []
    assert tuple(database.conn.execute("SELECT original_mime,mime_sha256 FROM pec_messages WHERE id='registry'").fetchone()) == tuple(original)
    assert database.conn.execute("SELECT report_sha256 FROM pec_validation_reports WHERE id='registry-report'").fetchone()[0] == '0' * 64
    assert repo.retry_events(finish=finish)['delivered'] == 0


def test_mime_sostituito_non_rivalida_report_vecchio_nei_retry(receipts):
    database, repo = receipts
    database.conn.execute("UPDATE pec_messages SET mime_sha256=? WHERE id='registry'", ('f' * 64,))
    target = getattr(database, 'raw_conn', None) or database.conn

    def finish(_conn, *, rollback=False):
        target.rollback() if rollback else target.commit()

    finish(database.conn)
    assert repo.retry_events(finish=finish)['failed'] == 0
    for _ in range(2):
        page = repo.list_page(state='ACCETTATO_CANCELLERIA')
        assert not page['rows']
        assert page['unconfirmed_sources'][0]['issue'] == 'receipt_source_revision_changed'
        repo.project_message(database.conn, 'registry')
        finish(database.conn)


def test_proiezione_non_aggiorna_messaggi_neanche_a_valori_identici(tmp_path):
    path = tmp_path / 'audit.sqlite'
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        schema = (Path(__file__).resolve().parents[1] / 'pct/sql/20260521_pec_audit_pipeline.sql').read_text()
        conn.executescript(schema)
        install_deposit_query_events(conn)
        add_receipt(conn, 'one', 'accettazione_deposito')
        conn.commit()

        def authorize(action, table, _column, *_):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_UPDATE and table == 'pec_messages' else sqlite3.SQLITE_OK

        conn.set_authorizer(authorize)
        repo = PecDepositQueryRepository(conn, 'study-a')
        repo.project_message(conn, 'one')
        assert conn.execute('SELECT state FROM pec_deposit_query_index').fetchone()[0] == 'ACCETTATO_CANCELLERIA'
        from pct.pec_deposit_query_migration import begin, rebuild_batch

        state = begin(conn, tenant='study-a', backup_reference='verified-controlled-snapshot',
                      backup_sha256='a' * 64, actor='controlled-migration')
        result = rebuild_batch(conn, repo, migration_id=state['id'], after_key='', actor='controlled-migration')
        assert result['processed'] == 1
