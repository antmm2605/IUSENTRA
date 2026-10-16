"""Consultazioni SQL controllate, senza toccare dati operativi."""

import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pct.email_mailbox_query_index import projected_fields
from pct.email_mailbox_repository import EmailMailboxRepository, MailboxConflict, MailboxQueryIndexNotReady
from tests.test_condivisioni_sql_repository import SQLFactory


@pytest.fixture(params=['sqlite', 'postgresql'])
def mailbox(request):
    backend = request.param
    if backend == 'postgresql' and not os.getenv('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('PostgreSQL controllato non configurato: parità non verificata in questa esecuzione.')
    factory = SQLFactory(backend)
    repo = EmailMailboxRepository(factory.new(), 'studio-a', 'pec')
    repo.ensure_schema()
    records = {
        'previous': {'id': 'previous', 'cartella': 'INBOX', 'data': '2026-10-13T21:59:59Z'},
        'midnight': {'id': 'midnight', 'cartella': 'INBOX', 'data': '2026-10-13T22:00:00Z'},
        'late': {'id': 'late', 'cartella': 'INBOX', 'data': '2026-10-14T21:59:59Z'},
        'next': {'id': 'next', 'cartella': 'INBOX', 'data': '2026-10-14T22:00:00Z'},
        'accepted-pec': {'id': 'accepted-pec', 'cartella': 'INBOX', 'data': '2026-10-14T12:00:00+02:00', 'stato_pct': 'ACCETTATO_PEC'},
        'accepted-office': {'id': 'accepted-office', 'cartella': 'INBOX', 'data': '2026-10-14T12:00:00+02:00', 'stato_pct': 'ACCETTATO_CANCELLERIA'},
        'sent': {'id': 'sent', 'cartella': 'CESTINO', 'origine': 'INVIATA', 'data': '2026-10-14T12:00:00+02:00'},
        'unknown': {'id': 'unknown', 'cartella': 'INBOX', 'data': 'non valida'},
    }
    repo.initialize(records, source_of_truth=backend)
    other = EmailMailboxRepository(factory.new(), 'studio-b', 'pec')
    other.initialize({'other': {'id': 'other', 'cartella': 'INBOX', 'data': '2026-10-14T12:00:00+02:00'}}, source_of_truth=backend)
    yield repo
    factory.close()


def test_giorno_italiano_prima_del_limite_e_tenant(mailbox):
    statements = []
    connection = mailbox.db.conn
    def execute(sql, params=()):
        statements.append(sql)
        return connection.execute(sql, params)
    with patch.object(mailbox, 'load', side_effect=AssertionError('Nessun catalogo completo')), patch.object(mailbox.db, 'conn', SimpleNamespace(execute=execute)):
        result = mailbox.query_records(ranges=((date(2026, 10, 14), date(2026, 10, 14)),), direction='received', limit=2)
        assert result['has_more']
        seen = {row['id'] for row in result['rows']}
        while result['has_more']:
            result = mailbox.query_records(ranges=((date(2026, 10, 14), date(2026, 10, 14)),), direction='received', limit=2, cursor=result['cursor'])
            assert not seen.intersection(row['id'] for row in result['rows'])
            seen.update(row['id'] for row in result['rows'])
    assert seen == {'midnight', 'late', 'accepted-pec', 'accepted-office'}
    assert result['unknown_date_count'] == 1
    assert statements and all(sql.startswith('SELECT') for sql in statements)
    assert not any('NOT EXISTS' in sql for sql in statements)


def test_accettazione_pec_non_equivale_a_cancelleria(mailbox):
    result = mailbox.query_records(deposit_status='ACCETTATO_CANCELLERIA')
    assert [row['id'] for row in result['rows']] == ['accepted-office']
    assert [row['id'] for row in mailbox.query_records(direction='sent')['rows']] == ['sent']


def test_cestino_e_direzione_sono_filtri_indipendenti(mailbox):
    assert [row['id'] for row in mailbox.query_records(folder='CESTINO')['rows']] == ['sent']
    assert not mailbox.query_records(folder='CESTINO', direction='received')['rows']
    assert mailbox.query_records(folder='CESTINO')['unknown_date_count'] == 0
    with pytest.raises(ValueError, match='Cartella'):
        mailbox.query_records(folder="CESTINO' OR 1=1")


def test_origine_nativa_preservata_e_direzione_incerta_esplicita(mailbox):
    assert projected_fields({'cartella': 'CESTINO', 'origine': 'INVIATI'})[1] == 'sent'
    assert projected_fields({'cartella': 'CESTINO', 'origine': 'BOZZE'})[1] == 'draft'
    records = mailbox.load()
    records['unknown-direction'] = {'id': 'unknown-direction', 'cartella': 'CESTINO', 'origine': 'CESTINO',
                                   'data': '2026-10-14T12:00:00+02:00'}
    mailbox.save(records, actor_key='controlled-user')
    page = mailbox.query_records(direction='received', ranges=((date(2026, 10, 14), date(2026, 10, 14)),))
    assert page['unknown_direction_count'] == 1
    assert 'unknown-direction' not in {row['id'] for row in page['rows']}
    assert mailbox.query_records(direction='received', ranges=((date(2026, 10, 15), date(2026, 10, 15)),))['unknown_direction_count'] == 0


def test_proiezione_mancante_non_restituisce_un_falso_zero(mailbox):
    mailbox.db.conn.execute('DELETE FROM email_mailbox_query_index WHERE tenant_key=? AND message_key=?', ('studio-a', 'midnight'))
    SQLFactory.commit(mailbox.db)
    with pytest.raises(MailboxQueryIndexNotReady):
        mailbox.query_records()
    migration = mailbox.begin_query_index_migration(backup_reference='controlled-snapshot', backup_sha256='a' * 64,
                                                    actor_key='controlled-migration')
    cursor = ''
    while True:
        result = mailbox.rebuild_query_index_batch(migration_id=migration['id'], after_key=cursor, limit=2, actor_key='controlled-migration')
        cursor = result['after_key']
        if result['done']:
            break
    assert len(mailbox.query_records()['rows']) == 8


def test_scritture_native_aggiornano_la_stessa_proiezione(mailbox):
    rows = mailbox.load()
    rows['accepted-pec']['stato_pct'] = 'ACCETTATO_CANCELLERIA'
    mailbox.save(rows, actor_key='controlled-user')
    assert len(mailbox.query_records(deposit_status='ACCETTATO_CANCELLERIA')['rows']) == 2
    rows = mailbox.load()
    del rows['accepted-pec']
    mailbox.save(rows, actor_key='controlled-user')
    assert len(mailbox.query_records(deposit_status='ACCETTATO_CANCELLERIA')['rows']) == 1


def test_produttore_sql_diretto_non_produce_falso_indice_aggiornato(mailbox):
    from pct.email_mailbox_query_events import AGGREGATE_PREFIX, EVENT_TYPE

    mailbox.db.conn.execute('UPDATE email_mailbox_records SET payload_json=? '
                            'WHERE tenant_key=? AND mailbox_kind=? AND message_key=?',
                            ('{"id":"midnight","data":"2026-10-16T12:00:00+02:00"}', 'studio-a', 'pec', 'midnight'))
    SQLFactory.commit(mailbox.db)
    with pytest.raises(MailboxQueryIndexNotReady):
        mailbox.query_records()
    mailbox.db.conn.execute("UPDATE transactional_outbox SET status='FAILED' WHERE tenant_id=? "
                            "AND aggregate_type=? AND event_type=? AND status='PENDING'",
                            ('studio-a', AGGREGATE_PREFIX + 'pec', EVENT_TYPE))
    SQLFactory.commit(mailbox.db)
    with pytest.raises(MailboxQueryIndexNotReady):
        mailbox.query_records()


def test_rollback_fonte_annulla_anche_invalidazione(mailbox):
    mailbox.db.conn.execute('DELETE FROM email_mailbox_records WHERE tenant_key=? '
                            'AND mailbox_kind=? AND message_key=?', ('studio-a', 'pec', 'midnight'))
    target = getattr(mailbox.db, 'raw_conn', None) or mailbox.db.conn
    target.rollback()
    assert 'midnight' in {row['id'] for row in mailbox.query_records()['rows']}


def test_recupero_evento_puntuale_e_ripetizione_senza_doppioni(mailbox):
    mailbox.db.conn.execute('DELETE FROM email_mailbox_query_index WHERE tenant_key=? AND message_key=?',
                            ('studio-a', 'midnight'))
    SQLFactory.commit(mailbox.db)
    with patch.object(mailbox, 'load', side_effect=AssertionError('Catalogo intero non richiesto')):
        assert mailbox.retry_query_index_events(limit=1) == {'delivered': 1, 'failed': 0}
        assert mailbox.retry_query_index_events(limit=1) == {'delivered': 0, 'failed': 0}
    assert 'midnight' in {row['id'] for row in mailbox.query_records()['rows']}


def test_cancellazione_fonte_pulisce_solo_proiezione_pendente(mailbox):
    mailbox.db.conn.execute('DELETE FROM email_mailbox_records WHERE tenant_key=? AND message_key=?',
                            ('studio-a', 'midnight'))
    SQLFactory.commit(mailbox.db)
    assert mailbox.retry_query_index_events(limit=1) == {'delivered': 1, 'failed': 0}
    assert 'midnight' not in {row['id'] for row in mailbox.query_records()['rows']}
    assert mailbox.retry_query_index_events(limit=1) == {'delivered': 0, 'failed': 0}


def test_errore_consegna_finito_non_nasconde_proiezione_incompleta(mailbox):
    mailbox.db.conn.execute('DELETE FROM email_mailbox_query_index WHERE tenant_key=? AND message_key=?',
                            ('studio-a', 'midnight'))
    SQLFactory.commit(mailbox.db)
    with patch('pct.email_mailbox_repository.upsert_projection', side_effect=RuntimeError('errore controllato')):
        for _attempt in range(5):
            result = mailbox.retry_query_index_events(limit=1)
            assert result == {'delivered': 0, 'failed': 1}
            assert mailbox.retry_query_index_events(limit=1) == {'delivered': 0, 'failed': 0}
            mailbox.db.conn.execute("UPDATE transactional_outbox SET available_at='2000-01-01T00:00:00+00:00' "
                                    "WHERE tenant_id='studio-a' AND status='PENDING'")
            SQLFactory.commit(mailbox.db)
    with pytest.raises(MailboxQueryIndexNotReady):
        mailbox.query_records()
    failed = mailbox.db.conn.execute("SELECT attempts FROM transactional_outbox WHERE tenant_id='studio-a' AND status='FAILED'").fetchall()
    assert [row[0] for row in failed] == [5]


def test_migrazione_non_puo_saltare_righe_o_cambiare_prova_di_backup(mailbox):
    migration = mailbox.begin_query_index_migration(backup_reference='controlled-resume', backup_sha256='b' * 64,
                                                   actor_key='controlled-migration')
    with pytest.raises(MailboxQueryIndexNotReady):
        mailbox.query_records()
    with pytest.raises(MailboxConflict):
        mailbox.rebuild_query_index_batch(migration_id=migration['id'], after_key='zzzz-skipped', actor_key='controlled-migration')
    first = mailbox.rebuild_query_index_batch(migration_id=migration['id'], actor_key='controlled-migration', limit=2)
    resumed = mailbox.begin_query_index_migration(backup_reference='controlled-resume', backup_sha256='b' * 64,
                                                 actor_key='controlled-migration')
    assert resumed['id'] == migration['id']
    assert resumed['after_key'] == first['after_key']
    with pytest.raises(MailboxConflict):
        mailbox.begin_query_index_migration(backup_reference='controlled-resume', backup_sha256='c' * 64,
                                            actor_key='controlled-migration')
    with pytest.raises(MailboxConflict):
        mailbox.rebuild_query_index_batch(migration_id=migration['id'], after_key=first['after_key'], actor_key='different-actor')
    state = mailbox.db.conn.execute('SELECT processed_count FROM email_mailbox_query_migrations WHERE id=?',
                                   (migration['id'],)).fetchone()
    assert state[0] == 2


def test_ora_legale_e_provenienza_incerte_non_inventate():
    first = projected_fields({'data': '2026-10-25T02:30:00+02:00', 'cartella': 'CESTINO'})
    second = projected_fields({'data': '2026-10-25T02:30:00+01:00', 'cartella': 'CESTINO'})
    assert first[0] != second[0]
    assert first[1] == second[1] == 'unknown'
    imported = projected_fields({'ricevuta_il': '2026-10-14T10:00:00+02:00', 'origine': 'IMPORT', 'cartella': 'INBOX'})
    assert imported[0] == ''
