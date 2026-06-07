CREATE TABLE IF NOT EXISTS client_portal_profiles (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    fiscal_code TEXT NOT NULL DEFAULT '',
    identity_expires_at TEXT NOT NULL DEFAULT '',
    preferences_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_client_portal_profiles_tenant_client
    ON client_portal_profiles (tenant_id, client_id);
CREATE INDEX IF NOT EXISTS idx_client_portal_profiles_tenant_name
    ON client_portal_profiles (tenant_id, display_name);

CREATE TABLE IF NOT EXISTS client_portal_matters (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'attiva',
    progress INTEGER NOT NULL DEFAULT 0,
    next_action TEXT NOT NULL DEFAULT '',
    opened_at TEXT NOT NULL DEFAULT '',
    closed_at TEXT NOT NULL DEFAULT '',
    data_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_client_portal_matters_tenant_fascicolo
    ON client_portal_matters (tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_client_portal_matters_tenant_client
    ON client_portal_matters (tenant_id, client_id);
CREATE INDEX IF NOT EXISTS idx_client_portal_matters_tenant_status
    ON client_portal_matters (tenant_id, status);

CREATE TABLE IF NOT EXISTS client_portal_invites (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'attivo',
    expires_at TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT '',
    revoked_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    last_sent_at TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT 'email',
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_client_portal_invites_token_hash
    ON client_portal_invites (token_hash);
CREATE INDEX IF NOT EXISTS idx_client_portal_invites_tenant_client
    ON client_portal_invites (tenant_id, client_id);
CREATE INDEX IF NOT EXISTS idx_client_portal_invites_tenant_matter
    ON client_portal_invites (tenant_id, matter_id);
CREATE INDEX IF NOT EXISTS idx_client_portal_invites_tenant_status
    ON client_portal_invites (tenant_id, status);

CREATE TABLE IF NOT EXISTS client_portal_steps (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'da_fare',
    due_at TEXT NOT NULL DEFAULT '',
    visible_to_client INTEGER NOT NULL DEFAULT 1,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_client_portal_steps_tenant_matter_position
    ON client_portal_steps (tenant_id, matter_id, position);

CREATE TABLE IF NOT EXISTS client_portal_document_requests (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    required INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'richiesto',
    due_at TEXT NOT NULL DEFAULT '',
    accepted_types_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_client_portal_document_requests_tenant_matter
    ON client_portal_document_requests (tenant_id, matter_id, status);

CREATE TABLE IF NOT EXISTS client_portal_documents (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    request_id TEXT NOT NULL DEFAULT '',
    client_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'caricato',
    uploaded_at TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT '',
    review_note TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_client_portal_documents_tenant_matter
    ON client_portal_documents (tenant_id, matter_id, uploaded_at);
CREATE INDEX IF NOT EXISTS idx_client_portal_documents_tenant_client
    ON client_portal_documents (tenant_id, client_id);
CREATE INDEX IF NOT EXISTS idx_client_portal_documents_sha256
    ON client_portal_documents (sha256);

CREATE TABLE IF NOT EXISTS client_portal_signature_requests (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    document_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'da_firmare',
    due_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_client_portal_signature_requests_tenant_matter
    ON client_portal_signature_requests (tenant_id, matter_id, status);

CREATE TABLE IF NOT EXISTS client_portal_consents (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    consent_key TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1',
    accepted INTEGER NOT NULL DEFAULT 0,
    accepted_at TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_client_portal_consents_unique
    ON client_portal_consents (tenant_id, client_id, matter_id, consent_key, version);
CREATE INDEX IF NOT EXISTS idx_client_portal_consents_tenant_client
    ON client_portal_consents (tenant_id, client_id);

CREATE TABLE IF NOT EXISTS client_portal_messages (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    sender_type TEXT NOT NULL,
    sender_id TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    attachment_document_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    read_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_client_portal_messages_tenant_matter_created
    ON client_portal_messages (tenant_id, matter_id, created_at);

CREATE TABLE IF NOT EXISTS client_portal_appointments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'proposto',
    location TEXT NOT NULL DEFAULT '',
    video_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_client_portal_appointments_tenant_matter
    ON client_portal_appointments (tenant_id, matter_id, starts_at);

CREATE TABLE IF NOT EXISTS client_portal_notifications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'info',
    priority TEXT NOT NULL DEFAULT 'normale',
    href TEXT NOT NULL DEFAULT '',
    read_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_client_portal_notifications_tenant_client
    ON client_portal_notifications (tenant_id, client_id, read_at, created_at);

CREATE TABLE IF NOT EXISTS client_portal_questionnaires (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'aperto',
    questions_json TEXT NOT NULL DEFAULT '[]',
    responses_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_client_portal_questionnaires_tenant_matter
    ON client_portal_questionnaires (tenant_id, matter_id, status);

CREATE TABLE IF NOT EXISTS client_portal_surveys (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    rating INTEGER NOT NULL DEFAULT 0,
    comment TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_client_portal_surveys_tenant_matter
    ON client_portal_surveys (tenant_id, matter_id, submitted_at);

CREATE TABLE IF NOT EXISTS client_portal_evidence_packs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'preparato',
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_client_portal_evidence_packs_tenant_matter
    ON client_portal_evidence_packs (tenant_id, matter_id, created_at);

CREATE TABLE IF NOT EXISTS client_portal_settings (
    tenant_id TEXT PRIMARY KEY,
    settings_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS client_portal_push_subscriptions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    endpoint_hash TEXT NOT NULL,
    subscription_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'attiva',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_client_portal_push_subscriptions_unique
    ON client_portal_push_subscriptions (tenant_id, client_id, endpoint_hash);

CREATE TABLE IF NOT EXISTS client_portal_audit_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL DEFAULT '',
    resource_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_client_portal_audit_events_tenant_created
    ON client_portal_audit_events (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_client_portal_audit_events_tenant_resource
    ON client_portal_audit_events (tenant_id, resource_type, resource_id);
