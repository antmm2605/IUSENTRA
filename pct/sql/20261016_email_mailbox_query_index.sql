-- Proiezione consultiva: struttura soltanto, riallineamento esplicito dopo backup.
CREATE TABLE IF NOT EXISTS email_mailbox_query_index (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        message_key TEXT NOT NULL, event_at_utc TEXT NOT NULL,
        direction TEXT NOT NULL, deposit_status TEXT NOT NULL,
        source_revision TEXT NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind,message_key));

CREATE INDEX IF NOT EXISTS idx_email_mailbox_query_period
        ON email_mailbox_query_index
        (tenant_key,mailbox_kind,direction,event_at_utc,message_key);

CREATE INDEX IF NOT EXISTS idx_email_mailbox_query_deposit
        ON email_mailbox_query_index
        (tenant_key,mailbox_kind,deposit_status,event_at_utc,message_key);

CREATE TABLE IF NOT EXISTS email_mailbox_query_bootstrap (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL, version INTEGER NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind));

CREATE TABLE IF NOT EXISTS email_mailbox_query_schema (
        singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS email_mailbox_query_migrations (
        id TEXT PRIMARY KEY, tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        backup_reference TEXT NOT NULL, backup_sha256 TEXT NOT NULL, actor_key TEXT NOT NULL,
        after_key TEXT NOT NULL DEFAULT '', processed_count INTEGER NOT NULL DEFAULT 0,
        phase TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(tenant_key,mailbox_kind,backup_reference));

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_mailbox_query_active_migration
        ON email_mailbox_query_migrations(tenant_key,mailbox_kind) WHERE phase='BACKFILL';
