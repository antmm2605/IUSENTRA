-- Editor AI - schema SQLite
-- Migrazione idempotente e non distruttiva.

CREATE TABLE IF NOT EXISTS fascicolo_editor_ai_atti (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    tipo_atto TEXT NOT NULL,
    template_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'in_review', 'approved', 'exported', 'archived')),
    editor_document_id TEXT NOT NULL,
    current_version_id TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_atti_tenant_fascicolo
    ON fascicolo_editor_ai_atti (tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_atti_editor_document
    ON fascicolo_editor_ai_atti (tenant_id, fascicolo_id, editor_document_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_atti_status
    ON fascicolo_editor_ai_atti (status);

CREATE TABLE IF NOT EXISTS fascicolo_editor_ai_versioni (
    id TEXT PRIMARY KEY,
    atto_ai_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('ai_generation', 'ai_edit', 'manual_edit', 'export')),
    editor_document_snapshot_json TEXT NOT NULL DEFAULT '{}',
    docx_path TEXT,
    pdf_path TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (atto_ai_id) REFERENCES fascicolo_editor_ai_atti(id) ON DELETE CASCADE,
    UNIQUE (atto_ai_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_versioni_atto
    ON fascicolo_editor_ai_versioni (tenant_id, fascicolo_id, atto_ai_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_versioni_numero
    ON fascicolo_editor_ai_versioni (atto_ai_id, version_number);

CREATE TABLE IF NOT EXISTS fascicolo_editor_ai_fonti (
    id TEXT PRIMARY KEY,
    atto_ai_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    document_id TEXT,
    page_number INTEGER,
    quote TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (atto_ai_id) REFERENCES fascicolo_editor_ai_atti(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_fonti_atto
    ON fascicolo_editor_ai_fonti (atto_ai_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_fonti_documento
    ON fascicolo_editor_ai_fonti (document_id);

CREATE TABLE IF NOT EXISTS fascicolo_editor_ai_modifiche (
    id TEXT PRIMARY KEY,
    atto_ai_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected', 'superseded')),
    operation_type TEXT NOT NULL CHECK (operation_type IN ('replace', 'insert_after', 'insert_before', 'delete', 'rewrite_section', 'add_section')),
    target_block_id TEXT,
    find_text TEXT,
    replace_text TEXT,
    insert_text TEXT,
    reason TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_by TEXT,
    resolved_at TEXT,
    FOREIGN KEY (atto_ai_id) REFERENCES fascicolo_editor_ai_atti(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_modifiche_atto_status
    ON fascicolo_editor_ai_modifiche (atto_ai_id, status);
CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_modifiche_versione
    ON fascicolo_editor_ai_modifiche (version_id);

CREATE TABLE IF NOT EXISTS fascicolo_editor_ai_audit (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    atto_ai_id TEXT,
    version_id TEXT,
    editor_document_id TEXT,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_audit_atto
    ON fascicolo_editor_ai_audit (tenant_id, fascicolo_id, atto_ai_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_editor_ai_audit_evento
    ON fascicolo_editor_ai_audit (event_type, created_at);
