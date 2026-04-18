CREATE TABLE IF NOT EXISTS telematico_repository_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS telematico_catalog_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    catalog_version TEXT NOT NULL DEFAULT '',
    schema_version TEXT NOT NULL DEFAULT '',
    pst_webservices_doc_version TEXT NOT NULL DEFAULT '',
    pst_webservices_wsdl_catalog_version TEXT NOT NULL DEFAULT '',
    pst_dm44_specifiche_revision TEXT NOT NULL DEFAULT '',
    busta_max_bytes INTEGER NOT NULL DEFAULT 0,
    busta_max_mb INTEGER NOT NULL DEFAULT 0,
    catalog_sources_json TEXT NOT NULL DEFAULT '[]',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_methods_repository (
    method_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    page INTEGER NOT NULL DEFAULT 0,
    current_support TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_wsdl_modules_repository (
    module_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_xsd_channels_repository (
    channel_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    area TEXT NOT NULL DEFAULT '',
    download_page_url TEXT NOT NULL DEFAULT '',
    package_name TEXT NOT NULL DEFAULT '',
    package_url TEXT NOT NULL DEFAULT '',
    package_date TEXT NOT NULL DEFAULT '',
    changelog_name TEXT NOT NULL DEFAULT '',
    changelog_url TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    status_source_news_date TEXT NOT NULL DEFAULT '',
    status_source_news_url TEXT NOT NULL DEFAULT '',
    applies_to TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    production_ready INTEGER NOT NULL DEFAULT 0 CHECK (production_ready IN (0,1)),
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_catalog_sources_repository (
    source_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_sources_repository (
    source_id TEXT PRIMARY KEY,
    nome TEXT NOT NULL DEFAULT '',
    motore TEXT NOT NULL DEFAULT '',
    area TEXT NOT NULL DEFAULT '',
    official_url TEXT NOT NULL DEFAULT '',
    monitor_url TEXT NOT NULL DEFAULT '',
    connector_kind TEXT NOT NULL DEFAULT '',
    cadence TEXT NOT NULL DEFAULT '',
    formats_json TEXT NOT NULL DEFAULT '[]',
    capability TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_capabilities_repository (
    capability_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    support_level TEXT NOT NULL DEFAULT '',
    supports_live INTEGER NOT NULL DEFAULT 0 CHECK (supports_live IN (0,1)),
    auto_sync INTEGER NOT NULL DEFAULT 0 CHECK (auto_sync IN (0,1)),
    handoff_required INTEGER NOT NULL DEFAULT 0 CHECK (handoff_required IN (0,1)),
    requires_certificate INTEGER NOT NULL DEFAULT 0 CHECK (requires_certificate IN (0,1)),
    authentication_mode TEXT NOT NULL DEFAULT '',
    source_of_truth TEXT NOT NULL DEFAULT '',
    operational_text TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_rules_repository (
    rule_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    rule_text TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_actions_repository (
    action_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    supports_live INTEGER NOT NULL DEFAULT 0 CHECK (supports_live IN (0,1)),
    requires_certificate INTEGER NOT NULL DEFAULT 0 CHECK (requires_certificate IN (0,1)),
    handoff_required INTEGER NOT NULL DEFAULT 0 CHECK (handoff_required IN (0,1)),
    source_of_truth TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_wizard_sections_repository (
    section_id TEXT PRIMARY KEY,
    label TEXT NOT NULL DEFAULT '',
    icon TEXT NOT NULL DEFAULT '',
    colore TEXT NOT NULL DEFAULT '',
    descrizione TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS telematico_monitoring_repository (
    source_id TEXT PRIMARY KEY,
    nome TEXT NOT NULL DEFAULT '',
    area TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    status_code INTEGER NOT NULL DEFAULT 0,
    changed INTEGER NOT NULL DEFAULT 0 CHECK (changed IN (0,1)),
    last_check TEXT NOT NULL DEFAULT '',
    detected_version TEXT NOT NULL DEFAULT '',
    detected_package TEXT NOT NULL DEFAULT '',
    detected_package_date TEXT NOT NULL DEFAULT '',
    detected_status TEXT NOT NULL DEFAULT '',
    detected_news_date TEXT NOT NULL DEFAULT '',
    warning TEXT NOT NULL DEFAULT '',
    official_url TEXT NOT NULL DEFAULT '',
    monitor_url TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_telematico_methods_category
ON telematico_methods_repository(category, current_support, label);

CREATE INDEX IF NOT EXISTS idx_telematico_wsdl_category
ON telematico_wsdl_modules_repository(category, label);

CREATE INDEX IF NOT EXISTS idx_telematico_xsd_status
ON telematico_xsd_channels_repository(status, area, label);

CREATE INDEX IF NOT EXISTS idx_telematico_sources_area
ON telematico_sources_repository(motore, area, nome);

CREATE INDEX IF NOT EXISTS idx_telematico_capabilities_topic
ON telematico_capabilities_repository(topic, channel, support_level);

CREATE INDEX IF NOT EXISTS idx_telematico_rules_topic
ON telematico_rules_repository(topic, channel, severity);

CREATE INDEX IF NOT EXISTS idx_telematico_actions_topic
ON telematico_actions_repository(topic, channel, supports_live);

CREATE INDEX IF NOT EXISTS idx_telematico_monitoring_status
ON telematico_monitoring_repository(status, changed, source_id);
