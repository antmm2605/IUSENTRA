-- Stesso contratto SQLite: isolamento studio e aggiornamenti per record.
CREATE TABLE IF NOT EXISTS condivisioni_records (
    tenant_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    record_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_key, kind, record_key)
);
CREATE TABLE IF NOT EXISTS condivisioni_bootstrap (
    tenant_key TEXT PRIMARY KEY,
    bootstrap_source TEXT NOT NULL,
    initialized_at TEXT NOT NULL
);
