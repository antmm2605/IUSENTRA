-- Migrazione Sito Studio Builder Pro (SQLite)
-- Le colonne su site_studio vengono aggiunte in modo idempotente dal repository,
-- per compatibilita' con SQLite che non supporta ADD COLUMN IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS site_theme_preset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    preview_image_url TEXT NOT NULL DEFAULT '',
    tokens_json TEXT NOT NULL DEFAULT '{}',
    blocks_seed_json TEXT NOT NULL DEFAULT '[]',
    is_builtin INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_design_revision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_design_revision_site ON site_design_revision(site_id, created_at);
