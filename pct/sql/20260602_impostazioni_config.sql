-- Mirror governato delle Impostazioni studio su SQLite.
-- Fonte runtime: pct.impostazioni_config_repository.

CREATE TABLE IF NOT EXISTS settings_config (
    section TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'config_studio',
    secret_fields_json TEXT NOT NULL DEFAULT '[]',
    dati_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_settings_config_updated ON settings_config(updated_at);
