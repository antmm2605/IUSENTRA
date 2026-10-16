"""Preparazione riprendibile del catalogo, fuori dalle richieste consultive."""
import re
import uuid
from datetime import UTC, datetime

from pct.fascicoli_list_query import VERSION


def prepare_empty_catalog(database, *, tenant, registry_path, backup_dir):
    """Provisioning di un nuovo studio: nessuna scansione o richiesta web."""
    from pathlib import Path
    from contextlib import ExitStack
    import os
    from types import SimpleNamespace
    from pct.fascicoli_list_query import install_schema, install_source_events, install_registry_events
    from pct.registro_letture import RegistroLetture
    from scripts.query_index_backup import verified_backup

    # Uno studio con pratiche richiede la migrazione esplicita a lotti.
    if database.conn.execute('SELECT 1 FROM fascicoli LIMIT 1').fetchone() is not None:
        return False
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    registry = RegistroLetture(registry_path,
        postgres_dsn=os.environ.get('IUSENTRA_REGISTRO_LETTURE_DSN') or getattr(database, 'dsn', ''))
    try:
        verified_backup(database, Path(backup_dir) / 'core')
        with ExitStack() as stack:
            source = registry.connection()
            if callable(getattr(source, 'close', None)):
                stack.callback(source.close)
            with source:
                verified_backup(SimpleNamespace(conn=source, db_path=registry.db_path, dsn=registry.postgres_dsn,
                    backend_kind='postgresql' if registry.backend_kind == 'postgres' else 'sqlite'),
                                Path(backup_dir) / 'registro')
                install_registry_events(source, tenant=tenant, postgres=registry.backend_kind == 'postgres')
        install_schema(database.conn, postgres=postgres)
        install_source_events(database.conn, postgres=postgres)
        database.conn.execute('INSERT INTO fascicoli_list_owner(singleton,tenant_key,version) VALUES (1,?,?) '
            'ON CONFLICT(singleton) DO NOTHING', (tenant, VERSION))
        owner = database.conn.execute('SELECT tenant_key,version FROM fascicoli_list_owner WHERE singleton=1').fetchone()
        if owner[0] != tenant or owner[1] != VERSION:
            raise ValueError('Proprietario del catalogo vuoto non confermato.')
        from datetime import date
        from pct.fascicoli_list_clock import initialize_clock
        initialize_clock(database.conn, tenant, date.today().isoformat())
        (getattr(database, 'raw_conn', None) or database.conn).commit()
        return True
    finally:
        registry.close()


def install_migration_schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS fascicoli_list_migrations ('
        'id TEXT PRIMARY KEY,tenant_key TEXT NOT NULL,backup_reference TEXT NOT NULL,'
        'backup_sha256 TEXT NOT NULL,actor_key TEXT NOT NULL,phase TEXT NOT NULL,'
        "after_key TEXT NOT NULL DEFAULT '',processed_count INTEGER NOT NULL DEFAULT 0,"
        'created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(tenant_key,backup_reference))')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_fascicoli_list_migration_active '
        "ON fascicoli_list_migrations(tenant_key) WHERE phase IN ('IDENTITIES','DEADLINES','ROWS')")


def begin(conn, *, tenant, backup_reference, backup_sha256, actor):
    from datetime import date
    from pct.fascicoli_list_clock import initialize_clock
    if not tenant or not backup_reference or not actor or not re.fullmatch('[0-9a-f]{64}', backup_sha256):
        raise ValueError('Studio, backup verificato e autore sono obbligatori.')
    conn.execute('INSERT INTO fascicoli_list_owner(singleton,tenant_key,version) VALUES (1,?,0) '
                 'ON CONFLICT(singleton) DO NOTHING', (tenant,))
    owner = conn.execute('SELECT tenant_key FROM fascicoli_list_owner WHERE singleton=1').fetchone()
    if owner[0] != tenant:
        raise ValueError('Catalogo attribuito a un altro studio.')
    initialize_clock(conn, tenant, date.today().isoformat())
    previous = conn.execute('SELECT id,backup_sha256,actor_key,phase,after_key FROM fascicoli_list_migrations '
        'WHERE tenant_key=? AND backup_reference=?', (tenant, backup_reference)).fetchone()
    if previous:
        if previous[1] != backup_sha256 or previous[2] != actor:
            raise ValueError('Backup o autore della ripresa discordante.')
        return dict(id=previous[0], phase=previous[3], after_key=previous[4])
    key, now = uuid.uuid4().hex, datetime.now(UTC).isoformat()
    conn.execute('INSERT INTO fascicoli_list_migrations '
        '(id,tenant_key,backup_reference,backup_sha256,actor_key,phase,created_at,updated_at) '
        "VALUES (?,?,?,?,?,'IDENTITIES',?,?)", (key, tenant, backup_reference, backup_sha256, actor, now, now))
    conn.execute('UPDATE fascicoli_list_owner SET version=0 WHERE singleton=1 AND tenant_key=?', (tenant,))
    return dict(id=key, phase='IDENTITIES', after_key='')


def rebuild_batch(conn, *, tenant, migration_id, actor, phase, after_key, project, limit=100):
    """Il callback usa i resolver nativi solo sulle chiavi SQL del lotto."""
    if phase not in {'IDENTITIES', 'DEADLINES', 'ROWS'} or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Fase o dimensione del lotto non valida.')
    now = datetime.now(UTC).isoformat()
    lock = conn.execute('UPDATE fascicoli_list_migrations SET updated_at=? WHERE id=? AND tenant_key=? '
        'AND actor_key=? AND phase=? AND after_key=? RETURNING id',
        (now, migration_id, tenant, actor, phase, after_key)).fetchone()
    if lock is None:
        raise ValueError('Cursore, fase o autore non coincide con il lotto confermato.')
    source_table = 'scadenze' if phase == 'DEADLINES' else 'fascicoli'
    rows = conn.execute('SELECT id FROM ' + source_table + ' WHERE id>? ORDER BY id LIMIT ?', (after_key, limit)).fetchall()
    keys = [str(row[0]) for row in rows]
    if keys:
        project(conn, keys, phase=phase)
    cursor = keys[-1] if keys else after_key
    next_phase = phase if keys else {'IDENTITIES': 'DEADLINES', 'DEADLINES': 'ROWS', 'ROWS': 'COMPLETED'}[phase]
    if next_phase != phase:
        cursor = ''
    conn.execute('UPDATE fascicoli_list_migrations SET after_key=?,processed_count=processed_count+?,phase=?,updated_at=? '
        'WHERE id=? AND tenant_key=?', (cursor, len(keys), next_phase, now, migration_id, tenant))
    if next_phase == 'COMPLETED':
        source_count = int(conn.execute('SELECT COUNT(*) FROM fascicoli').fetchone()[0])
        indexed_count = int(conn.execute('SELECT COUNT(*) FROM fascicoli_list_rows WHERE tenant_key=?', (tenant,)).fetchone()[0])
        if source_count != indexed_count:
            raise ValueError('Il catalogo non rappresenta tutte le fonti: preparazione non confermata.')
        missing = conn.execute('SELECT 1 FROM fascicoli f WHERE NOT EXISTS '
            '(SELECT 1 FROM fascicoli_list_rows r WHERE r.tenant_key=? AND r.record_key=f.id) LIMIT 1', (tenant,)).fetchone()
        obsolete = conn.execute('SELECT 1 FROM fascicoli_list_rows r WHERE r.tenant_key=? AND NOT EXISTS '
            '(SELECT 1 FROM fascicoli f WHERE f.id=r.record_key) LIMIT 1', (tenant,)).fetchone()
        if missing is not None or obsolete is not None:
            raise ValueError('Identità delle righe del catalogo non allineate alle fonti SQL.')
        conn.execute('UPDATE fascicoli_list_owner SET version=? WHERE singleton=1 AND tenant_key=?', (VERSION, tenant))
    return dict(id=migration_id, phase=next_phase, after_key=cursor, processed=len(keys))
