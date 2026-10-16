"""Avanzamento del giorno sui soli termini indicizzati interessati."""
import uuid
from datetime import date, timedelta

from pct.operational_live import signal_domain_changed
from pct.transactional_outbox import OutboxEvent, enqueue


def install_clock_schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_clock ('
        'tenant_key TEXT PRIMARY KEY,event_day TEXT NOT NULL,target_day TEXT NOT NULL DEFAULT \'\','
        'after_key TEXT NOT NULL DEFAULT \'\')')


def initialize_clock(conn, tenant, day):
    value = date.fromisoformat(day).isoformat()
    conn.execute('INSERT INTO fascicoli_list_clock(tenant_key,event_day) VALUES (?,?) '
                 'ON CONFLICT(tenant_key) DO NOTHING', (tenant, value))


def clock_ready(conn, tenant):
    row = conn.execute('SELECT event_day FROM fascicoli_list_clock WHERE tenant_key=?', (tenant,)).fetchone()
    return row is not None and row[0] == date.today().isoformat()


def refresh_clock(conn, tenant, *, postgres=False, limit=100):
    """Lotto finito nella outbox condivisa; nessuna lettura delle pratiche."""
    from pct.fascicoli_list_query import AGGREGATE, EVENT_TYPE
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Lotto del cambio giorno non valido.')
    owner = conn.execute('SELECT tenant_key FROM fascicoli_list_owner WHERE singleton=1').fetchone()
    if owner is None or owner[0] != tenant:
        raise ValueError('Studio proprietario del cambio giorno non riscontrato.')
    if postgres:
        conn.execute('SELECT pg_advisory_xact_lock(hashtext(?),hashtext(?))', (tenant, 'fascicoli-list-clock'))
    row = conn.execute('SELECT event_day,target_day,after_key FROM fascicoli_list_clock WHERE tenant_key=?',
                       (tenant,)).fetchone()
    if row is None:
        raise ValueError('Giorno della proiezione non preparato.')
    current = date.today()
    previous = date.fromisoformat(row[0])
    if previous == current:
        return 0
    cursor = row[2] if row[1] == current.isoformat() else ''
    low = (min(current, previous) + timedelta(days=4)).isoformat()
    high = (max(current, previous) + timedelta(days=7)).isoformat()
    rows = conn.execute('SELECT record_key FROM fascicoli_list_deadlines WHERE tenant_key=? '
        'AND event_day>=? AND event_day<=? AND record_key>? ORDER BY record_key LIMIT ?',
        (tenant, low, high, cursor, limit)).fetchall()
    for value in rows:
        enqueue(conn, OutboxEvent(tenant_id=tenant, aggregate_type=AGGREGATE,
            aggregate_id='deadline:' + str(value[0]), aggregate_version=1, event_type=EVENT_TYPE,
            idempotency_key='fascicoli-clock:' + uuid.uuid4().hex, payload={}, actor_id='native-list-clock'))
    complete = len(rows) < limit
    confirmed = conn.execute('UPDATE fascicoli_list_clock SET event_day=?,target_day=?,after_key=? '
        'WHERE tenant_key=? AND event_day=? AND target_day=? AND after_key=? RETURNING tenant_key',
        (current.isoformat() if complete else previous.isoformat(), '' if complete else current.isoformat(),
         '' if complete else str(rows[-1][0]), tenant, row[0], row[1], row[2])).fetchone()
    if confirmed is None:
        raise RuntimeError('Cursore del cambio giorno aggiornato da una consegna concorrente: ripresa necessaria.')
    if complete:
        signal_domain_changed(conn, 'fascicoli')
    return len(rows)
