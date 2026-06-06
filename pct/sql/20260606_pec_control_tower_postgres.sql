-- PEC Control Tower - PostgreSQL schema
-- Parita' strutturale del runtime SQLite per produzione.

CREATE TABLE IF NOT EXISTS legal_communications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    account_email TEXT NOT NULL DEFAULT '',
    folder TEXT NOT NULL DEFAULT '',
    message_id_header TEXT NOT NULL DEFAULT '',
    original_message_id TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    sender TEXT NOT NULL DEFAULT '',
    recipients_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    received_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ NULL,
    mime_sha256 TEXT NOT NULL,
    technical_type TEXT NOT NULL,
    legal_category TEXT NOT NULL,
    legal_event_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    confidence_label TEXT NOT NULL DEFAULT '',
    requires_human_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'open',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    fascicolo_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'media',
    summary TEXT NOT NULL DEFAULT '',
    extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, mime_sha256)
);

CREATE TABLE IF NOT EXISTS legal_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    risk_level TEXT NOT NULL DEFAULT 'media',
    event_at TIMESTAMPTZ NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    extracted_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expected_documents_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    produced_documents_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_documents_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    legal_articles_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggested_actions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_receipt_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    referred_message_id TEXT NOT NULL DEFAULT '',
    receipt_type TEXT NOT NULL DEFAULT '',
    recipient TEXT NOT NULL DEFAULT '',
    receipt_at TIMESTAMPTZ NULL,
    daticert_sha256 TEXT NOT NULL DEFAULT '',
    daticert_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    proof_status TEXT NOT NULL DEFAULT 'partial',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_deadlines (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES legal_events(id) ON DELETE CASCADE,
    matter_id TEXT NOT NULL DEFAULT '',
    rule_code TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    title TEXT NOT NULL,
    due_at TIMESTAMPTZ NOT NULL,
    source_event_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft_pending_confirmation',
    risk_level TEXT NOT NULL DEFAULT 'media',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    requires_human_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    confirmed_at TIMESTAMPTZ NULL,
    confirmed_by TEXT NOT NULL DEFAULT '',
    confirmation_rule TEXT NOT NULL DEFAULT '',
    calculation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS agenda_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES legal_events(id) ON DELETE CASCADE,
    matter_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    source TEXT NOT NULL DEFAULT 'pec_control_tower',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_event_tasks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES legal_events(id) ON DELETE CASCADE,
    matter_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'media',
    due_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS notification_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES legal_events(id) ON DELETE CASCADE,
    matter_id TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL DEFAULT 'outbound',
    recipient TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT 'PEC',
    title TEXT NOT NULL,
    draft_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft_pending_confirmation',
    risk_level TEXT NOT NULL DEFAULT 'media',
    requires_human_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    approved_at TIMESTAMPTZ NULL,
    approved_by TEXT NOT NULL DEFAULT '',
    sent_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_recipients (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    notification_id TEXT NOT NULL REFERENCES notification_jobs(id) ON DELETE CASCADE,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    registry_source TEXT NOT NULL DEFAULT '',
    registry_status TEXT NOT NULL DEFAULT 'not_checked',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS registry_lookups (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    recipient_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    registry TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'not_checked',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_proofs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    notification_id TEXT NOT NULL DEFAULT '',
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    proof_type TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL DEFAULT '',
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'partial',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_rule_versions (
    code TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    legal_basis_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    deadline_days INTEGER NOT NULL DEFAULT 0,
    calendar_mode TEXT NOT NULL DEFAULT 'calendar',
    requires_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (code, version)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    previous_hash TEXT NOT NULL DEFAULT '',
    event_hash TEXT NOT NULL,
    key_hint TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_legal_communications_tenant_received
    ON legal_communications (tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_legal_communications_category
    ON legal_communications (tenant_id, legal_category, status);
CREATE INDEX IF NOT EXISTS idx_legal_deadlines_status
    ON legal_deadlines (tenant_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_notification_jobs_status
    ON notification_jobs (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_referred
    ON pec_receipt_events (tenant_id, referred_message_id, role);
