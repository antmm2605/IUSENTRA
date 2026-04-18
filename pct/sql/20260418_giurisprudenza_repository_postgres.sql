CREATE TABLE IF NOT EXISTS giurisprudenza_repository_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS giurisprudenza_runtime_state (
    state_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS giurisprudenza_sources_repository (
    source_id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    giurisdizione TEXT NOT NULL DEFAULT '',
    coverage TEXT NOT NULL DEFAULT '',
    official_url TEXT NOT NULL DEFAULT '',
    search_url TEXT NOT NULL DEFAULT '',
    access_mode TEXT NOT NULL DEFAULT '',
    sync_mode TEXT NOT NULL DEFAULT '',
    badge TEXT NOT NULL DEFAULT '',
    icon TEXT NOT NULL DEFAULT '',
    search_label TEXT NOT NULL DEFAULT '',
    supports_auto_sync INTEGER NOT NULL DEFAULT 0 CHECK (supports_auto_sync IN (0,1)),
    default_area TEXT NOT NULL DEFAULT '',
    default_grade TEXT NOT NULL DEFAULT '',
    license_note TEXT NOT NULL DEFAULT '',
    route_bias TEXT NOT NULL DEFAULT '',
    link_keywords_json TEXT NOT NULL DEFAULT '[]',
    judgment_count INTEGER NOT NULL DEFAULT 0,
    last_status TEXT NOT NULL DEFAULT '',
    last_check TEXT NOT NULL DEFAULT '',
    last_message TEXT NOT NULL DEFAULT '',
    last_imported INTEGER NOT NULL DEFAULT 0,
    last_updated INTEGER NOT NULL DEFAULT 0,
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS giurisprudenza_taxonomy_repository (
    taxon_id TEXT PRIMARY KEY,
    level_name TEXT NOT NULL,
    area_id TEXT NOT NULL DEFAULT '',
    area_title TEXT NOT NULL DEFAULT '',
    branch_title TEXT NOT NULL DEFAULT '',
    subbranch_title TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS giurisprudenza_usage_policy_repository (
    policy_id TEXT PRIMARY KEY,
    policy_type TEXT NOT NULL,
    policy_value TEXT NOT NULL,
    label TEXT NOT NULL,
    operational_text TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS giurisprudenza_sync_registry (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    giurisdizione TEXT NOT NULL DEFAULT '',
    access_mode TEXT NOT NULL DEFAULT '',
    sync_mode TEXT NOT NULL DEFAULT '',
    supports_auto_sync INTEGER NOT NULL DEFAULT 0 CHECK (supports_auto_sync IN (0,1)),
    judgment_count INTEGER NOT NULL DEFAULT 0,
    last_status TEXT NOT NULL DEFAULT '',
    last_check TEXT NOT NULL DEFAULT '',
    last_message TEXT NOT NULL DEFAULT '',
    imported INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    candidates INTEGER NOT NULL DEFAULT 0,
    handoff_required INTEGER NOT NULL DEFAULT 0 CHECK (handoff_required IN (0,1)),
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_giurisprudenza_sources_mode
ON giurisprudenza_sources_repository(access_mode, sync_mode, giurisdizione);

CREATE INDEX IF NOT EXISTS idx_giurisprudenza_taxonomy_level
ON giurisprudenza_taxonomy_repository(level_name, area_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_giurisprudenza_usage_policy_type
ON giurisprudenza_usage_policy_repository(policy_type, sort_order);

CREATE INDEX IF NOT EXISTS idx_giurisprudenza_sync_registry_status
ON giurisprudenza_sync_registry(last_status, last_check);
