"""Aggiorna solo metadati già migrati, nella transazione del salvataggio nativo."""
import logging
from datetime import UTC, datetime
from types import SimpleNamespace

from pct.calendar_query_projection import DOMAINS
from pct.calendar_query_repository import CalendarQueryRepository


def project_if_registered(conn, *, domain, keys):
    if domain not in DOMAINS or not keys:
        return
    postgres = hasattr(conn, '_backend')
    exists = ("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='calendar_query_owner'"
              if postgres else "SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_query_owner'")
    if conn.execute(exists).fetchone() is None:
        return
    conn.execute('SAVEPOINT calendar_query_projection_write')
    try:
        owner = conn.execute('SELECT tenant_key FROM calendar_query_owner WHERE singleton=1').fetchone()
        if owner is None:
            conn.execute('RELEASE SAVEPOINT calendar_query_projection_write')
            return
        marker = conn.execute('SELECT version FROM calendar_query_bootstrap WHERE tenant_key=? AND domain=?', (owner[0], domain)).fetchone()
        if marker is None or marker[0] != 1:
            conn.execute('RELEASE SAVEPOINT calendar_query_projection_write')
            return
        repository = CalendarQueryRepository(SimpleNamespace(conn=conn), owner[0])
        sources = {}
        for offset in range(0, len(keys), 500):
            batch = keys[offset:offset + 500]
            rows = conn.execute('SELECT * FROM ' + DOMAINS[domain] + ' WHERE id IN (' + ','.join('?' for _ in batch) + ')', tuple(batch)).fetchall()
            sources.update((str(row['id']), row) for row in rows)
        for key in keys:
            repository.project_record(conn, domain=domain, key=key, row=sources.get(key))
            conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=? WHERE tenant_id=? "
                         "AND aggregate_type=? AND aggregate_id=? AND event_type='calendar_query.refresh_requested' "
                         "AND status IN ('PENDING','FAILED')",
                         (datetime.now(UTC).isoformat(), owner[0], 'calendar_query:' + domain, key))
        conn.execute('RELEASE SAVEPOINT calendar_query_projection_write')
    except Exception:
        conn.execute('ROLLBACK TO SAVEPOINT calendar_query_projection_write')
        conn.execute('RELEASE SAVEPOINT calendar_query_projection_write')
        logging.getLogger(__name__).exception('Indice calendario non confermato: evento persistente da recuperare.')
