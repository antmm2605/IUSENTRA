PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS applicazioni_repository_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applicazioni_sections_repository (
    section_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    icon TEXT NOT NULL DEFAULT '',
    accent TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    default_status TEXT NOT NULL DEFAULT '',
    default_endpoint TEXT NOT NULL DEFAULT '',
    default_cta_label TEXT NOT NULL DEFAULT '',
    default_params_json TEXT NOT NULL DEFAULT '{}',
    items_json TEXT NOT NULL DEFAULT '[]',
    items_count INTEGER NOT NULL DEFAULT 0,
    workspace_kind TEXT NOT NULL DEFAULT '',
    workspace_kind_label TEXT NOT NULL DEFAULT '',
    workspace_kind_badge_class TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS applicazioni_catalog_repository (
    app_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    section_id TEXT NOT NULL DEFAULT '',
    section_title TEXT NOT NULL DEFAULT '',
    section_icon TEXT NOT NULL DEFAULT '',
    section_accent TEXT NOT NULL DEFAULT '',
    section_description TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    status_label TEXT NOT NULL DEFAULT '',
    status_description TEXT NOT NULL DEFAULT '',
    access_mode TEXT NOT NULL DEFAULT '',
    access_mode_label TEXT NOT NULL DEFAULT '',
    access_mode_description TEXT NOT NULL DEFAULT '',
    endpoint TEXT NOT NULL DEFAULT '',
    params_json TEXT NOT NULL DEFAULT '{}',
    cta_label TEXT NOT NULL DEFAULT '',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    workspace_kind TEXT NOT NULL DEFAULT '',
    workspace_kind_label TEXT NOT NULL DEFAULT '',
    featured INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0,1)),
    available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0,1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    requires_guided_flow INTEGER NOT NULL DEFAULT 0 CHECK (requires_guided_flow IN (0,1)),
    requires_login INTEGER NOT NULL DEFAULT 1 CHECK (requires_login IN (0,1)),
    requires_cliente INTEGER NOT NULL DEFAULT 0 CHECK (requires_cliente IN (0,1)),
    requires_fascicolo INTEGER NOT NULL DEFAULT 0 CHECK (requires_fascicolo IN (0,1)),
    requires_telematic_context INTEGER NOT NULL DEFAULT 0 CHECK (requires_telematic_context IN (0,1)),
    domain_area TEXT NOT NULL DEFAULT '',
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    suggested_when_json TEXT NOT NULL DEFAULT '[]',
    blocked_if_json TEXT NOT NULL DEFAULT '[]',
    health_state TEXT NOT NULL DEFAULT '',
    detail_path TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS applicazioni_status_repository (
    status_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    badge_class TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS applicazioni_access_repository (
    access_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    badge_class TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS applicazioni_section_kinds_repository (
    section_id TEXT PRIMARY KEY,
    workspace_kind TEXT NOT NULL DEFAULT '',
    workspace_kind_label TEXT NOT NULL DEFAULT '',
    workspace_kind_badge_class TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS applicazioni_featured_repository (
    app_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    section_id TEXT NOT NULL DEFAULT '',
    section_title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    status_label TEXT NOT NULL DEFAULT '',
    access_mode TEXT NOT NULL DEFAULT '',
    access_mode_label TEXT NOT NULL DEFAULT '',
    endpoint TEXT NOT NULL DEFAULT '',
    params_json TEXT NOT NULL DEFAULT '{}',
    cta_label TEXT NOT NULL DEFAULT '',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    workspace_kind TEXT NOT NULL DEFAULT '',
    workspace_kind_label TEXT NOT NULL DEFAULT '',
    featured_default_slug INTEGER NOT NULL DEFAULT 0 CHECK (featured_default_slug IN (0,1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS applicazioni_statistics_repository (
    stats_id TEXT PRIMARY KEY,
    totale INTEGER NOT NULL DEFAULT 0,
    per_stato_json TEXT NOT NULL DEFAULT '{}',
    per_sezione_json TEXT NOT NULL DEFAULT '{}',
    per_tipo_json TEXT NOT NULL DEFAULT '{}',
    per_modalita_json TEXT NOT NULL DEFAULT '{}',
    sezioni_attive INTEGER NOT NULL DEFAULT 0,
    primo_piano INTEGER NOT NULL DEFAULT 0,
    accessi_diretti INTEGER NOT NULL DEFAULT 0,
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_applicazioni_catalog_section
ON applicazioni_catalog_repository(section_id, status, access_mode, sort_order);

CREATE INDEX IF NOT EXISTS idx_applicazioni_catalog_kind
ON applicazioni_catalog_repository(workspace_kind, access_mode, featured, sort_order);

CREATE INDEX IF NOT EXISTS idx_applicazioni_featured_section
ON applicazioni_featured_repository(section_id, access_mode, sort_order);

COMMIT;
