"""Consegna finita per proiezioni nella outbox esistente, senza seconda coda."""
from datetime import UTC, datetime, timedelta


def deliver_pending(*, conn, finish, tenant, aggregate, event_type, project, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Lotto della proiezione non valido.')
    now = datetime.now(UTC).isoformat()
    events = conn.execute('SELECT id,aggregate_id FROM transactional_outbox '
                          'WHERE tenant_id=? AND aggregate_type=? AND event_type=? '
                          "AND status='PENDING' AND available_at<=? AND attempts<5 "
                          'ORDER BY available_at,id LIMIT ?', (tenant, aggregate, event_type, now, limit)).fetchall()
    finish(conn)
    delivered = failed = 0
    for event in events:
        event_id, key = event[0], event[1]
        try:
            claimed = conn.execute('UPDATE transactional_outbox SET attempts=attempts+1 '
                                   "WHERE id=? AND tenant_id=? AND aggregate_type=? AND event_type=? "
                                   "AND status='PENDING' AND available_at<=? AND attempts<5 RETURNING id",
                                   (event_id, tenant, aggregate, event_type, now)).fetchone()
            if claimed is None:
                finish(conn)
                continue
            project(conn, key)
            conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=? "
                         "WHERE id=? AND tenant_id=? AND status='PENDING'",
                         (datetime.now(UTC).isoformat(), event_id, tenant))
            finish(conn)
            delivered += 1
        except Exception:
            finish(conn, rollback=True)
            failed += 1
            retry_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            conn.execute('UPDATE transactional_outbox SET attempts=attempts+1,available_at=?, '
                         "status=CASE WHEN attempts+1>=5 THEN 'FAILED' ELSE 'PENDING' END,last_error=? "
                         "WHERE id=? AND tenant_id=? AND aggregate_type=? AND event_type=? AND status='PENDING'",
                         (retry_at, 'Proiezione consultiva non confermata: recupero necessario.', event_id,
                          tenant, aggregate, event_type))
            finish(conn)
    return dict(delivered=delivered, failed=failed)
