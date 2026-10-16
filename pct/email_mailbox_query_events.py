"""Invalidazione puntuale delle proiezioni tramite l'outbox SQL già esistente.

I trigger non leggono documenti e non avviano invii. La consegna della
proiezione partecipa alla transazione della mutazione nativa della casella.
"""
from __future__ import annotations

from datetime import UTC, datetime

from pct.query_projection_outbox import install_source_trigger
from pct.transactional_outbox import POSTGRES_SCHEMA

EVENT_TYPE = 'mailbox_query.refresh_requested'
AGGREGATE_PREFIX = 'mailbox_query:'


def install_query_events(conn, *, postgres=False):
    required = {'email_mailbox_records', 'email_mailbox_query_index'}
    if postgres:
        tables = conn.execute('SELECT table_name FROM information_schema.tables '
                              'WHERE table_schema=current_schema() AND table_name IN (?,?)', tuple(sorted(required))).fetchall()
    else:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN (?,?)", tuple(sorted(required))).fetchall()
    if {row[0] for row in tables} != required:
        return
    if postgres:
        conn.execute('SELECT pg_advisory_xact_lock(hashtext(current_schema()), 1158035850)')
    conn.execute('CREATE TABLE IF NOT EXISTS email_mailbox_query_schema '
                 '(singleton INTEGER PRIMARY KEY,version INTEGER NOT NULL)')
    installed = conn.execute('SELECT version FROM email_mailbox_query_schema WHERE singleton=1').fetchone()
    if installed is not None and installed[0] == 1:
        return
    # execute, non executescript: nessun commit implicito della transazione.
    for statement in POSTGRES_SCHEMA.split(';'):
        if statement.strip():
            conn.execute(statement)
    conn.execute('CREATE INDEX IF NOT EXISTS idx_outbox_mailbox_query_pending '
                 'ON transactional_outbox(tenant_id,aggregate_type,event_type,status,aggregate_id)')
    conn.execute('CREATE TABLE IF NOT EXISTS email_mailbox_query_bootstrap ('
                 'tenant_key TEXT NOT NULL,mailbox_kind TEXT NOT NULL,version INTEGER NOT NULL,'
                 'PRIMARY KEY(tenant_key,mailbox_kind))')
    for table, actions in (('email_mailbox_records', ('INSERT', 'UPDATE', 'DELETE')),
                           ('email_mailbox_query_index', ('DELETE',))):
        for action in actions:
            name = f'iusentra_query_{table}_{action.lower()}'
            unchanged = ("OLD.payload_json = NEW.payload_json AND OLD.folder = NEW.folder "
                         "AND OLD.read_state = NEW.read_state AND OLD.message_date = NEW.message_date")
            predicate = f'NOT ({unchanged})' if action == 'UPDATE' else '1=1'
            if table == 'email_mailbox_query_index':
                predicate = ('EXISTS (SELECT 1 FROM email_mailbox_records r WHERE '
                             'r.tenant_key={row}.tenant_key AND r.mailbox_kind={row}.mailbox_kind '
                             'AND r.message_key={row}.message_key)')
            install_source_trigger(conn, table=table, action=action, name=name,
                                   tenant_sql='{row}.tenant_key', aggregate_sql=f"'{AGGREGATE_PREFIX}' || {{row}}.mailbox_kind",
                                   key_sql='{row}.message_key', event_type=EVENT_TYPE,
                                   predicate=predicate, postgres=postgres)
    conn.execute('INSERT INTO email_mailbox_query_schema(singleton,version) VALUES (1,1) '
                 'ON CONFLICT(singleton) DO UPDATE SET version=excluded.version')


def acknowledge_projection(conn, tenant, kind, key):
    """Solo dopo la persistenza della proiezione nella stessa transazione."""
    conn.execute("UPDATE transactional_outbox SET status='PROCESSED',"
                 'processed_at=? '
                 "WHERE tenant_id=? AND aggregate_type=? AND aggregate_id=? AND event_type=? AND status IN ('PENDING','FAILED')",
                 (datetime.now(UTC).isoformat(),
                  tenant, AGGREGATE_PREFIX + kind, key, EVENT_TYPE))


def mark_bootstrapped(conn, tenant, kind):
    conn.execute('INSERT INTO email_mailbox_query_bootstrap(tenant_key,mailbox_kind,version) '
                 'VALUES (?,?,1) ON CONFLICT(tenant_key,mailbox_kind) DO UPDATE SET version=excluded.version',
                 (tenant, kind))


def projection_ready(conn, tenant, kind):
    marker = conn.execute('SELECT version FROM email_mailbox_query_bootstrap '
                          'WHERE tenant_key=? AND mailbox_kind=?', (tenant, kind)).fetchone()
    if marker is None or marker[0] != 1:
        return False
    return conn.execute('SELECT 1 FROM transactional_outbox WHERE tenant_id=? AND aggregate_type=? '
                        "AND event_type=? AND status IN ('PENDING','FAILED') LIMIT 1",
                        (tenant, AGGREGATE_PREFIX + kind, EVENT_TYPE)).fetchone() is None
