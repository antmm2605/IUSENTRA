-- Catalogazione documentale del fascicolo - schema SQLite.
-- Il fascicolo resta il contesto operativo; nessuna tabella usa JSON come fonte di verità.

CREATE TABLE IF NOT EXISTS document_catalog_rule_sets (
    id TEXT PRIMARY KEY,
    resolver_version TEXT NOT NULL,
    registry_version TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, resolver_version, registry_version)
);

CREATE TABLE IF NOT EXISTS document_catalog_source_snapshots (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    rule_set_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    official_url TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    snapshot_sha256 TEXT,
    last_verified_at TEXT,
    source_metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (rule_set_id) REFERENCES document_catalog_rule_sets(id) ON DELETE CASCADE,
    UNIQUE (tenant_id, rule_set_id, profile_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_document_catalog_source_snapshots_tenant_profile
    ON document_catalog_source_snapshots (tenant_id, profile_id);

CREATE TABLE IF NOT EXISTS document_catalog_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_ai_id TEXT,
    document_version_id TEXT,
    document_sha256 TEXT NOT NULL,
    resolver_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'review_required', 'error')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    requested_by TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, fascicolo_id, document_id, document_sha256, resolver_version)
);

CREATE INDEX IF NOT EXISTS idx_document_catalog_jobs_tenant_fascicolo_status
    ON document_catalog_jobs (tenant_id, fascicolo_id, status, updated_at);

CREATE TABLE IF NOT EXISTS document_catalog_assignments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_ai_id TEXT,
    document_version_id TEXT,
    document_sha256 TEXT NOT NULL,
    profile_id TEXT,
    legal_area TEXT,
    legal_branch TEXT,
    legal_subfamily TEXT,
    jurisdiction TEXT,
    rite TEXT,
    proceeding_phase TEXT,
    document_nature TEXT NOT NULL,
    document_label TEXT NOT NULL,
    document_section TEXT NOT NULL,
    deposit_role TEXT NOT NULL,
    deposit_candidate INTEGER NOT NULL DEFAULT 0 CHECK (deposit_candidate IN (0, 1)),
    status TEXT NOT NULL CHECK (status IN ('proposed', 'confirmed', 'review_required', 'superseded', 'rejected')),
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    source_state TEXT NOT NULL CHECK (source_state IN ('verified_snapshot', 'manual_browser_evidence', 'manual_override', 'review_required')),
    resolver_version TEXT NOT NULL,
    rule_set_id TEXT,
    reason TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT,
    FOREIGN KEY (rule_set_id) REFERENCES document_catalog_rule_sets(id) ON DELETE SET NULL,
    UNIQUE (tenant_id, fascicolo_id, document_id, document_sha256, resolver_version)
);

CREATE INDEX IF NOT EXISTS idx_document_catalog_assignments_fascicolo_active
    ON document_catalog_assignments (tenant_id, fascicolo_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_document_catalog_assignments_document
    ON document_catalog_assignments (tenant_id, fascicolo_id, document_id, updated_at);

CREATE TABLE IF NOT EXISTS document_catalog_candidates (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    rank_number INTEGER NOT NULL CHECK (rank_number >= 1),
    profile_id TEXT,
    document_nature TEXT NOT NULL,
    document_label TEXT NOT NULL,
    document_section TEXT NOT NULL,
    deposit_role TEXT NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (assignment_id) REFERENCES document_catalog_assignments(id) ON DELETE CASCADE,
    UNIQUE (assignment_id, rank_number)
);

CREATE TABLE IF NOT EXISTS document_catalog_evidence (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('fascicolo_context', 'portal_metadata', 'document_metadata', 'extracted_text', 'legal_source', 'manual_confirmation')),
    locator TEXT NOT NULL,
    excerpt TEXT NOT NULL DEFAULT '',
    weight INTEGER NOT NULL CHECK (weight BETWEEN 0 AND 100),
    content_sha256 TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (assignment_id) REFERENCES document_catalog_assignments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_catalog_evidence_assignment
    ON document_catalog_evidence (assignment_id, evidence_type);

CREATE TABLE IF NOT EXISTS document_catalog_reviews (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('open', 'resolved', 'dismissed')),
    reason_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    resolved_by TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (assignment_id) REFERENCES document_catalog_assignments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_catalog_reviews_tenant_fascicolo_state
    ON document_catalog_reviews (tenant_id, fascicolo_id, state, created_at);
