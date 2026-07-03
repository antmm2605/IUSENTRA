-- IUSENTRA PEC audit-grade pipeline - PostgreSQL
-- Versione: 2026-05-21.pec-audit-pipeline.v1

CREATE TABLE IF NOT EXISTS pec_schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL,
    sha256 text NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_retention_policies (
    id text PRIMARY KEY,
    name text NOT NULL,
    original_mime_days integer NOT NULL,
    parsed_json_days integer NOT NULL,
    legal_hold boolean NOT NULL DEFAULT true,
    action text NOT NULL DEFAULT 'review',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_messages (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    account_email text NOT NULL,
    folder text NOT NULL,
    imap_uid text NOT NULL DEFAULT '',
    message_id_header text NOT NULL DEFAULT '',
    mime_sha256 text NOT NULL,
    mime_size integer NOT NULL,
    original_mime bytea NOT NULL,
    received_at timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'ingested',
    quality_status text NOT NULL DEFAULT 'da_controllare',
    signature_status text NOT NULL DEFAULT 'non_verificata',
    linked_fascicolo_id text NOT NULL DEFAULT '',
    linked_fascicolo_score double precision NOT NULL DEFAULT 0,
    retention_policy_id text NOT NULL DEFAULT 'pec_audit_default',
    retention_until date,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (tenant_id, account_email, message_id_header, mime_sha256),
    UNIQUE (tenant_id, mime_sha256)
);

CREATE TABLE IF NOT EXISTS pec_parsed_versions (
    id text PRIMARY KEY,
    message_id text NOT NULL REFERENCES pec_messages(id),
    version integer NOT NULL,
    parser_version text NOT NULL,
    parsed_json jsonb NOT NULL,
    parsed_sha256 text NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL DEFAULT 'pec-pipeline',
    UNIQUE (message_id, version)
);

CREATE TABLE IF NOT EXISTS pec_attachments (
    id text PRIMARY KEY,
    message_id text NOT NULL REFERENCES pec_messages(id),
    parsed_version_id text NOT NULL REFERENCES pec_parsed_versions(id),
    attachment_index integer NOT NULL,
    filename text NOT NULL,
    content_type text NOT NULL,
    size_bytes integer NOT NULL,
    sha256 text NOT NULL,
    classification text NOT NULL,
    classification_score double precision NOT NULL,
    classification_reason text NOT NULL,
    ocr_text text NOT NULL DEFAULT '',
    ocr_coverage double precision NOT NULL DEFAULT 0,
    signature_status text NOT NULL DEFAULT 'non_verificata',
    signature_details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    UNIQUE (message_id, parsed_version_id, attachment_index)
);

CREATE TABLE IF NOT EXISTS pec_validation_reports (
    id text PRIMARY KEY,
    message_id text NOT NULL REFERENCES pec_messages(id),
    parsed_version_id text NOT NULL REFERENCES pec_parsed_versions(id),
    event_type text NOT NULL,
    report_json jsonb NOT NULL,
    report_sha256 text NOT NULL,
    severity text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_fascicolo_links (
    id text PRIMARY KEY,
    message_id text NOT NULL REFERENCES pec_messages(id),
    parsed_version_id text NOT NULL REFERENCES pec_parsed_versions(id),
    fascicolo_id text NOT NULL DEFAULT '',
    score double precision NOT NULL,
    status text NOT NULL,
    seeds_json jsonb NOT NULL,
    candidates_json jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_legal_events (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    message_id text NOT NULL REFERENCES pec_messages(id),
    parsed_version_id text NOT NULL REFERENCES pec_parsed_versions(id),
    rulepack_version text NOT NULL,
    family text NOT NULL,
    primary_event text NOT NULL,
    priority text NOT NULL,
    confidence double precision NOT NULL,
    human_review_required boolean NOT NULL,
    event_json jsonb NOT NULL,
    event_sha256 text NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (tenant_id, message_id, parsed_version_id, event_sha256)
);

CREATE TABLE IF NOT EXISTS pec_legal_deadlines (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    legal_event_id text NOT NULL REFERENCES pec_legal_events(id) ON DELETE CASCADE,
    deadline_type text NOT NULL,
    norm_ref text NOT NULL,
    dies_a_quo_type text NOT NULL,
    dies_a_quo_date date,
    duration_value integer,
    duration_unit text NOT NULL DEFAULT '',
    direction text NOT NULL DEFAULT 'forward',
    peremptory boolean,
    deterministic_status text NOT NULL,
    scadenziario_id text NOT NULL DEFAULT '',
    human_review_required boolean NOT NULL,
    evidence_json jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_legal_hearings (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    legal_event_id text NOT NULL REFERENCES pec_legal_events(id) ON DELETE CASCADE,
    hearing_date date,
    hearing_time text NOT NULL DEFAULT '',
    mode text NOT NULL,
    platform text NOT NULL DEFAULT '',
    link text NOT NULL DEFAULT '',
    link_verified boolean NOT NULL DEFAULT false,
    aula text NOT NULL DEFAULT '',
    piano text NOT NULL DEFAULT '',
    indirizzo text NOT NULL DEFAULT '',
    agenda_id text NOT NULL DEFAULT '',
    human_review_required boolean NOT NULL,
    evidence_json jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_legal_payments (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    legal_event_id text NOT NULL REFERENCES pec_legal_events(id) ON DELETE CASCADE,
    payment_event_type text NOT NULL,
    beneficiary_type text NOT NULL,
    payer text NOT NULL DEFAULT '',
    lawyer_direct_credit boolean NOT NULL DEFAULT false,
    amounts_json jsonb NOT NULL,
    workflow_status text NOT NULL DEFAULT 'to_review',
    incasso_id text NOT NULL DEFAULT '',
    human_review_required boolean NOT NULL,
    evidence_json jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_jobs (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    message_id text NOT NULL DEFAULT '',
    job_type text NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    priority integer NOT NULL DEFAULT 50,
    attempts integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3,
    available_at timestamptz NOT NULL,
    started_at timestamptz,
    finished_at timestamptz,
    error text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (tenant_id, message_id, job_type, status)
);

CREATE TABLE IF NOT EXISTS pec_digest_runs (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    digest_date date NOT NULL,
    run_at timestamptz NOT NULL,
    digest_json jsonb NOT NULL,
    digest_sha256 text NOT NULL,
    status text NOT NULL,
    UNIQUE (tenant_id, digest_date)
);

CREATE TABLE IF NOT EXISTS pec_local_acquire_runs (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    status text NOT NULL DEFAULT 'running',
    started_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    finished_at timestamptz,
    cursor_index integer NOT NULL DEFAULT 0,
    total_emails integer NOT NULL DEFAULT 0,
    batch_size integer NOT NULL DEFAULT 50,
    acquired integer NOT NULL DEFAULT 0,
    duplicates integer NOT NULL DEFAULT 0,
    skipped_missing_mime integer NOT NULL DEFAULT 0,
    skipped_not_pec integer NOT NULL DEFAULT 0,
    queued_repairs integer NOT NULL DEFAULT 0,
    deadline_created integer NOT NULL DEFAULT 0,
    deadline_already_exists integer NOT NULL DEFAULT 0,
    deadline_expired integer NOT NULL DEFAULT 0,
    deadline_not_ready integer NOT NULL DEFAULT 0,
    deadline_errors integer NOT NULL DEFAULT 0,
    agenda_linked integer NOT NULL DEFAULT 0,
    errors integer NOT NULL DEFAULT 0,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS pec_local_acquire_items (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    run_id text NOT NULL REFERENCES pec_local_acquire_runs(id),
    email_id text NOT NULL DEFAULT '',
    message_id text NOT NULL DEFAULT '',
    subject text NOT NULL DEFAULT '',
    status text NOT NULL,
    deadline_status text NOT NULL DEFAULT '',
    due_date date,
    deadline_id text NOT NULL DEFAULT '',
    agenda_id text NOT NULL DEFAULT '',
    detail_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (tenant_id, run_id, email_id)
);

CREATE TABLE IF NOT EXISTS pec_audit_log (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    occurred_at timestamptz NOT NULL,
    actor text NOT NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    payload_json jsonb NOT NULL,
    prev_hash text NOT NULL,
    entry_hash text NOT NULL
);

CREATE OR REPLACE FUNCTION pec_audit_log_append_only()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'pec_audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS pec_audit_log_no_update ON pec_audit_log;
CREATE TRIGGER pec_audit_log_no_update
BEFORE UPDATE ON pec_audit_log
FOR EACH ROW EXECUTE FUNCTION pec_audit_log_append_only();

DROP TRIGGER IF EXISTS pec_audit_log_no_delete ON pec_audit_log;
CREATE TRIGGER pec_audit_log_no_delete
BEFORE DELETE ON pec_audit_log
FOR EACH ROW EXECUTE FUNCTION pec_audit_log_append_only();

CREATE INDEX IF NOT EXISTS idx_pec_messages_received ON pec_messages(tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_pec_messages_quality ON pec_messages(tenant_id, quality_status);
CREATE INDEX IF NOT EXISTS idx_pec_legal_events_message ON pec_legal_events(tenant_id, message_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pec_legal_events_priority ON pec_legal_events(tenant_id, priority, human_review_required);
CREATE INDEX IF NOT EXISTS idx_pec_legal_deadlines_event ON pec_legal_deadlines(tenant_id, legal_event_id);
CREATE INDEX IF NOT EXISTS idx_pec_legal_hearings_event ON pec_legal_hearings(tenant_id, legal_event_id, hearing_date);
CREATE INDEX IF NOT EXISTS idx_pec_legal_payments_event ON pec_legal_payments(tenant_id, legal_event_id);
CREATE INDEX IF NOT EXISTS idx_pec_jobs_due ON pec_jobs(status, available_at, priority);
CREATE INDEX IF NOT EXISTS idx_pec_local_runs_status ON pec_local_acquire_runs(tenant_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_run ON pec_local_acquire_items(tenant_id, run_id, status);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_email ON pec_local_acquire_items(tenant_id, email_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_message ON pec_local_acquire_items(tenant_id, message_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_deadline ON pec_local_acquire_items(tenant_id, deadline_status, due_date);
CREATE INDEX IF NOT EXISTS idx_pec_audit_resource ON pec_audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_pec_audit_action_resource ON pec_audit_log(tenant_id, action, resource_type, resource_id);
