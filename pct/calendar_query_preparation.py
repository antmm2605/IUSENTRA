"""Preparazione esplicita del calendario alla creazione/attivazione dello studio."""
from pct.calendar_query_migration import begin, rebuild_batch
from pct.calendar_query_repository import CalendarQueryRepository
from pct.calendar_query_schema import install_calendar_query_events
from scripts.query_index_backup import verified_backup


def rebuild(database, *, tenant, destination, domain, limit=100, max_batches=100):
    if domain not in {'agenda', 'deadlines'} or not tenant or type(max_batches) is not int or not 1 <= max_batches <= 1000:
        raise ValueError('Studio, dominio e budget finito sono obbligatori.')
    snapshot, digest = verified_backup(database, destination)
    writable = getattr(database, '_conn_per_scrittura', None)
    conn = writable() if callable(writable) else database.conn
    target = getattr(database, 'raw_conn', None) or conn
    repository = CalendarQueryRepository(database, tenant)
    try:
        install_calendar_query_events(conn, postgres=getattr(database, 'backend_kind', '') == 'postgresql')
        state = begin(conn, tenant=tenant, domain=domain, backup_reference=str(snapshot), backup_sha256=digest,
                      actor='calendar-query-migration')
        target.commit()
        processed = 0
        for _ in range(max_batches):
            if state['phase'] == 'COMPLETED':
                break
            state = rebuild_batch(conn, repository, domain=domain, migration_id=state['id'],
                                  after_key=state['after_key'], actor='calendar-query-migration', limit=limit)
            target.commit()
            processed += state['processed']
        return dict(migration_id=state['id'], phase=state['phase'], processed_this_run=processed, backup_sha256=digest)
    except Exception:
        target.rollback()
        raise


def prepare_calendar_query_catalog(database, *, tenant, backup_dir):
    from pathlib import Path

    conn = database.conn
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    exists = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='calendar_query_owner'"
                          if postgres else "SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_query_owner'").fetchone()
    ready = set()
    if exists:
        owner = conn.execute('SELECT tenant_key,version FROM calendar_query_owner WHERE singleton=1').fetchone()
        if owner is not None and (owner[0] != tenant or owner[1] != 1):
            raise ValueError('Catalogo calendario attribuito a un altro studio o revisione non supportata.')
        if owner is not None:
            ready = {row[0] for row in conn.execute('SELECT domain FROM calendar_query_bootstrap WHERE tenant_key=? AND version=1', (tenant,)).fetchall()}
    if ready == {'agenda', 'deadlines'}:
        return False
    for domain in ('agenda', 'deadlines'):
        if domain in ready:
            continue
        result = rebuild(database, tenant=tenant, destination=Path(backup_dir) / domain, domain=domain)
        if result['phase'] != 'COMPLETED':
            raise RuntimeError('Preparazione calendario non terminata: riprendere il lotto registrato prima di attivare lo studio.')
    return True
