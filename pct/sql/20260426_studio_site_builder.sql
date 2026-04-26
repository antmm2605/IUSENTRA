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

CREATE TABLE IF NOT EXISTS site_asset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    alt_text TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'generale',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    mime_type TEXT NOT NULL DEFAULT '',
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_asset_site ON site_asset(site_id, created_at);

CREATE TABLE IF NOT EXISTS site_ai_article_job (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    risk_checklist_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft_generated',
    article_id INTEGER NOT NULL DEFAULT 0,
    image_prompt TEXT NOT NULL DEFAULT '',
    image_asset_id INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES site_studio(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_ai_article_job_site ON site_ai_article_job(site_id, created_at);
