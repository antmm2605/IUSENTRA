-- Adozione esplicita nell'archivio canonico dello studio, mai nelle GET.
CREATE TABLE IF NOT EXISTS termini_state (
    tenant_key TEXT PRIMARY KEY,
    revision BIGINT NOT NULL,
    source_sha256 TEXT NOT NULL,
    backup_reference TEXT NOT NULL,
    archive_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS termini_records (
    tenant_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    record_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    order_key TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_key, kind, record_key)
);
CREATE INDEX IF NOT EXISTS idx_termini_order
    ON termini_records (tenant_key, kind, order_key);
