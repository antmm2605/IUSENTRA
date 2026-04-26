-- Migrazione Sito Studio Builder Pro (PostgreSQL)

ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS theme_template TEXT NOT NULL DEFAULT 'classic_legal';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS theme_variant TEXT NOT NULL DEFAULT 'default';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS design_tokens_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS typography_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS layout_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS effects_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS custom_css TEXT NOT NULL DEFAULT '';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS cookie_banner_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS analytics_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS analytics_provider TEXT NOT NULL DEFAULT '';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS analytics_id TEXT NOT NULL DEFAULT '';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS seo_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS legal_disclaimer TEXT NOT NULL DEFAULT '';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS privacy_url TEXT NOT NULL DEFAULT '';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS cookie_policy_url TEXT NOT NULL DEFAULT '';
ALTER TABLE site_studio ADD COLUMN IF NOT EXISTS accessibility_statement_url TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS site_theme_preset (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    preview_image_url TEXT NOT NULL DEFAULT '',
    tokens_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    blocks_seed_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_builtin BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_design_revision (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL REFERENCES site_studio(id) ON DELETE CASCADE,
    label TEXT NOT NULL DEFAULT '',
    snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_design_revision_site ON site_design_revision(site_id, created_at);

CREATE TABLE IF NOT EXISTS site_asset (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL REFERENCES site_studio(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    alt_text TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'generale',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    mime_type TEXT NOT NULL DEFAULT '',
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_asset_site ON site_asset(site_id, created_at);

CREATE TABLE IF NOT EXISTS site_ai_article_job (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL REFERENCES site_studio(id) ON DELETE CASCADE,
    topic TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_checklist_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft_generated',
    article_id BIGINT NOT NULL DEFAULT 0,
    image_prompt TEXT NOT NULL DEFAULT '',
    image_asset_id BIGINT NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_site_ai_article_job_site ON site_ai_article_job(site_id, created_at);
