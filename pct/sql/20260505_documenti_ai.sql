-- Documenti AI Fascicolo - schema SQLite
-- Migrazione idempotente e non distruttiva.

CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    safe_filename TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'doc', 'txt', 'xml', 'json', 'csv', 'html', 'htm', 'rtf', 'odt', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp', 'gif', 'eml', 'msg', 'zip', 'p7m', 'pm7', 'bin')),
    mime_type TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('uploaded', 'processing', 'ready', 'error', 'archived')),
    current_version_id TEXT,
    page_count INTEGER,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_tenant_fascicolo
    ON fascicolo_documenti_ai (tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_tenant_fascicolo_id
    ON fascicolo_documenti_ai (tenant_id, fascicolo_id, id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_sha256
    ON fascicolo_documenti_ai (sha256);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_status
    ON fascicolo_documenti_ai (status);

CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai_versioni (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('upload', 'generated', 'assistant_edit', 'user_accept', 'user_reject', 'import')),
    storage_path TEXT NOT NULL,
    extracted_text_path TEXT,
    pdf_preview_path TEXT,
    sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES fascicolo_documenti_ai(id) ON DELETE CASCADE,
    UNIQUE (document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_versioni_doc
    ON fascicolo_documenti_ai_versioni (tenant_id, fascicolo_id, document_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_versioni_numero
    ON fascicolo_documenti_ai_versioni (document_id, version_number);

CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai_testi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    extraction_engine TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    pages_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES fascicolo_documenti_ai(id) ON DELETE CASCADE,
    FOREIGN KEY (version_id) REFERENCES fascicolo_documenti_ai_versioni(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_testi_doc
    ON fascicolo_documenti_ai_testi (tenant_id, fascicolo_id, document_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_testi_versione
    ON fascicolo_documenti_ai_testi (version_id);

CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai_audit (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    document_id TEXT,
    version_id TEXT,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_audit_doc
    ON fascicolo_documenti_ai_audit (tenant_id, fascicolo_id, document_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_audit_evento
    ON fascicolo_documenti_ai_audit (event_type, created_at);
