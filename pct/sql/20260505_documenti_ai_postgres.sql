-- Documenti AI Fascicolo - schema PostgreSQL
-- Migrazione idempotente e non distruttiva.

CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    safe_filename TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'doc', 'txt', 'xml', 'json', 'csv', 'html', 'htm', 'rtf', 'odt', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp', 'gif', 'eml', 'msg', 'zip', 'p7m', 'pm7', 'bin')),
    mime_type TEXT,
    size_bytes BIGINT NOT NULL DEFAULT 0,
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
    document_id TEXT NOT NULL REFERENCES fascicolo_documenti_ai(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('upload', 'generated', 'assistant_edit', 'user_accept', 'user_reject', 'import')),
    storage_path TEXT NOT NULL,
    extracted_text_path TEXT,
    pdf_preview_path TEXT,
    sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_versioni_doc
    ON fascicolo_documenti_ai_versioni (tenant_id, fascicolo_id, document_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_versioni_numero
    ON fascicolo_documenti_ai_versioni (document_id, version_number);

CREATE TABLE IF NOT EXISTS fascicolo_documenti_ai_testi (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    document_id TEXT NOT NULL REFERENCES fascicolo_documenti_ai(id) ON DELETE CASCADE,
    version_id TEXT NOT NULL REFERENCES fascicolo_documenti_ai_versioni(id) ON DELETE CASCADE,
    extraction_engine TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    pages_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings_json JSONB,
    created_at TEXT NOT NULL
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
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_audit_doc
    ON fascicolo_documenti_ai_audit (tenant_id, fascicolo_id, document_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_documenti_ai_audit_evento
    ON fascicolo_documenti_ai_audit (event_type, created_at);

DO $$
DECLARE
    check_name TEXT;
BEGIN
    FOR check_name IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'fascicolo_documenti_ai'
          AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) LIKE '%file_type%'
    LOOP
        EXECUTE format('ALTER TABLE fascicolo_documenti_ai DROP CONSTRAINT IF EXISTS %I', check_name);
    END LOOP;

    ALTER TABLE fascicolo_documenti_ai
        ADD CONSTRAINT fascicolo_documenti_ai_file_type_check
        CHECK (file_type IN ('pdf', 'docx', 'doc', 'txt', 'xml', 'json', 'csv', 'html', 'htm', 'rtf', 'odt', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp', 'gif', 'eml', 'msg', 'zip', 'p7m', 'pm7', 'bin'));
END $$;
