-- Shared public directory only. No case, client, credentials or private attachments.
-- Deliberately portable: the same migration runs on SQLite and PostgreSQL.
CREATE TABLE IF NOT EXISTS mediazione_organismi (
    registration_number TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    website TEXT NOT NULL DEFAULT '',
    registry_source TEXT NOT NULL,
    registry_checked_at TEXT NOT NULL,
    record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mediazione_active ON mediazione_organismi(active, name);
CREATE TABLE IF NOT EXISTS mediazione_site_checks (
    registration_number TEXT PRIMARY KEY REFERENCES mediazione_organismi(registration_number),
    checked_at TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mediazione_directory_audit (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    action TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mediazione_office_snapshots (
    registration_number TEXT PRIMARY KEY REFERENCES mediazione_organismi(registration_number),
    checked_at TEXT NOT NULL,
    source_url TEXT NOT NULL,
    expected_count INTEGER NOT NULL,
    pages INTEGER NOT NULL,
    content_sha256 TEXT NOT NULL,
    offices_json TEXT NOT NULL
);
-- Evidence of public-channel research. Discovery never authorizes a submission.
CREATE TABLE IF NOT EXISTS mediazione_channel_checks (
    registration_number TEXT PRIMARY KEY REFERENCES mediazione_organismi(registration_number),
    checked_at TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL
);
-- Append-only research evidence and resumable, leased refreshes. No legal sends.
CREATE TABLE IF NOT EXISTS mediazione_source_history (
    id TEXT PRIMARY KEY,
    registration_number TEXT NOT NULL REFERENCES mediazione_organismi(registration_number),
    checked_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    material_sha256 TEXT NOT NULL,
    outcome TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mediazione_source_history ON mediazione_source_history(registration_number, checked_at);
CREATE TABLE IF NOT EXISTS mediazione_source_state (
    registration_number TEXT PRIMARY KEY REFERENCES mediazione_organismi(registration_number),
    last_success_id TEXT NOT NULL DEFAULT '',
    last_attempt_id TEXT NOT NULL DEFAULT '',
    last_change_at TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mediazione_source_jobs (
    registration_number TEXT PRIMARY KEY REFERENCES mediazione_organismi(registration_number),
    input_sha256 TEXT NOT NULL,
    research_version TEXT NOT NULL,
    due_at TEXT NOT NULL,
    lease_token TEXT NOT NULL DEFAULT '',
    lease_until TEXT NOT NULL DEFAULT '',
    failures INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_mediazione_source_due ON mediazione_source_jobs(due_at, lease_until);
