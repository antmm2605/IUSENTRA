-- Metadati consultivi; i trigger outbox sono installati dalla migrazione governata.
CREATE TABLE IF NOT EXISTS calendar_query_owner (
        singleton INTEGER PRIMARY KEY,tenant_key TEXT NOT NULL,version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS calendar_query_index (
        tenant_key TEXT NOT NULL,domain TEXT NOT NULL,record_key TEXT NOT NULL,
        event_day TEXT NOT NULL,sort_key TEXT NOT NULL,status TEXT NOT NULL,title TEXT NOT NULL,kind TEXT NOT NULL,
        source_revision TEXT NOT NULL,issue TEXT NOT NULL,
        PRIMARY KEY(tenant_key,domain,record_key));

CREATE INDEX IF NOT EXISTS idx_calendar_query_day
        ON calendar_query_index(tenant_key,domain,event_day,sort_key,record_key);

CREATE INDEX IF NOT EXISTS idx_calendar_query_status_day
        ON calendar_query_index(tenant_key,domain,status,event_day,sort_key,record_key);

CREATE INDEX IF NOT EXISTS idx_calendar_query_kind_day
        ON calendar_query_index(tenant_key,domain,kind,event_day,sort_key,record_key);

CREATE TABLE IF NOT EXISTS calendar_query_bootstrap (
        tenant_key TEXT NOT NULL,domain TEXT NOT NULL,version INTEGER NOT NULL,
        PRIMARY KEY(tenant_key,domain));

CREATE TABLE IF NOT EXISTS calendar_query_migrations (
        id TEXT PRIMARY KEY,tenant_key TEXT NOT NULL,domain TEXT NOT NULL,
        backup_reference TEXT NOT NULL,backup_sha256 TEXT NOT NULL,actor_key TEXT NOT NULL,
        after_key TEXT NOT NULL DEFAULT '',processed_count INTEGER NOT NULL DEFAULT 0,
        phase TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        UNIQUE(tenant_key,domain,backup_reference));

CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_query_active_migration
        ON calendar_query_migrations(tenant_key,domain) WHERE phase='BACKFILL';
