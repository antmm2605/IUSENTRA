-- PEC Control Tower - SQLite schema
-- Fonte software: pct.pec_control_tower.SQLITE_SCHEMA, versione 2026-06-06.1.
-- Ogni PEC diventa evento giuridico tracciato; scadenze e notifiche restano bozze
-- finche' non vengono confermate dall'avvocato.

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
    recipients_json TEXT NOT NULL DEFAULT '[]',
    received_at TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT '',
    mime_sha256 TEXT NOT NULL,
    technical_type TEXT NOT NULL,
    legal_category TEXT NOT NULL,
    legal_event_type TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    confidence_label TEXT NOT NULL DEFAULT '',
    requires_human_confirmation INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'open',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    fascicolo_score REAL NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'media',
    summary TEXT NOT NULL DEFAULT '',
    extracted_json TEXT NOT NULL DEFAULT '{}',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    source_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
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
    event_at TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    extracted_json TEXT NOT NULL DEFAULT '{}',
    expected_documents_json TEXT NOT NULL DEFAULT '[]',
    produced_documents_json TEXT NOT NULL DEFAULT '[]',
    missing_documents_json TEXT NOT NULL DEFAULT '[]',
    legal_articles_json TEXT NOT NULL DEFAULT '[]',
    suggested_actions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_receipt_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    referred_message_id TEXT NOT NULL DEFAULT '',
    receipt_type TEXT NOT NULL DEFAULT '',
    recipient TEXT NOT NULL DEFAULT '',
    receipt_at TEXT NOT NULL DEFAULT '',
    daticert_sha256 TEXT NOT NULL DEFAULT '',
    daticert_json TEXT NOT NULL DEFAULT '{}',
    proof_status TEXT NOT NULL DEFAULT 'partial',
    created_at TEXT NOT NULL
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
    due_at TEXT NOT NULL,
    source_event_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft_pending_confirmation',
    risk_level TEXT NOT NULL DEFAULT 'media',
    confidence REAL NOT NULL DEFAULT 0,
    requires_human_confirmation INTEGER NOT NULL DEFAULT 1,
    confirmed_at TEXT NOT NULL DEFAULT '',
    confirmed_by TEXT NOT NULL DEFAULT '',
    confirmation_rule TEXT NOT NULL DEFAULT '',
    calculation_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agenda_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL REFERENCES legal_communications(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES legal_events(id) ON DELETE CASCADE,
    matter_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    source TEXT NOT NULL DEFAULT 'pec_control_tower',
    created_at TEXT NOT NULL
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
    due_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT ''
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
    requires_human_confirmation INTEGER NOT NULL DEFAULT 1,
    approved_at TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    sent_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registry_lookups (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    recipient_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    registry TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'not_checked',
    confidence REAL NOT NULL DEFAULT 0,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
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
    evidence_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'partial',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_rule_versions (
    code TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    legal_basis_json TEXT NOT NULL DEFAULT '[]',
    deadline_days INTEGER NOT NULL DEFAULT 0,
    calendar_mode TEXT NOT NULL DEFAULT 'calendar',
    requires_confirmation INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY (code, version)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    previous_hash TEXT NOT NULL DEFAULT '',
    event_hash TEXT NOT NULL,
    key_hint TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_legal_communications_tenant_received
    ON legal_communications (tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_legal_communications_event_received
    ON legal_communications (tenant_id, legal_event_type, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_legal_communications_event_received_prefix
    ON legal_communications (tenant_id, legal_event_type, substr(received_at, 1, 19));
CREATE INDEX IF NOT EXISTS idx_legal_communications_category
    ON legal_communications (tenant_id, legal_category, status);
CREATE INDEX IF NOT EXISTS idx_legal_deadlines_status
    ON legal_deadlines (tenant_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_notification_jobs_status
    ON notification_jobs (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_referred
    ON pec_receipt_events (tenant_id, referred_message_id, role);
