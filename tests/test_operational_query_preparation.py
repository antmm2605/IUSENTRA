import json
import sqlite3
import sys

import pytest

from pct.email_mailbox_repository import EmailMailboxRepository, MailboxNotInitialized
from tests.test_calendar_query_preparation import store as store
from tests.test_studio_readonly_request import studies as studies
from tools.prepare_operational_query_indexes import main, prepare_core


def test_riepilogo_pec_usa_indice_coprente_senza_modificare_fonti(tmp_path):
    from tools.prepare_operational_query_indexes import prepare_notifications

    path = tmp_path / 'pec_audit.sqlite'
    with sqlite3.connect(path) as conn:
        conn.execute('''CREATE TABLE pec_messages(
            id TEXT PRIMARY KEY, tenant_id TEXT, message_id_header TEXT,
            quality_status TEXT, signature_status TEXT, linked_fascicolo_id TEXT,
            linked_fascicolo_score REAL, received_at TEXT, mime_blob BLOB,
            account_email TEXT DEFAULT '', folder TEXT DEFAULT '', imap_uid TEXT DEFAULT '',
            mime_sha256 TEXT DEFAULT '', mime_size INTEGER DEFAULT 0, ingested_at TEXT DEFAULT '',
            status TEXT DEFAULT '', retention_policy_id TEXT DEFAULT '', retention_until TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}')''')
        conn.execute('CREATE INDEX idx_pec_messages_received ON pec_messages(tenant_id,received_at DESC)')
        conn.execute('INSERT INTO pec_messages(id,tenant_id,message_id_header,quality_status,signature_status,'
                     'linked_fascicolo_id,linked_fascicolo_score,received_at,mime_blob) VALUES(?,?,?,?,?,?,?,?,?)',
                     ('one', 'controlled-study', '<controlled>', 'ok', 'assente', 'case', 1.0,
                      '2026-10-14T08:00:00Z', b'controlled-source' * 1000))
        before = conn.execute('SELECT * FROM pec_messages').fetchall()
    assert prepare_notifications(path, tenant='controlled-study', destination=tmp_path / 'backup')
    query = '''SELECT id,message_id_header,quality_status,signature_status,linked_fascicolo_id,
        linked_fascicolo_score,received_at FROM pec_messages WHERE tenant_id=?
        AND message_id_header IN (?) ORDER BY received_at DESC'''
    with sqlite3.connect(path) as conn:
        plan = conn.execute('EXPLAIN QUERY PLAN ' + query, ('controlled-study', '<controlled>')).fetchall()
        assert any('COVERING INDEX idx_pec_messages_header_summary' in row[3] for row in plan)
        assert conn.execute(query, ('controlled-study', '<controlled>')).fetchone()[0] == 'one'
        assert conn.execute('SELECT * FROM pec_messages').fetchall() == before
        list_query = '''SELECT id,tenant_id,account_email,folder,imap_uid,message_id_header,
            mime_sha256,mime_size,received_at,ingested_at,status,quality_status,signature_status,
            linked_fascicolo_id,linked_fascicolo_score,retention_policy_id,retention_until,metadata_json
            FROM pec_messages WHERE tenant_id=? ORDER BY received_at DESC,id DESC LIMIT ? OFFSET ?'''
        list_plan = conn.execute('EXPLAIN QUERY PLAN ' + list_query, ('controlled-study', 200, 0)).fetchall()
        assert any('COVERING INDEX idx_pec_messages_list_summary' in row[3] for row in list_plan)
    assert not prepare_notifications(path, tenant='controlled-study', destination=tmp_path / 'backup')


def test_preparazione_repository_nativi_senza_modificare_messaggi(store, tmp_path, monkeypatch):
    for kind in ('pec', 'ordinary'):
        mailbox = EmailMailboxRepository(store, 'controlled-study', kind)
        mailbox.ensure_schema()
        mailbox.initialize({'one': {'id': 'one', 'cartella': 'INBOX', 'data': '2026-10-14T10:00:00'}}, source_of_truth=store.backend_kind)
    before = [tuple(row) for row in store.conn.execute('SELECT * FROM email_mailbox_records ORDER BY mailbox_kind,message_key').fetchall()]
    assert prepare_core(store, tenant='controlled-study', destination=tmp_path / 'backup') == ['agenda', 'deadlines']
    monkeypatch.setattr('tools.prepare_operational_query_indexes.verified_backup', lambda *a, **kw: pytest.fail('Backup non necessario'))
    monkeypatch.setattr('pct.calendar_query_preparation.verified_backup', lambda *a, **kw: pytest.fail('Backup non necessario'))
    assert prepare_core(store, tenant='controlled-study', destination=tmp_path / 'backup') == []
    assert [tuple(row) for row in store.conn.execute('SELECT * FROM email_mailbox_records ORDER BY mailbox_kind,message_key').fetchall()] == before


def test_comando_usa_tenant_e_percorsi_nativi_senza_avviare_web_pipeline_o_modelli(studies, tmp_path, monkeypatch, capsys):
    app, owners, databases, _ = studies
    for owner, database in zip(owners, databases, strict=True):
        EmailMailboxRepository(database, owner.slug, 'ordinary').initialize({}, source_of_truth='sqlite')
    monkeypatch.setattr('web.app.create_app', lambda *a, **kw: pytest.fail('Avvio applicativo non richiesto'))
    monkeypatch.setattr('pct.pec_pipeline.PecAuditRepository.__init__', lambda *a, **kw: pytest.fail('Pipeline PEC non richiesta'))
    monkeypatch.setattr(sys, 'argv', ['prepare-query-indexes', '--tenant-registry', app.config['TENANTS_REGISTRY'], '--backup-dir', str(tmp_path / 'backup')])
    main()
    first = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {row['tenant'] for row in first} == {owner.slug for owner in owners}
    assert all(row['changed'] == ['agenda', 'deadlines'] and row['notifications_changed'] for row in first)
    main()
    second = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert all(row['changed'] == [] and not row['notifications_changed'] for row in second)
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--tenant', 'missing-controlled-study'])
    with pytest.raises(ValueError, match='Studio richiesto non disponibile'):
        main()


def test_catalogo_posta_non_provisionato_non_diventa_casella_vuota(store, tmp_path):
    mailbox = EmailMailboxRepository(store, 'controlled-study', 'pec')
    mailbox.ensure_schema()
    with pytest.raises(MailboxNotInitialized):
        prepare_core(store, tenant='controlled-study', destination=tmp_path / 'must-not-exist')
    assert not (tmp_path / 'must-not-exist').exists()


def test_provisione_casella_vuota_verificata_sui_due_backend(store, tmp_path):
    from web.services.email_storage_runtime import prepare_empty_sql_mailboxes

    paths = {'EMAIL_CASELLA_DB': str(tmp_path / 'casella.json'), 'EMAIL_ORDINARIA_DB': str(tmp_path / 'ordinaria.json')}
    status = prepare_empty_sql_mailboxes(store, 'controlled-study', paths, store.backend_kind)
    assert set(status.values()) == {'verified_empty_initialized'}
    for kind in ('pec', 'ordinary'):
        assert EmailMailboxRepository(store, 'controlled-study', kind).query_records()['rows'] == []
    assert set(prepare_empty_sql_mailboxes(store, 'controlled-study', paths, store.backend_kind).values()) == {'already_initialized'}


def test_provisione_non_sostituisce_fonti_storiche_con_vuoto(store, tmp_path):
    from web.services.email_storage_runtime import prepare_empty_sql_mailboxes

    path = tmp_path / 'casella.json'
    path.write_text(json.dumps({'old': {'id': 'old', 'oggetto': 'Fonte storica controllata'}}), encoding='utf-8')
    before = path.read_bytes()
    status = prepare_empty_sql_mailboxes(store, 'controlled-study',
        {'EMAIL_CASELLA_DB': str(path), 'EMAIL_ORDINARIA_DB': str(tmp_path / 'ordinary.json')}, store.backend_kind)
    assert status['pec'] == 'verified_migration_required'
    assert path.read_bytes() == before
    with pytest.raises(MailboxNotInitialized):
        EmailMailboxRepository(store, 'controlled-study', 'pec').query_records()
