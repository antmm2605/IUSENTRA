-- IUSENTRA PEC audit-grade pipeline - SQLite
-- Versione: 2026-05-21.pec-audit-pipeline.v1

CREATE TABLE IF NOT EXISTS pec_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL,
    sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_retention_policies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    original_mime_days INTEGER NOT NULL,
    parsed_json_days INTEGER NOT NULL,
    legal_hold INTEGER NOT NULL DEFAULT 1,
    action TEXT NOT NULL DEFAULT 'review',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_messages (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    account_email TEXT NOT NULL,
    folder TEXT NOT NULL,
    imap_uid TEXT NOT NULL DEFAULT '',
    message_id_header TEXT NOT NULL DEFAULT '',
    mime_sha256 TEXT NOT NULL,
    mime_size INTEGER NOT NULL,
    original_mime BLOB NOT NULL,
    received_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ingested',
    quality_status TEXT NOT NULL DEFAULT 'da_controllare',
    signature_status TEXT NOT NULL DEFAULT 'non_verificata',
    linked_fascicolo_id TEXT NOT NULL DEFAULT '',
    linked_fascicolo_score REAL NOT NULL DEFAULT 0,
    retention_policy_id TEXT NOT NULL DEFAULT 'pec_audit_default',
    retention_until TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (tenant_id, account_email, message_id_header, mime_sha256),
    UNIQUE (tenant_id, mime_sha256)
);

CREATE TABLE IF NOT EXISTS pec_parsed_versions (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES pec_messages(id),
    version INTEGER NOT NULL,
    parser_version TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    parsed_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'pec-pipeline',
    UNIQUE (message_id, version)
);

CREATE TABLE IF NOT EXISTS pec_attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES pec_messages(id),
    parsed_version_id TEXT NOT NULL REFERENCES pec_parsed_versions(id),
    attachment_index INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    classification TEXT NOT NULL,
    classification_score REAL NOT NULL,
    classification_reason TEXT NOT NULL,
    ocr_text TEXT NOT NULL DEFAULT '',
    ocr_coverage REAL NOT NULL DEFAULT 0,
    signature_status TEXT NOT NULL DEFAULT 'non_verificata',
    signature_details_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (message_id, parsed_version_id, attachment_index)
);

CREATE TABLE IF NOT EXISTS pec_validation_reports (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES pec_messages(id),
    parsed_version_id TEXT NOT NULL REFERENCES pec_parsed_versions(id),
    event_type TEXT NOT NULL,
    report_json TEXT NOT NULL,
    report_sha256 TEXT NOT NULL,
    severity TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_fascicolo_links (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES pec_messages(id),
    parsed_version_id TEXT NOT NULL REFERENCES pec_parsed_versions(id),
    fascicolo_id TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL,
    status TEXT NOT NULL,
    seeds_json TEXT NOT NULL,
    candidates_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '',
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 50,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    available_at TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, message_id, job_type, status)
);

CREATE TABLE IF NOT EXISTS pec_digest_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    digest_date TEXT NOT NULL,
    run_at TEXT NOT NULL,
    digest_json TEXT NOT NULL,
    digest_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    UNIQUE (tenant_id, digest_date)
);

CREATE TABLE IF NOT EXISTS pec_audit_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS pec_audit_log_no_update
BEFORE UPDATE ON pec_audit_log
BEGIN
    SELECT RAISE(ABORT, 'pec_audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS pec_audit_log_no_delete
BEFORE DELETE ON pec_audit_log
BEGIN
    SELECT RAISE(ABORT, 'pec_audit_log is append-only');
END;

CREATE INDEX IF NOT EXISTS idx_pec_messages_received ON pec_messages(tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_pec_messages_quality ON pec_messages(tenant_id, quality_status);
CREATE INDEX IF NOT EXISTS idx_pec_jobs_due ON pec_jobs(status, available_at, priority);
CREATE INDEX IF NOT EXISTS idx_pec_audit_resource ON pec_audit_log(resource_type, resource_id);
