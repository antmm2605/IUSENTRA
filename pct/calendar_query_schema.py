"""Schema dei metadati calendario; nessuna esecuzione durante una domanda."""
from pct.query_projection_outbox import install_source_trigger
from pct.transactional_outbox import POSTGRES_SCHEMA

DDL = (
    '''CREATE TABLE IF NOT EXISTS calendar_query_owner (
        singleton INTEGER PRIMARY KEY,tenant_key TEXT NOT NULL,version INTEGER NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS calendar_query_index (
        tenant_key TEXT NOT NULL,domain TEXT NOT NULL,record_key TEXT NOT NULL,
        event_day TEXT NOT NULL,sort_key TEXT NOT NULL,status TEXT NOT NULL,title TEXT NOT NULL,kind TEXT NOT NULL,
        source_revision TEXT NOT NULL,issue TEXT NOT NULL,
        PRIMARY KEY(tenant_key,domain,record_key))''',
    '''CREATE INDEX IF NOT EXISTS idx_calendar_query_day
        ON calendar_query_index(tenant_key,domain,event_day,sort_key,record_key)''',
    '''CREATE INDEX IF NOT EXISTS idx_calendar_query_status_day
        ON calendar_query_index(tenant_key,domain,status,event_day,sort_key,record_key)''',
    '''CREATE INDEX IF NOT EXISTS idx_calendar_query_kind_day
        ON calendar_query_index(tenant_key,domain,kind,event_day,sort_key,record_key)''',
    '''CREATE TABLE IF NOT EXISTS calendar_query_bootstrap (
        tenant_key TEXT NOT NULL,domain TEXT NOT NULL,version INTEGER NOT NULL,
        PRIMARY KEY(tenant_key,domain))''',
    '''CREATE TABLE IF NOT EXISTS calendar_query_migrations (
        id TEXT PRIMARY KEY,tenant_key TEXT NOT NULL,domain TEXT NOT NULL,
        backup_reference TEXT NOT NULL,backup_sha256 TEXT NOT NULL,actor_key TEXT NOT NULL,
        after_key TEXT NOT NULL DEFAULT '',processed_count INTEGER NOT NULL DEFAULT 0,
        phase TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        UNIQUE(tenant_key,domain,backup_reference))''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_query_active_migration
        ON calendar_query_migrations(tenant_key,domain) WHERE phase='BACKFILL' ''',
)

EVENT_TYPE = 'calendar_query.refresh_requested'


def install_calendar_query_events(conn, *, postgres=False):
    """Migrazione esplicita su database proprietario già identificato."""
    for statement in DDL:
        conn.execute(statement)
    for statement in POSTGRES_SCHEMA.split(';'):
        if statement.strip():
            conn.execute(statement)
    conn.execute('CREATE INDEX IF NOT EXISTS idx_outbox_calendar_query_pending '
                 'ON transactional_outbox(tenant_id,aggregate_type,event_type,status,aggregate_id)')
    owner = '(SELECT tenant_key FROM calendar_query_owner WHERE singleton=1)'
    for domain, table in (('agenda', 'appuntamenti'), ('deadlines', 'scadenze')):
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            predicate = f'{owner} IS NOT NULL'
            if action == 'UPDATE':
                # Tutte le colonne native contribuiscono all'impronta. Il
                # confronto è null-safe e non usa una funzione esterna alle app.
                from pct.agenda_sql_writer import COLUMNS as AGENDA_COLUMNS
                from pct.scadenziario_sql_writer import COLUMNS as DEADLINE_COLUMNS
                columns = AGENDA_COLUMNS + ('modificato_il',) if domain == 'agenda' else DEADLINE_COLUMNS
                equal = ' AND '.join(f'(OLD.{key}=NEW.{key} OR (OLD.{key} IS NULL AND NEW.{key} IS NULL))' for key in columns)
                # COALESCE evita che una differenza NULL/stringa venga scartata.
                predicate += f' AND NOT COALESCE(({equal}),FALSE)'
            install_source_trigger(conn, table=table, action=action,
                name=f'iusentra_query_{table}_{action.lower()}', tenant_sql=owner,
                aggregate_sql=f"'calendar_query:{domain}'", key_sql='{row}.id',
                event_type=EVENT_TYPE, predicate=predicate, postgres=postgres)
        install_source_trigger(conn, table='calendar_query_index', action='DELETE',
            name=f'iusentra_query_calendar_index_{domain}_delete', tenant_sql='{row}.tenant_key',
            aggregate_sql=f"'calendar_query:{domain}'", key_sql='{row}.record_key', event_type=EVENT_TYPE,
            predicate=f"{{row}}.domain='{domain}' AND EXISTS (SELECT 1 FROM {table} s WHERE s.id={{row}}.record_key)",
            postgres=postgres)
