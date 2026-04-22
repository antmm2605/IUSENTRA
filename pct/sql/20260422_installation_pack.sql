CREATE TABLE IF NOT EXISTS installation_product_pack_manifest (
    manifest_id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    version TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    signature TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS installation_studio_local_pack_manifest (
    studio_slug TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    studio_id TEXT NOT NULL,
    studio_nome TEXT NOT NULL DEFAULT '',
    database_backend TEXT NOT NULL DEFAULT '',
    signature TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS installation_update_pack_manifest (
    manifest_id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    from_version TEXT NOT NULL DEFAULT '',
    to_version TEXT NOT NULL DEFAULT '',
    installation_id TEXT NOT NULL,
    signature TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_installation_product_pack_version
    ON installation_product_pack_manifest(version, updated_at);

CREATE INDEX IF NOT EXISTS idx_installation_studio_local_backend
    ON installation_studio_local_pack_manifest(database_backend, studio_nome);

CREATE INDEX IF NOT EXISTS idx_installation_update_pack_version
    ON installation_update_pack_manifest(to_version, updated_at);
