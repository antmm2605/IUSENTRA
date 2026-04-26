-- Ricerca Studio globale - SQLite

CREATE TABLE IF NOT EXISTS global_search_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    subtitle TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    client_id TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    pratica_id TEXT NOT NULL DEFAULT '',
    source_module TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'studio',
    permission_scope TEXT NOT NULL DEFAULT 'studio',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    indexed_at TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT '',
    UNIQUE(tenant_id, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_global_search_tenant_type
    ON global_search_index(tenant_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_global_search_fascicolo
    ON global_search_index(tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_global_search_cliente
    ON global_search_index(tenant_id, client_id);

CREATE VIRTUAL TABLE IF NOT EXISTS global_search_index_fts USING fts5(
    title,
    subtitle,
    body,
    keywords,
    search_text,
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TABLE IF NOT EXISTS global_search_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    action TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
