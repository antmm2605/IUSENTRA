PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS normative_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_name TEXT,
    zip_path TEXT,
    xml_entry TEXT,
    tipo_atto TEXT,
    numero TEXT,
    data_atto TEXT,
    data_pubblicazione TEXT,
    titolo TEXT,
    urn TEXT,
    redazione_id TEXT,
    vigenza TEXT,
    xml_sha256 TEXT UNIQUE,
    topics TEXT,
    relevance_score REAL DEFAULT 0,
    is_relevant INTEGER DEFAULT 0,
    text_content TEXT,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS normative_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    article_number TEXT,
    article_title TEXT,
    article_text TEXT,
    topics TEXT,
    relevance_score REAL DEFAULT 0,
    embedding_id TEXT,
    FOREIGN KEY(document_id) REFERENCES normative_documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS normative_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    article_id INTEGER,
    chunk_key TEXT UNIQUE,
    chunk_text TEXT NOT NULL,
    metadata_json TEXT,
    embedding_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES normative_documents(id) ON DELETE CASCADE,
    FOREIGN KEY(article_id) REFERENCES normative_articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS normative_sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_dir TEXT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    zip_files INTEGER NOT NULL DEFAULT 0,
    xml_seen INTEGER NOT NULL DEFAULT 0,
    documents_imported INTEGER NOT NULL DEFAULT 0,
    chunks_written INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    report_json TEXT NOT NULL DEFAULT '{}'
);

CREATE VIEW IF NOT EXISTS normattiva_documents AS SELECT * FROM normative_documents;
CREATE VIEW IF NOT EXISTS normattiva_articles AS SELECT * FROM normative_articles;
CREATE VIEW IF NOT EXISTS normattiva_chunks AS SELECT * FROM normative_chunks;

CREATE INDEX IF NOT EXISTS idx_normative_documents_collection ON normative_documents(collection_name);
CREATE INDEX IF NOT EXISTS idx_normative_documents_topics ON normative_documents(topics);
CREATE INDEX IF NOT EXISTS idx_normative_articles_document ON normative_articles(document_id);
CREATE INDEX IF NOT EXISTS idx_normative_chunks_document ON normative_chunks(document_id);
