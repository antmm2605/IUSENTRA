-- IUSENTRA production hardening - SQLite

CREATE TABLE IF NOT EXISTS json_documents (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    record_key TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_json_documents_source ON json_documents(source_path);
CREATE INDEX IF NOT EXISTS idx_json_documents_record_key ON json_documents(record_key);

CREATE VIRTUAL TABLE IF NOT EXISTS json_documents_fts
USING fts5(id UNINDEXED, title, body, source_path UNINDEXED);

CREATE TABLE IF NOT EXISTS hardening_audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    previous_hash TEXT NOT NULL DEFAULT '',
    signature TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hardening_audit_action ON hardening_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_hardening_audit_tenant ON hardening_audit_log(tenant_id);
