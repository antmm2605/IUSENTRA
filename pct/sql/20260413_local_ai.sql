PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS local_ai_runtime (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL,
    api_base_url TEXT NOT NULL DEFAULT 'http://127.0.0.1:11434/api',
    ollama_version TEXT,
    install_path TEXT,
    models_path TEXT,
    hardware_profile TEXT NOT NULL DEFAULT 'weak',
    os_version TEXT,
    ram_gb REAL,
    disk_free_gb REAL,
    cpu_name TEXT,
    gpu_vendor TEXT,
    gpu_name TEXT,
    last_health_check_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_ai_models (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    model_name TEXT NOT NULL,
    install_state TEXT NOT NULL,
    size_bytes INTEGER,
    context_window INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_verified_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS rag_documents (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT,
    practice_id TEXT,
    title TEXT,
    file_path TEXT,
    mime_type TEXT,
    sha256 TEXT NOT NULL,
    language TEXT,
    parse_state TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    last_indexed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_documents_source
ON rag_documents(source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_rag_documents_practice
ON rag_documents(practice_id, updated_at);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    practice_id TEXT,
    section_type TEXT,
    ordinal INTEGER NOT NULL,
    page_from INTEGER,
    page_to INTEGER,
    token_estimate INTEGER,
    text TEXT NOT NULL,
    metadata_json TEXT,
    embedding_state TEXT NOT NULL DEFAULT 'pending',
    embedding_json TEXT,
    embedding_dimensions INTEGER,
    embedding_provider TEXT,
    embedding_model TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_document
ON rag_chunks(document_id, ordinal);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_practice
ON rag_chunks(practice_id, ordinal);

CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_state
ON rag_chunks(embedding_state, updated_at);

CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
    id UNINDEXED,
    document_id UNINDEXED,
    practice_id UNINDEXED,
    text,
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS rag_chunks_ai AFTER INSERT ON rag_chunks BEGIN
    INSERT INTO rag_chunks_fts(rowid, id, document_id, practice_id, text)
    VALUES (new.rowid, new.id, new.document_id, new.practice_id, new.text);
END;

-- Nota: rag_chunks_fts è una FTS5 normale (non external-content), quindi la
-- rimozione va fatta con DELETE ... WHERE rowid: il comando speciale 'delete'
-- è valido solo per tabelle contentless/external-content e qui solleva
-- "SQL logic error", bloccando la re-indicizzazione dei documenti modificati.
CREATE TRIGGER IF NOT EXISTS rag_chunks_ad AFTER DELETE ON rag_chunks BEGIN
    DELETE FROM rag_chunks_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS rag_chunks_au
AFTER UPDATE OF id, document_id, practice_id, text ON rag_chunks BEGIN
    DELETE FROM rag_chunks_fts WHERE rowid = old.rowid;
    INSERT INTO rag_chunks_fts(rowid, id, document_id, practice_id, text)
    VALUES (new.rowid, new.id, new.document_id, new.practice_id, new.text);
END;

CREATE TABLE IF NOT EXISTS rag_jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    target_id TEXT,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    error_text TEXT
);

CREATE TABLE IF NOT EXISTS rag_query_logs (
    id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_type TEXT NOT NULL,
    top_k INTEGER NOT NULL,
    duration_ms INTEGER,
    load_duration_ms INTEGER,
    prompt_eval_count INTEGER,
    eval_count INTEGER,
    retrieved_ids_json TEXT,
    created_at TEXT NOT NULL
);

INSERT OR IGNORE INTO local_ai_runtime (
    id, status, api_base_url, hardware_profile, created_at, updated_at
) VALUES (
    1, 'missing', 'http://127.0.0.1:11434/api', 'weak', datetime('now'), datetime('now')
);
