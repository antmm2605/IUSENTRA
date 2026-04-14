PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS template_repository_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS template_repository (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL UNIQUE,
    codice TEXT,
    titolo TEXT NOT NULL,
    categoria TEXT,
    collezione TEXT,
    area TEXT,
    branca TEXT,
    sottobranca TEXT,
    microtema TEXT,
    fase TEXT,
    rito TEXT,
    grado TEXT,
    canale_telematico TEXT,
    profilo_deposito TEXT,
    builtin INTEGER NOT NULL DEFAULT 1 CHECK (builtin IN (0,1)),
    ordine INTEGER NOT NULL DEFAULT 9999,
    descrizione TEXT,
    note TEXT,
    search_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_template_repository_titolo
ON template_repository(titolo);

CREATE INDEX IF NOT EXISTS idx_template_repository_area
ON template_repository(area, branca, sottobranca);

CREATE INDEX IF NOT EXISTS idx_template_repository_fase
ON template_repository(fase, rito, grado);

CREATE INDEX IF NOT EXISTS idx_template_repository_canale
ON template_repository(canale_telematico, profilo_deposito);

CREATE INDEX IF NOT EXISTS idx_template_repository_builtin
ON template_repository(builtin, ordine);

CREATE TABLE IF NOT EXISTS template_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL REFERENCES template_repository(template_id) ON DELETE CASCADE,
    block_key TEXT NOT NULL,
    block_type TEXT NOT NULL DEFAULT 'body',
    content TEXT NOT NULL,
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_blocks_template
ON template_blocks(template_id, ordine);

CREATE TABLE IF NOT EXISTS template_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL REFERENCES template_repository(template_id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT,
    section_name TEXT,
    placeholder TEXT,
    help_text TEXT,
    rows_count INTEGER NOT NULL DEFAULT 0,
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_fields_template
ON template_fields(template_id, ordine);

CREATE INDEX IF NOT EXISTS idx_template_fields_name
ON template_fields(field_name);

CREATE TABLE IF NOT EXISTS template_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL REFERENCES template_repository(template_id) ON DELETE CASCADE,
    check_text TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_checks_template
ON template_checks(template_id, ordine);

CREATE TABLE IF NOT EXISTS template_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL REFERENCES template_repository(template_id) ON DELETE CASCADE,
    binding_type TEXT NOT NULL,
    binding_value TEXT NOT NULL,
    label TEXT,
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_bindings_template
ON template_bindings(template_id, ordine);

CREATE TABLE IF NOT EXISTS template_required_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL REFERENCES template_repository(template_id) ON DELETE CASCADE,
    attachment_name TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0,1)),
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_required_attachments_template
ON template_required_attachments(template_id, ordine);

CREATE TABLE IF NOT EXISTS template_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL REFERENCES template_repository(template_id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_keywords_template
ON template_keywords(template_id, ordine);

CREATE INDEX IF NOT EXISTS idx_template_keywords_keyword
ON template_keywords(keyword);

CREATE TABLE IF NOT EXISTS template_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL REFERENCES template_repository(template_id) ON DELETE CASCADE,
    variante TEXT NOT NULL,
    ordine INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_template_variants_template
ON template_variants(template_id, ordine);

COMMIT;
