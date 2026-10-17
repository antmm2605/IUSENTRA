-- Installazione esplicita del catalogo consultivo, mai nelle richieste di lettura.
CREATE TABLE IF NOT EXISTS pec_deposit_query_index (
        tenant_id TEXT NOT NULL,message_id TEXT NOT NULL,report_id TEXT NOT NULL,
        source_revision TEXT NOT NULL,mime_sha256 TEXT NOT NULL,state TEXT NOT NULL,
        event_at TEXT NOT NULL,correlation_key TEXT NOT NULL,case_id TEXT NOT NULL,
        candidate_case_id TEXT NOT NULL,title TEXT NOT NULL,issue TEXT NOT NULL,
        PRIMARY KEY(tenant_id,message_id));

CREATE INDEX IF NOT EXISTS idx_pec_deposit_query_period
        ON pec_deposit_query_index(tenant_id,state,event_at,message_id);

CREATE INDEX IF NOT EXISTS idx_pec_deposit_query_case
        ON pec_deposit_query_index(tenant_id,case_id,state,event_at,message_id);

CREATE INDEX IF NOT EXISTS idx_pec_deposit_query_issue
        ON pec_deposit_query_index(tenant_id,state,issue,message_id);

CREATE TABLE IF NOT EXISTS pec_deposit_query_bootstrap (
        tenant_id TEXT PRIMARY KEY,version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS pec_deposit_query_migrations (
        id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,backup_reference TEXT NOT NULL,
        backup_sha256 TEXT NOT NULL,actor_key TEXT NOT NULL,after_key TEXT NOT NULL DEFAULT '',
        phase TEXT NOT NULL,processed_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        UNIQUE(tenant_id,backup_reference));

CREATE UNIQUE INDEX IF NOT EXISTS idx_pec_deposit_query_migration_active
        ON pec_deposit_query_migrations(tenant_id) WHERE phase='BACKFILL';
