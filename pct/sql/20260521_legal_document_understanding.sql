-- Legal Document Understanding, OCR forense, PEC ZIP e RAG Lex validato.
-- Migrazione SQLite tenant-aware. Il repository applica lo stesso schema
-- anche in runtime per ambienti file-based.

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT,
    parent_document_id TEXT,
    root_document_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_message_id TEXT,
    original_filename TEXT NOT NULL,
    normalized_filename TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL,
    security_status TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    version_type TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    author TEXT NOT NULL,
    reason TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    prev_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(document_id, version_number)
);

CREATE TABLE IF NOT EXISTS document_files (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    normalized_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    parent_document_id TEXT,
    root_pec_id TEXT,
    extraction_path_virtuale TEXT NOT NULL DEFAULT '',
    extraction_depth INTEGER NOT NULL DEFAULT 0,
    security_status TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_archive_children (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    parent_document_id TEXT NOT NULL,
    child_document_id TEXT NOT NULL,
    root_document_id TEXT NOT NULL,
    root_pec_id TEXT,
    extraction_path_virtuale TEXT NOT NULL,
    extraction_depth INTEGER NOT NULL,
    security_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_ocr_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    engine TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    language TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    confidence_document REAL NOT NULL DEFAULT 0,
    raw_text TEXT NOT NULL DEFAULT '',
    corrected_text TEXT NOT NULL DEFAULT '',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    errors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS document_ocr_tokens (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    ocr_run_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    token_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_json TEXT NOT NULL DEFAULT '{}',
    warning TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS document_classifications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    legal_area TEXT NOT NULL,
    macro_area TEXT NOT NULL,
    rito TEXT NOT NULL,
    fase TEXT NOT NULL,
    procedimento TEXT NOT NULL,
    portale_probabile TEXT NOT NULL,
    confidence REAL NOT NULL,
    motivation TEXT NOT NULL,
    signals_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_entities (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL NOT NULL,
    page INTEGER,
    bbox_json TEXT NOT NULL DEFAULT '{}',
    source_document_id TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_validations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    result TEXT NOT NULL,
    valid INTEGER NOT NULL DEFAULT 0,
    missing_critical_fields_json TEXT NOT NULL DEFAULT '[]',
    issues_json TEXT NOT NULL DEFAULT '[]',
    consistency_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_case_matches (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    matched_case_id TEXT,
    confidence REAL NOT NULL,
    matched_signals_json TEXT NOT NULL DEFAULT '[]',
    conflicts_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    date_value TEXT NOT NULL DEFAULT '',
    evidence_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS document_review_tasks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    fields_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    decision_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS evidence_audit_logs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS evidence_audit_logs_no_update
BEFORE UPDATE ON evidence_audit_logs
BEGIN
    SELECT RAISE(ABORT, 'evidence_audit_logs is append-only');
END;

CREATE TRIGGER IF NOT EXISTS evidence_audit_logs_no_delete
BEFORE DELETE ON evidence_audit_logs
BEGIN
    SELECT RAISE(ABORT, 'evidence_audit_logs is append-only');
END;

CREATE TABLE IF NOT EXISTS evidence_hash_chain (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proof_bundles (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    stored_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lex_index_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    chunks_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS lex_document_chunks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    text TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant_status ON documents(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_fascicolo ON documents(tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_document_files_doc ON document_files(tenant_id, document_id);
CREATE INDEX IF NOT EXISTS idx_archive_parent ON document_archive_children(tenant_id, parent_document_id);
CREATE INDEX IF NOT EXISTS idx_entities_doc ON legal_entities(tenant_id, document_id);
CREATE INDEX IF NOT EXISTS idx_events_doc ON document_events(tenant_id, document_id);
CREATE INDEX IF NOT EXISTS idx_lex_chunks_doc ON lex_document_chunks(tenant_id, document_id);
