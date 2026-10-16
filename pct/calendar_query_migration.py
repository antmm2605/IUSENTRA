"""Lotti espliciti del catalogo: transazione e backup restano del chiamante."""
import re
import uuid
from datetime import UTC, datetime

from pct.calendar_query_projection import DOMAINS


def begin(conn, *, tenant, domain, backup_reference, backup_sha256, actor):
    if domain not in DOMAINS or not tenant or not actor or not backup_reference or not re.fullmatch('[0-9a-f]{64}', backup_sha256):
        raise ValueError('Studio, dominio, backup verificato e autore sono obbligatori.')
    conn.execute('INSERT INTO calendar_query_owner(singleton,tenant_key,version) VALUES (1,?,1) '
                 'ON CONFLICT(singleton) DO NOTHING', (tenant,))
    owner = conn.execute('SELECT tenant_key FROM calendar_query_owner WHERE singleton=1').fetchone()
    if owner[0] != tenant:
        raise ValueError('Database calendario attribuito a un altro studio.')
    previous = conn.execute('SELECT id,backup_sha256,actor_key,phase,after_key FROM calendar_query_migrations '
                            'WHERE tenant_key=? AND domain=? AND backup_reference=?', (tenant, domain, backup_reference)).fetchone()
    if previous:
        if previous[1] != backup_sha256 or previous[2] != actor:
            raise ValueError('Backup o autore della ripresa discordante.')
        return dict(id=previous[0], phase=previous[3], after_key=previous[4])
    key, now = uuid.uuid4().hex, datetime.now(UTC).isoformat()
    conn.execute('INSERT INTO calendar_query_migrations '
                 '(id,tenant_key,domain,backup_reference,backup_sha256,actor_key,phase,created_at,updated_at) '
                 "VALUES (?,?,?,?,?,?,'BACKFILL',?,?)", (key, tenant, domain, backup_reference, backup_sha256, actor, now, now))
    conn.execute('INSERT INTO calendar_query_bootstrap(tenant_key,domain,version) VALUES (?,?,0) '
                 'ON CONFLICT(tenant_key,domain) DO UPDATE SET version=0', (tenant, domain))
    return dict(id=key, phase='BACKFILL', after_key='')


def rebuild_batch(conn, repository, *, domain, migration_id, after_key, actor, limit=100):
    if domain not in DOMAINS or not actor:
        raise ValueError('Dominio o autore della migrazione non valido.')
    now = datetime.now(UTC).isoformat()
    locked = conn.execute('UPDATE calendar_query_migrations SET updated_at=? '
                          "WHERE id=? AND tenant_key=? AND domain=? AND phase='BACKFILL' AND after_key=? AND actor_key=? RETURNING id",
                          (now, migration_id, repository.tenant, domain, after_key, actor)).fetchone()
    if locked is None:
        raise ValueError('Cursore o autore non coincide con il lotto confermato.')
    table = DOMAINS[domain]
    rows = conn.execute(f'SELECT id FROM {table} WHERE id>? ORDER BY id LIMIT ?',
                         (after_key, max(1, min(int(limit), 500)))).fetchall()
    for row in rows:
        key = row[0]
        # Il lock mantiene immutata la fonte fino alla conferma della proiezione.
        current = conn.execute(f'UPDATE {table} SET id=id WHERE id=? RETURNING *', (key,)).fetchone()
        if current is None:
            raise ValueError('Fonte cambiata durante il lotto: ripetizione necessaria.')
        repository.project_record(conn, domain=domain, key=key, row=current)
        conn.execute("UPDATE transactional_outbox SET status='PROCESSED',processed_at=? "
                     "WHERE tenant_id=? AND aggregate_type=? AND aggregate_id=? AND event_type='calendar_query.refresh_requested' "
                     "AND status IN ('PENDING','FAILED')", (now, repository.tenant, 'calendar_query:' + domain, key))
    cursor = rows[-1][0] if rows else after_key
    phase = 'BACKFILL' if rows else 'COMPLETED'
    conn.execute('UPDATE calendar_query_migrations SET after_key=?,processed_count=processed_count+?,phase=?,updated_at=? WHERE id=?',
                 (cursor, len(rows), phase, now, migration_id))
    if not rows:
        conn.execute('INSERT INTO calendar_query_bootstrap(tenant_key,domain,version) VALUES (?,?,1) '
                     'ON CONFLICT(tenant_key,domain) DO UPDATE SET version=1', (repository.tenant, domain))
    return dict(id=migration_id, phase=phase, after_key=cursor, processed=len(rows))
