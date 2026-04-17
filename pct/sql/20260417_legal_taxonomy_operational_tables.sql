BEGIN;

CREATE TABLE IF NOT EXISTS legal_subbranch_profiles (
    subbranch_code VARCHAR(128) PRIMARY KEY,
    coverage_mode VARCHAR(64) NOT NULL DEFAULT 'OPERATIONAL_READY',
    operational_priority INTEGER NOT NULL DEFAULT 50,
    is_telematic BOOLEAN NOT NULL DEFAULT FALSE,
    requires_human_review BOOLEAN NOT NULL DEFAULT TRUE,
    default_channel_code VARCHAR(64),
    default_registry_code VARCHAR(64),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedures (
    code VARCHAR(128) PRIMARY KEY,
    subbranch_code VARCHAR(128) NOT NULL,
    phase_code VARCHAR(64) NOT NULL DEFAULT 'PREPARAZIONE',
    channel_code VARCHAR(64) NOT NULL DEFAULT 'INTERNO_STUDIO',
    act_type_code VARCHAR(64) NOT NULL DEFAULT 'ISTANZA',
    norm_source_code VARCHAR(64) NOT NULL DEFAULT 'CODICE_CIVILE',
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    workflow_code VARCHAR(128),
    estimated_duration_days INTEGER NOT NULL DEFAULT 30,
    complexity_level VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    mandatory_human_review BOOLEAN NOT NULL DEFAULT TRUE,
    requires_hearing BOOLEAN NOT NULL DEFAULT FALSE,
    requires_registry_enrollment BOOLEAN NOT NULL DEFAULT FALSE,
    allows_settlement BOOLEAN NOT NULL DEFAULT FALSE,
    default_output_bundle_code VARCHAR(128),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_variants (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_phase_map (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    phase_code VARCHAR(64) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_acts (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    act_type_code VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_documents (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_document_map (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    document_type_code VARCHAR(64) NOT NULL DEFAULT 'CERTIFICATO',
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    phase_code VARCHAR(64) NOT NULL DEFAULT 'PREPARAZIONE',
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_user_upload BOOLEAN NOT NULL DEFAULT TRUE,
    is_system_generated BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_norms (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    norm_source_code VARCHAR(64) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_checklists (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    item_text TEXT NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_requirements (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    requirement_type VARCHAR(64) NOT NULL,
    requirement_key VARCHAR(128) NOT NULL,
    requirement_value TEXT,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_deadlines (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    phase_code VARCHAR(64),
    label VARCHAR(255) NOT NULL,
    relative_to VARCHAR(64) NOT NULL DEFAULT 'EVENTO',
    days_offset INTEGER,
    business_days_only BOOLEAN NOT NULL DEFAULT FALSE,
    is_peremptory BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_outcomes (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_positive BOOLEAN,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_procedure_rules (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    rule_type VARCHAR(64) NOT NULL DEFAULT 'WARNING',
    rule_key VARCHAR(128) NOT NULL,
    rule_expression TEXT NOT NULL,
    user_message TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_templates (
    code VARCHAR(160) PRIMARY KEY,
    procedure_code VARCHAR(128) NOT NULL,
    act_type_code VARCHAR(64),
    template_kind VARCHAR(64) NOT NULL DEFAULT 'ACT',
    version_label VARCHAR(64) NOT NULL DEFAULT 'v1',
    is_placeholder BOOLEAN NOT NULL DEFAULT FALSE,
    jurisdiction_scope VARCHAR(128),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    body TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS legal_template_variables (
    code VARCHAR(160) PRIMARY KEY,
    template_code VARCHAR(160) NOT NULL,
    variable_name VARCHAR(128) NOT NULL,
    variable_type VARCHAR(64) NOT NULL DEFAULT 'STRING',
    source_scope VARCHAR(64) NOT NULL DEFAULT 'MANUAL',
    source_key VARCHAR(128),
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    default_value TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legal_subbranch_profiles_priority
    ON legal_subbranch_profiles (operational_priority DESC, subbranch_code);
CREATE INDEX IF NOT EXISTS idx_legal_procedures_subbranch
    ON legal_procedures (subbranch_code, is_active);
CREATE INDEX IF NOT EXISTS idx_legal_variants_procedure
    ON legal_procedure_variants (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_phase_map_procedure
    ON legal_procedure_phase_map (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_acts_procedure
    ON legal_procedure_acts (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_document_map_procedure
    ON legal_procedure_document_map (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_norms_procedure
    ON legal_procedure_norms (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_checklists_procedure
    ON legal_procedure_checklists (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_requirements_procedure
    ON legal_procedure_requirements (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_outcomes_procedure
    ON legal_procedure_outcomes (procedure_code);
CREATE INDEX IF NOT EXISTS idx_legal_rules_procedure
    ON legal_procedure_rules (procedure_code, is_active);
CREATE INDEX IF NOT EXISTS idx_legal_templates_procedure
    ON legal_templates (procedure_code, is_active);
CREATE INDEX IF NOT EXISTS idx_legal_template_variables_template
    ON legal_template_variables (template_code);

COMMIT;
