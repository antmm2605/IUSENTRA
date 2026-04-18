CREATE TABLE IF NOT EXISTS legal_repository_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS legal_runtime_state (
    state_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS legal_sources_repository (
    source_id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    motore TEXT NOT NULL,
    area TEXT NOT NULL,
    official_url TEXT NOT NULL DEFAULT '',
    monitor_url TEXT NOT NULL DEFAULT '',
    connector_kind TEXT NOT NULL DEFAULT '',
    cadence TEXT NOT NULL DEFAULT '',
    formats_json TEXT NOT NULL DEFAULT '[]',
    capability TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_engines_repository (
    engine_id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    short_name TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    output TEXT NOT NULL,
    value TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_keyword_to_engine (
    keyword TEXT PRIMARY KEY,
    engine_ids_json TEXT NOT NULL DEFAULT '[]',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_keyword_to_source (
    keyword TEXT PRIMARY KEY,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_engine_source_edges (
    engine_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    engine_name TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    area TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (engine_id, source_id)
);

CREATE TABLE IF NOT EXISTS legal_monitoring_repository (
    source_id TEXT PRIMARY KEY,
    nome TEXT NOT NULL DEFAULT '',
    area TEXT NOT NULL DEFAULT '',
    freshness TEXT NOT NULL DEFAULT '',
    last_check TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    status_code INTEGER NOT NULL DEFAULT 0,
    changed INTEGER NOT NULL DEFAULT 0 CHECK (changed IN (0,1)),
    detected_version TEXT NOT NULL DEFAULT '',
    detected_reference TEXT NOT NULL DEFAULT '',
    detected_document_url TEXT NOT NULL DEFAULT '',
    detected_package TEXT NOT NULL DEFAULT '',
    detected_package_date TEXT NOT NULL DEFAULT '',
    detected_status TEXT NOT NULL DEFAULT '',
    detected_news_date TEXT NOT NULL DEFAULT '',
    detected_news_url TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    warning TEXT NOT NULL DEFAULT '',
    official_url TEXT NOT NULL DEFAULT '',
    monitor_url TEXT NOT NULL DEFAULT '',
    connector_kind TEXT NOT NULL DEFAULT '',
    cadence TEXT NOT NULL DEFAULT '',
    formats_json TEXT NOT NULL DEFAULT '[]',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_alert_repository (
    alert_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    motore_id TEXT NOT NULL DEFAULT '',
    alert_type TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    official_url TEXT NOT NULL DEFAULT '',
    related_entity_type TEXT NOT NULL DEFAULT '',
    related_entity_id TEXT NOT NULL DEFAULT '',
    acknowledged INTEGER NOT NULL DEFAULT 0 CHECK (acknowledged IN (0,1)),
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_audit_repository (
    trace_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    query TEXT NOT NULL DEFAULT '',
    user_name TEXT NOT NULL DEFAULT '',
    engine_ids_json TEXT NOT NULL DEFAULT '[]',
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    source_snapshots_json TEXT NOT NULL DEFAULT '[]',
    ai_model TEXT NOT NULL DEFAULT '',
    result_summary TEXT NOT NULL DEFAULT '',
    warning TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS legal_operational_repository (
    rule_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    scope TEXT NOT NULL,
    operational_text TEXT NOT NULL,
    deterministic INTEGER NOT NULL DEFAULT 1 CHECK (deterministic IN (0,1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_legal_sources_repository_area
ON legal_sources_repository(motore, area, nome);

CREATE INDEX IF NOT EXISTS idx_legal_engines_repository_name
ON legal_engines_repository(nome, short_name);

CREATE INDEX IF NOT EXISTS idx_legal_engine_source_edges_engine
ON legal_engine_source_edges(engine_id, source_id);

CREATE INDEX IF NOT EXISTS idx_legal_monitoring_repository_status
ON legal_monitoring_repository(status, freshness, source_id);

CREATE INDEX IF NOT EXISTS idx_legal_alert_repository_created
ON legal_alert_repository(created_at, severity, source_id);

CREATE INDEX IF NOT EXISTS idx_legal_audit_repository_created
ON legal_audit_repository(created_at);

CREATE INDEX IF NOT EXISTS idx_legal_operational_repository_scope
ON legal_operational_repository(scope, sort_order);
