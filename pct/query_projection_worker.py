"""Consegna finita per proiezioni nella outbox esistente, senza seconda coda."""
from datetime import UTC, datetime, timedelta
import sqlite3
import time


def deliver_pending(*, conn, finish, tenant, aggregate, event_type, project, limit=50,
                    aggregate_id=None, failure_message='Proiezione consultiva non confermata: recupero necessario.',
                    prepare=None, tempo_massimo=None):
    """Consegna gli eventi in attesa, uno per transazione.

    ``prepare(conn, key)``, se c'è, fa le letture della proiezione prima di prenotare l'evento, fuori dalla
    transazione di scrittura; ``project(conn, key, preparato)`` scrive soltanto. Verifica del 24/11/2026 sull'8080:
    con le letture dentro la prenotazione il registro delle letture restava bloccato in scrittura per decine di minuti.
    ``tempo_massimo`` (secondi) ferma il giro prima di prenotare un altro evento: il resto va al giro dopo.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Lotto della proiezione non valido.')
    now = datetime.now(UTC).isoformat()
    if aggregate_id is not None and (not isinstance(aggregate_id, str) or not aggregate_id):
        raise ValueError('Riferimento della consegna non valido.')
    targeted = ' AND aggregate_id=? ' if aggregate_id is not None else ''
    parameters = (tenant, aggregate, event_type, now, *((aggregate_id,) if aggregate_id is not None else ()), limit)
    events = conn.execute('SELECT id,aggregate_id FROM transactional_outbox '
                          'WHERE tenant_id=? AND aggregate_type=? AND event_type=? '
                          "AND status='PENDING' AND available_at<=? AND attempts<5 "
                          + targeted + 'ORDER BY available_at,id LIMIT ?', parameters).fetchall()
    finish(conn)
    delivered = failed = 0
    scadenza = None if tempo_massimo is None else time.monotonic() + float(tempo_massimo)
    for event in events:
        if scadenza is not None and time.monotonic() >= scadenza:
            break
        event_id, key = event[0], event[1]
        try:
            if prepare is not None:
                preparato = prepare(conn, key)
                finish(conn)
            claimed = conn.execute('UPDATE transactional_outbox SET attempts=attempts+1 '
                                   "WHERE id=? AND tenant_id=? AND aggregate_type=? AND event_type=? "
                                   "AND status='PENDING' AND available_at<=? AND attempts<5 RETURNING id",
                                   (event_id, tenant, aggregate, event_type, now)).fetchone()
            if claimed is None:
                finish(conn)
                continue
            if prepare is not None:
                project(conn, key, preparato)
            else:
                project(conn, key)
            conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=? "
                         "WHERE id=? AND tenant_id=? AND status='PENDING'",
                         (datetime.now(UTC).isoformat(), event_id, tenant))
            finish(conn)
            delivered += 1
        except Exception as exc:
            finish(conn, rollback=True)
            if isinstance(exc, sqlite3.OperationalError) and (
                getattr(exc, 'sqlite_errorcode', 0) & 0xff
            ) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                # Il prossimo giro recupera la consegna con lo stesso budget.
                failed += 1
                break
            failed += 1
            retry_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
            conn.execute('UPDATE transactional_outbox SET attempts=attempts+1,available_at=?, '
                         "status=CASE WHEN attempts+1>=5 THEN 'FAILED' ELSE 'PENDING' END,last_error=? "
                         "WHERE id=? AND tenant_id=? AND aggregate_type=? AND event_type=? AND status='PENDING'",
                         (retry_at, failure_message(exc) if callable(failure_message) else failure_message, event_id,
                          tenant, aggregate, event_type))
            finish(conn)
    return dict(delivered=delivered, failed=failed)
