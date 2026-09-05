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
