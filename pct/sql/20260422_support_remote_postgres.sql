CREATE TABLE IF NOT EXISTS support_session (
    id BIGSERIAL PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    client_token TEXT NOT NULL UNIQUE,
    studio_slug TEXT NOT NULL DEFAULT '',
    studio_nome TEXT NOT NULL DEFAULT '',
    practice_id TEXT NOT NULL DEFAULT '',
    practice_label TEXT NOT NULL DEFAULT '',
    client_id TEXT NOT NULL DEFAULT '',
    customer_name TEXT NOT NULL DEFAULT '',
    customer_email TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    assigned_to TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    consent_screen BOOLEAN NOT NULL DEFAULT FALSE,
    consent_audio BOOLEAN NOT NULL DEFAULT FALSE,
    consent_chat BOOLEAN NOT NULL DEFAULT TRUE,
    consent_advanced_control BOOLEAN NOT NULL DEFAULT FALSE,
    advanced_control_requested BOOLEAN NOT NULL DEFAULT FALSE,
    advanced_control_approved BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TEXT NOT NULL DEFAULT '',
    ended_at TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_support_session_status ON support_session(status);
CREATE INDEX IF NOT EXISTS idx_support_session_studio_slug ON support_session(studio_slug);
CREATE INDEX IF NOT EXISTS idx_support_session_practice_id ON support_session(practice_id);
CREATE INDEX IF NOT EXISTS idx_support_session_customer_name ON support_session(customer_name);
CREATE INDEX IF NOT EXISTS idx_support_session_created_at ON support_session(created_at DESC);

CREATE TABLE IF NOT EXISTS support_event (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES support_session(id) ON DELETE CASCADE,
    public_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_role TEXT NOT NULL DEFAULT '',
    actor_name TEXT NOT NULL DEFAULT '',
    story_line TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_support_event_session_id ON support_event(session_id);
CREATE INDEX IF NOT EXISTS idx_support_event_public_id ON support_event(public_id);
CREATE INDEX IF NOT EXISTS idx_support_event_type ON support_event(event_type);
CREATE INDEX IF NOT EXISTS idx_support_event_created_at ON support_event(created_at DESC);
