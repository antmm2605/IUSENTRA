-- IUSENTRA - Preparazione autonoma deposito legale - PostgreSQL

CREATE TABLE IF NOT EXISTS deposit_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    signed_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_code TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS deposit_documents (
    id TEXT PRIMARY KEY,
    deposit_job_id TEXT NOT NULL REFERENCES deposit_jobs(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'attachment',
    filename TEXT NOT NULL DEFAULT '',
    mime_type TEXT NOT NULL DEFAULT '',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    validation_status TEXT NOT NULL DEFAULT '',
    validation_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS deposit_packages (
    id TEXT PRIMARY KEY,
    deposit_job_id TEXT NOT NULL,
    package_path TEXT NOT NULL DEFAULT '',
    manifest_path TEXT NOT NULL DEFAULT '',
    xml_path TEXT NOT NULL DEFAULT '',
    zip_path TEXT NOT NULL DEFAULT '',
    p7m_path TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deposit_receipts (
    id TEXT PRIMARY KEY,
    deposit_job_id TEXT NOT NULL,
    receipt_type TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    pec_from TEXT NOT NULL DEFAULT '',
    pec_to TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    eml_path TEXT NOT NULL DEFAULT '',
    xml_path TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT '',
    parsed_json TEXT NOT NULL DEFAULT '{}',
    sha256 TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS deposit_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    deposit_job_id TEXT NOT NULL REFERENCES deposit_jobs(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    status_before TEXT NOT NULL DEFAULT '',
    status_after TEXT NOT NULL DEFAULT '',
    detail_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deposit_alerts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    deposit_job_id TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'INFO',
    title TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    dedupe_key TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_deposit_jobs_tenant_fascicolo ON deposit_jobs(tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_deposit_jobs_status ON deposit_jobs(status);
CREATE INDEX IF NOT EXISTS idx_deposit_documents_job ON deposit_documents(deposit_job_id);
CREATE INDEX IF NOT EXISTS idx_deposit_packages_job ON deposit_packages(deposit_job_id);
CREATE INDEX IF NOT EXISTS idx_deposit_receipts_job ON deposit_receipts(deposit_job_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_deposit_alerts_dedupe
    ON deposit_alerts(tenant_id, dedupe_key)
    WHERE dedupe_key <> '';
CREATE INDEX IF NOT EXISTS idx_deposit_alerts_status ON deposit_alerts(tenant_id, status);
