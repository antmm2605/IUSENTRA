-- Practice Engine / Regia Operativa Fascicolo - PostgreSQL

CREATE TABLE IF NOT EXISTS practice_profiles (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    area TEXT,
    channel TEXT,
    registry TEXT,
    workflow_code TEXT,
    practice_id TEXT,
    procedure_code TEXT,
    version TEXT NOT NULL DEFAULT '1.0',
    source TEXT NOT NULL DEFAULT 'legal_platform_catalog',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    applied_at TIMESTAMPTZ NOT NULL,
    applied_by TEXT,
    manual_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_practice_profiles_fascicolo ON practice_profiles(fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_practice_profiles_code ON practice_profiles(code);

CREATE TABLE IF NOT EXISTS practice_requirements (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    requirement_key TEXT NOT NULL,
    label TEXT NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    blocking BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT,
    message TEXT,
    suggested_action TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_practice_requirements_fascicolo ON practice_requirements(fascicolo_id);

CREATE TABLE IF NOT EXISTS practice_document_slots (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    slot_key TEXT NOT NULL,
    label TEXT NOT NULL,
    type TEXT NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    blocking BOOLEAN NOT NULL DEFAULT TRUE,
    document_id TEXT,
    status TEXT NOT NULL,
    validators_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_validation_at TIMESTAMPTZ,
    message TEXT,
    suggested_action TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(fascicolo_id, slot_key)
);

CREATE INDEX IF NOT EXISTS idx_practice_document_slots_fascicolo ON practice_document_slots(fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_practice_document_slots_document ON practice_document_slots(document_id);

CREATE TABLE IF NOT EXISTS practice_checklist_items (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    item_key TEXT NOT NULL,
    label TEXT NOT NULL,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    blocking BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL,
    message TEXT,
    suggested_action TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    source TEXT,
    UNIQUE(fascicolo_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_practice_checklist_items_fascicolo ON practice_checklist_items(fascicolo_id);

CREATE TABLE IF NOT EXISTS practice_validation_results (
    id BIGSERIAL PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    slot_key TEXT,
    validator_key TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    technical_detail TEXT,
    suggested_action TEXT,
    source TEXT,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_practice_validation_results_fascicolo ON practice_validation_results(fascicolo_id, scope);

CREATE TABLE IF NOT EXISTS practice_state_history (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    state TEXT NOT NULL,
    actor TEXT,
    reason TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_practice_state_history_fascicolo ON practice_state_history(fascicolo_id, created_at);

CREATE TABLE IF NOT EXISTS deposit_sessions (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    transport_mode TEXT NOT NULL DEFAULT 'non_configurato',
    simulated BOOLEAN NOT NULL DEFAULT FALSE,
    real_transport BOOLEAN NOT NULL DEFAULT FALSE,
    predeposit_status TEXT,
    messages_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    acquired_at TIMESTAMPTZ,
    final_receipt_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_deposit_sessions_fascicolo ON deposit_sessions(fascicolo_id, created_at);

CREATE TABLE IF NOT EXISTS deposit_receipts (
    id TEXT PRIMARY KEY,
    deposit_session_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    receipt_type TEXT NOT NULL,
    status TEXT NOT NULL,
    positive BOOLEAN NOT NULL DEFAULT FALSE,
    source TEXT NOT NULL,
    original_name TEXT,
    original_hash_sha256 TEXT NOT NULL,
    original_path TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMPTZ NOT NULL,
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_deposit_receipts_session ON deposit_receipts(deposit_session_id);
CREATE INDEX IF NOT EXISTS idx_deposit_receipts_fascicolo ON deposit_receipts(fascicolo_id);

CREATE TABLE IF NOT EXISTS deposit_timeline_events (
    id TEXT PRIMARY KEY,
    deposit_session_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    evidence_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_deposit_timeline_events_session ON deposit_timeline_events(deposit_session_id, created_at);

CREATE TABLE IF NOT EXISTS evidence_packs (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    deposit_session_id TEXT NOT NULL,
    path TEXT NOT NULL,
    hash_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    available BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_evidence_packs_deposit ON evidence_packs(deposit_session_id);

CREATE TABLE IF NOT EXISTS practice_audit_events (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT,
    message TEXT,
    reason TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_practice_audit_events_fascicolo
    ON practice_audit_events(fascicolo_id, created_at);
