"""Preparazione esplicita e riprendibile delle ricevute, senza rilettura MIME."""
import re
import uuid
from datetime import UTC, datetime

DDL = (
    '''CREATE TABLE IF NOT EXISTS pec_deposit_query_migrations (
        id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,backup_reference TEXT NOT NULL,
        backup_sha256 TEXT NOT NULL,actor_key TEXT NOT NULL,after_key TEXT NOT NULL DEFAULT '',
        phase TEXT NOT NULL,processed_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        UNIQUE(tenant_id,backup_reference))''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS idx_pec_deposit_query_migration_active
        ON pec_deposit_query_migrations(tenant_id) WHERE phase='BACKFILL' ''',
)


def prepare_empty_catalog(path, *, tenant, backup_dir):
    """Provisioning governato: solo archivio nuovo o ancora privo di messaggi."""
    import sqlite3
    from pathlib import Path
    from types import SimpleNamespace

    from pct.pec_deposit_query_repository import install_deposit_query_events
    from pct.pec_pipeline import PecAuditRepository
    from scripts.query_index_backup import verified_backup

    source = Path(path).resolve()
    if not tenant:
        raise ValueError('Studio delle ricevute non determinato.')
    if source.is_file():
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as read:
            exists = read.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pec_messages'").fetchone()
            if not exists or read.execute('SELECT 1 FROM pec_messages LIMIT 1').fetchone():
                return False  # Fonti preesistenti: preparazione esplicita a lotti.
    repository = PecAuditRepository(source, tenant_id=tenant)
    with repository.connect() as conn:
        verified_backup(SimpleNamespace(conn=conn, db_path=source, backend_kind='sqlite'), backup_dir)
        install_deposit_query_events(conn)
        conn.execute('INSERT INTO pec_deposit_query_bootstrap(tenant_id,version) VALUES (?,1) '
                     'ON CONFLICT(tenant_id) DO NOTHING', (tenant,))
    return True


def begin(conn, *, tenant, backup_reference, backup_sha256, actor):
    if not tenant or not actor or not backup_reference or not re.fullmatch('[0-9a-f]{64}', backup_sha256):
        raise ValueError('Studio, autore e backup verificato sono obbligatori.')
    for statement in DDL:
        conn.execute(statement)
    previous = conn.execute('SELECT id,backup_sha256,actor_key,phase,after_key FROM pec_deposit_query_migrations '
                            'WHERE tenant_id=? AND backup_reference=?', (tenant, backup_reference)).fetchone()
    if previous:
        if previous[1] != backup_sha256 or previous[2] != actor:
            raise ValueError('Backup o autore della ripresa discordante.')
        return dict(id=previous[0], phase=previous[3], after_key=previous[4])
    key, now = uuid.uuid4().hex, datetime.now(UTC).isoformat()
    conn.execute('INSERT INTO pec_deposit_query_migrations '
                 '(id,tenant_id,backup_reference,backup_sha256,actor_key,phase,created_at,updated_at) '
                 "VALUES (?,?,?,?,?,'BACKFILL',?,?)", (key, tenant, backup_reference, backup_sha256, actor, now, now))
    conn.execute('INSERT INTO pec_deposit_query_bootstrap(tenant_id,version) VALUES (?,0) '
                 'ON CONFLICT(tenant_id) DO UPDATE SET version=0', (tenant,))
    return dict(id=key, phase='BACKFILL', after_key='')


def rebuild_batch(conn, repository, *, migration_id, after_key, actor, limit=100):
    if not actor or type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('Autore e budget finito sono obbligatori.')
    now = datetime.now(UTC).isoformat()
    locked = conn.execute('UPDATE pec_deposit_query_migrations SET updated_at=? '
                          "WHERE id=? AND tenant_id=? AND phase='BACKFILL' AND after_key=? AND actor_key=? RETURNING id",
                          (now, migration_id, repository.tenant, after_key, actor)).fetchone()
    if locked is None:
        raise ValueError('Cursore o autore non coincide con il lotto confermato.')
    rows = conn.execute('SELECT id FROM pec_messages WHERE tenant_id=? AND id>? '
                         'AND EXISTS (SELECT 1 FROM pec_validation_reports r WHERE r.message_id=pec_messages.id) '
                         'ORDER BY id LIMIT ?', (repository.tenant, after_key, limit)).fetchall()
    for row in rows:
        key = row[0]
        current = conn.execute('UPDATE pec_messages SET id=id WHERE tenant_id=? AND id=? RETURNING id',
                               (repository.tenant, key)).fetchone()
        if current is None:
            raise ValueError('Fonte cambiata durante il lotto: ripetizione necessaria.')
        repository.project_message(conn, key)
        # Non consumare eventi concorrenti: il worker li riesamina puntualmente.
    cursor = rows[-1][0] if rows else after_key
    phase = 'BACKFILL' if rows else 'COMPLETED'
    conn.execute('UPDATE pec_deposit_query_migrations SET after_key=?,processed_count=processed_count+?,phase=?,updated_at=? WHERE id=?',
                 (cursor, len(rows), phase, now, migration_id))
    if not rows:
        conn.execute('UPDATE pec_deposit_query_bootstrap SET version=1 WHERE tenant_id=?', (repository.tenant,))
    return dict(id=migration_id, phase=phase, after_key=cursor, processed=len(rows))
