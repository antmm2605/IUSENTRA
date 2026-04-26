PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS official_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    connector TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 50,
    type TEXT NOT NULL DEFAULT '',
    refresh TEXT NOT NULL DEFAULT 'manual',
    base_url TEXT NOT NULL DEFAULT '',
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS official_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    original_url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    document_type TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL DEFAULT '',
    raw_path TEXT NOT NULL DEFAULT '',
    text_path TEXT NOT NULL DEFAULT '',
    hash_sha256 TEXT NOT NULL UNIQUE,
    document_date TEXT,
    published_at TEXT,
    numero TEXT NOT NULL DEFAULT '',
    serie TEXT NOT NULL DEFAULT '',
    materia TEXT NOT NULL DEFAULT '',
    text_content TEXT,
    acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    index_status TEXT NOT NULL DEFAULT 'pending',
    license TEXT NOT NULL DEFAULT '',
    topics_json TEXT NOT NULL DEFAULT '[]',
    relevance_score REAL NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(source_id) REFERENCES official_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS official_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    materia TEXT NOT NULL DEFAULT '',
    token_estimate INTEGER NOT NULL DEFAULT 0,
    reliability_level TEXT NOT NULL DEFAULT 'ufficiale',
    topics_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES official_documents(id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES official_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS official_sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    documents_found INTEGER NOT NULL DEFAULT 0,
    documents_saved INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(source_id) REFERENCES official_sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS official_source_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    run_id INTEGER,
    url TEXT NOT NULL DEFAULT '',
    error_type TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(source_id) REFERENCES official_sources(id) ON DELETE CASCADE,
    FOREIGN KEY(run_id) REFERENCES official_sync_runs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_official_documents_source ON official_documents(source_id);
CREATE INDEX IF NOT EXISTS idx_official_documents_materia ON official_documents(materia);
CREATE INDEX IF NOT EXISTS idx_official_documents_published ON official_documents(published_at);
CREATE INDEX IF NOT EXISTS idx_official_chunks_source ON official_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_official_chunks_document ON official_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_official_chunks_materia ON official_chunks(materia);
