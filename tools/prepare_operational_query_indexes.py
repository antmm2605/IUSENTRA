"""Prepara le consultazioni prima dell'avvio, riusando repository e backup nativi."""
import argparse
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from pct.calendar_query_preparation import rebuild as rebuild_calendar
from pct.calendar_query_repository import CalendarQueryNotReady, CalendarQueryRepository
from pct.email_mailbox_query_events import projection_ready
from pct.email_mailbox_repository import EmailMailboxRepository
from pct.pec_notification_presidio import NotificationPresidioRepository
from pct.pec_notification_presidio.repository_consultations import CONSULTATION_INDEXES
from scripts.query_index_backup import verified_backup


def _has_table(database, name):
    if getattr(database, 'backend_kind', '') == 'postgresql':
        return database.conn.execute('SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?', (name,)).fetchone() is not None
    return database.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def prepare_core(database, *, tenant, destination, max_batches=1000):
    if not tenant or type(max_batches) is not int or not 1 <= max_batches <= 1000:
        raise ValueError('Studio e budget finito sono obbligatori.')
    changed = []
    for kind in ('pec', 'ordinary'):
        repo = EmailMailboxRepository(database, tenant, kind)
        repo._assert_initialized()
        marker = None
        if _has_table(database, 'email_mailbox_query_bootstrap'):
            marker = database.conn.execute('SELECT version FROM email_mailbox_query_bootstrap WHERE tenant_key=? AND mailbox_kind=?', (tenant, kind)).fetchone()
        if marker is not None and marker[0] == 1:
            for _ in range(max_batches):
                if projection_ready(database.conn, tenant, kind):
                    break
                result = repo.retry_query_index_events(limit=100)
                if not result['delivered'] or result['failed']:
                    raise RuntimeError('Eventi della casella da recuperare prima di attivare la release.')
            if not projection_ready(database.conn, tenant, kind):
                raise RuntimeError('Budget della ripresa casella terminato: riprendere la consegna.')
            continue
        snapshot, digest = verified_backup(database, destination)
        repo.ensure_schema()
        state = repo.begin_query_index_migration(backup_reference=str(snapshot), backup_sha256=digest,
                                                 actor_key='operational-query-preparation')
        for _ in range(max_batches):
            if state['phase'] == 'COMPLETED':
                break
            batch = repo.rebuild_query_index_batch(migration_id=state['id'], after_key=state['after_key'],
                                                   actor_key='operational-query-preparation')
            state.update(after_key=batch['after_key'], phase='COMPLETED' if batch['done'] else 'BACKFILL')
        if state['phase'] != 'COMPLETED':
            raise RuntimeError('Lotto casella non concluso: checkpoint conservato, release non attivata.')
        changed.append(kind)
    ready = set()
    if _has_table(database, 'calendar_query_owner'):
        owner = database.conn.execute('SELECT tenant_key FROM calendar_query_owner WHERE singleton=1').fetchone()
        if owner is not None and owner[0] != tenant:
            raise ValueError('Catalogo calendario di un altro studio.')
        if owner is not None:
            ready = {row[0] for row in database.conn.execute('SELECT domain FROM calendar_query_bootstrap WHERE tenant_key=? AND version=1', (tenant,)).fetchall()}
    for domain in ('agenda', 'deadlines'):
        if domain in ready:
            calendar = CalendarQueryRepository(database, tenant)
            for _ in range(max_batches):
                try:
                    calendar._ready(domain)
                    break
                except CalendarQueryNotReady:
                    delivered = calendar.retry_events(domain=domain, limit=100)
                    if not delivered['delivered'] or delivered['failed']:
                        raise RuntimeError('Eventi calendario da recuperare prima di attivare la release.') from None
            calendar._ready(domain)
            continue
        result = rebuild_calendar(database, tenant=tenant, destination=destination, domain=domain, max_batches=max_batches)
        if result['phase'] != 'COMPLETED':
            raise RuntimeError('Lotto calendario non concluso: checkpoint conservato, release non attivata.')
        changed.append(domain)
    return changed


def prepare_notifications(path, *, tenant, destination):
    path = Path(path)
    summary_index = '''CREATE INDEX IF NOT EXISTS idx_pec_messages_header_summary ON pec_messages(
        tenant_id, received_at DESC, message_id_header, id, quality_status,
        signature_status, linked_fascicolo_id, linked_fascicolo_score)'''
    list_index = '''CREATE INDEX IF NOT EXISTS idx_pec_messages_list_summary ON pec_messages(
        tenant_id, received_at DESC, id DESC, account_email, folder, imap_uid,
        message_id_header, mime_sha256, mime_size, ingested_at, status,
        quality_status, signature_status, linked_fascicolo_id, linked_fascicolo_score,
        retention_policy_id, retention_until, metadata_json)'''
    has_messages = False
    if path.is_file():
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            conn.execute('PRAGMA query_only=ON')
            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            has_messages = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pec_messages'").fetchone() is not None
            required = {'idx_pec_notification_query_due', 'idx_pec_notification_query_rac'}
            audit_ready = True
            if has_messages:
                from pct.pec_pipeline import SCHEMA_VERSION, SQLITE_SCHEMA, sha256_bytes

                required.update({'idx_pec_messages_header_summary', 'idx_pec_messages_list_summary'})
                migration_sha = sha256_bytes(SQLITE_SCHEMA.encode('utf-8'))
                try:
                    audit_ready = conn.execute('SELECT 1 FROM pec_schema_migrations WHERE version=? AND sha256=?',
                        (f'{SCHEMA_VERSION}:schema:{migration_sha}', migration_sha)).fetchone() is not None
                except sqlite3.OperationalError as exc:
                    if 'no such table' not in str(exc).lower():
                        raise
                    audit_ready = False
            if required <= indexes and audit_ready:
                return False
            verified_backup(SimpleNamespace(conn=conn, db_path=path, backend_kind='sqlite'), destination)
    repository = NotificationPresidioRepository(path, tenant_id=tenant)
    try:
        with repository.connection() as conn:
            for statement in CONSULTATION_INDEXES:
                conn.execute(statement)
            if has_messages:
                conn.execute(summary_index)
                conn.execute(list_index)
    finally:
        repository.close()
    if has_messages:
        # Esegue il solo schema del repository prima dello swap applicativo,
        # così la nuova impronta non scatena DDL alla prima consultazione.
        from pct.pec_pipeline import PecAuditRepository

        PecAuditRepository(path, tenant_id=tenant)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-registry', required=True)
    parser.add_argument('--backup-dir', required=True, type=Path)
    parser.add_argument('--tenant', default='')
    args = parser.parse_args()
    from pct.postgres_runtime_support import database_config_to_dsn
    from pct.storage import StudioDB
    from pct.storage_postgres import PostgresStudioDB
    from pct.tenant import DbMode, GestioneTenant, StatoTenant
    from web.services.storage_runtime import resolve_storage_runtime

    registry = GestioneTenant(registry_path=str(Path(args.tenant_registry).resolve(strict=True)))
    selected = False
    for owner in registry.lista():
        if owner.stato == StatoTenant.SOSPESO or (args.tenant and owner.slug != args.tenant):
            continue
        selected = True
        paths = registry.percorsi_dati(owner.slug, reconcile_aliases=False, ensure_baseline=False)
        profile = resolve_storage_runtime(anchor_path=paths['FASCICOLI_DB'], tenant=owner)
        if profile.external_sql_configured and profile.effective_mode != profile.selected_mode:
            raise RuntimeError('Backend SQL configurato non disponibile: nessuna preparazione su copie storiche.')
        if profile.uses_sqlite:
            if not Path(profile.studio_db_path).is_file():
                raise RuntimeError('Database dello studio non predisposto: nessuna creazione implicita.')
            backend = StudioDB(profile.studio_db_path, initialize_schema=False)
        elif profile.effective_mode == DbMode.POSTGRESQL:
            backend = PostgresStudioDB(database_config_to_dsn(owner.database), initialize_schema=False)
        else:
            print(json.dumps(dict(tenant=owner.slug, status='archivio_non_sql')), flush=True)
            continue
        try:
            changed = prepare_core(backend, tenant=owner.slug, destination=args.backup_dir / owner.slug / 'core')
        finally:
            backend.chiudi()
        path = paths.get('PEC_AUDIT_DB') or str(Path(paths['EMAIL_CASELLA_DB']).parent / 'pec_audit.sqlite')
        notifications = prepare_notifications(path, tenant=owner.slug, destination=args.backup_dir / owner.slug / 'notifications')
        print(json.dumps(dict(tenant=owner.slug, changed=changed, notifications_changed=notifications)), flush=True)
    if args.tenant and not selected:
        raise ValueError('Studio richiesto non disponibile: nessuna preparazione eseguita.')


if __name__ == '__main__':
    main()
