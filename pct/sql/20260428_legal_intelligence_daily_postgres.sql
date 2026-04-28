-- Motore giornaliero Legal Intelligence - PostgreSQL

CREATE TABLE IF NOT EXISTS legal_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    official BOOLEAN NOT NULL DEFAULT TRUE,
    apply_mode TEXT NOT NULL DEFAULT 'manual',
    impact_areas_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    user_agent_note TEXT NOT NULL DEFAULT '',
    etag TEXT NOT NULL DEFAULT '',
    last_modified TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT 'never',
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_source_snapshots (
    id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
    fetched_at TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    status_code INTEGER NOT NULL DEFAULT 0,
    etag TEXT NOT NULL DEFAULT '',
    last_modified TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL,
    normalized_text TEXT NOT NULL DEFAULT '',
    raw_path TEXT NOT NULL DEFAULT '',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_legal_source_snapshots_source
    ON legal_source_snapshots(source_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS legal_updates (
    id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
    detected_at TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    old_sha256 TEXT NOT NULL DEFAULT '',
    new_sha256 TEXT NOT NULL DEFAULT '',
    diff_text TEXT NOT NULL DEFAULT '',
    impact_areas_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    apply_mode TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'pending_review',
    applied_at TEXT NOT NULL DEFAULT '',
    application_note TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'media',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_legal_updates_source_hash UNIQUE (source_id, new_sha256)
);

CREATE INDEX IF NOT EXISTS idx_legal_updates_status
    ON legal_updates(status, detected_at DESC);

CREATE TABLE IF NOT EXISTS legal_intelligence_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    sources_checked INTEGER NOT NULL DEFAULT 0,
    updates_detected INTEGER NOT NULL DEFAULT 0,
    updates_applied INTEGER NOT NULL DEFAULT 0,
    pending_review INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    log_json JSONB NOT NULL DEFAULT '[]'::jsonb
);
