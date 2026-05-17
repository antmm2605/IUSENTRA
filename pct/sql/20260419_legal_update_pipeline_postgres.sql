CREATE TABLE IF NOT EXISTS legal_update_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    base_url TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'web',
    trust_class TEXT NOT NULL DEFAULT 'A',
    is_official INTEGER NOT NULL DEFAULT 1 CHECK (is_official IN (0,1)),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    polling_minutes INTEGER NOT NULL DEFAULT 240,
    parser_type TEXT NOT NULL DEFAULT 'html',
    notes TEXT NOT NULL DEFAULT '',
    last_check_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS source_documents_raw (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    raw_html TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL DEFAULT '',
    raw_pdf_path TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL DEFAULT '',
    fetch_status TEXT NOT NULL DEFAULT 'fetched',
    http_status INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS source_documents_normalized (
    id BIGSERIAL PRIMARY KEY,
    raw_document_id BIGINT NOT NULL UNIQUE REFERENCES source_documents_raw(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body_text TEXT NOT NULL DEFAULT '',
    body_short TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'it',
    issuer TEXT NOT NULL DEFAULT '',
    document_date TEXT NOT NULL DEFAULT '',
    document_type_guess TEXT NOT NULL DEFAULT '',
    attachments_json TEXT NOT NULL DEFAULT '[]',
    normalized_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS source_agent_runs (
    id BIGSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    trigger_label TEXT NOT NULL DEFAULT 'batch',
    status TEXT NOT NULL DEFAULT 'running',
    timeout_seconds INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    finished_at TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    documents_found INTEGER NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0,
    skipped_unchanged INTEGER NOT NULL DEFAULT 0,
    autopublished_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT '',
    stderr_tail TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS matters (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    parent_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    level INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
);

CREATE TABLE IF NOT EXISTS ai_documents_analysis (
    id BIGSERIAL PRIMARY KEY,
    normalized_document_id BIGINT NOT NULL UNIQUE REFERENCES source_documents_normalized(id) ON DELETE CASCADE,
    classification_type TEXT NOT NULL DEFAULT 'INCERTO',
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    impact_level TEXT NOT NULL DEFAULT 'medio',
    matter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    submatter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    issuer TEXT NOT NULL DEFAULT '',
    norm_number TEXT NOT NULL DEFAULT '',
    norm_year TEXT NOT NULL DEFAULT '',
    norm_type TEXT NOT NULL DEFAULT '',
    decision_number TEXT NOT NULL DEFAULT '',
    decision_year TEXT NOT NULL DEFAULT '',
    court_name TEXT NOT NULL DEFAULT '',
    effective_date TEXT NOT NULL DEFAULT '',
    summary_short TEXT NOT NULL DEFAULT '',
    summary_long TEXT NOT NULL DEFAULT '',
    what_changes TEXT NOT NULL DEFAULT '',
    extracted_entities_json TEXT NOT NULL DEFAULT '{}',
    proposed_action TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    target_entity_type TEXT NOT NULL DEFAULT '',
    target_entity_id BIGINT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS normative (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    norm_type TEXT NOT NULL DEFAULT '',
    norm_number TEXT NOT NULL DEFAULT '',
    norm_year TEXT NOT NULL DEFAULT '',
    issuer TEXT NOT NULL DEFAULT '',
    publication_date TEXT NOT NULL DEFAULT '',
    effective_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'vigente',
    matter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    submatter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL DEFAULT '',
    source_document_id BIGINT REFERENCES source_documents_normalized(id) ON DELETE SET NULL,
    text_official TEXT NOT NULL DEFAULT '',
    text_current TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    version_group_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE (norm_type, norm_number, norm_year, issuer)
);

CREATE TABLE IF NOT EXISTS normative_versions (
    id BIGSERIAL PRIMARY KEY,
    normative_id BIGINT NOT NULL REFERENCES normative(id) ON DELETE CASCADE,
    version_label TEXT NOT NULL DEFAULT '',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_to TEXT NOT NULL DEFAULT '',
    text_version TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_document_id BIGINT REFERENCES source_documents_normalized(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS normative_relations (
    id BIGSERIAL PRIMARY KEY,
    normative_id BIGINT NOT NULL REFERENCES normative(id) ON DELETE CASCADE,
    related_normative_id BIGINT NOT NULL REFERENCES normative(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL DEFAULT 'references',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS jurisprudence (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    court_name TEXT NOT NULL DEFAULT '',
    section_name TEXT NOT NULL DEFAULT '',
    decision_number TEXT NOT NULL DEFAULT '',
    decision_year TEXT NOT NULL DEFAULT '',
    decision_date TEXT NOT NULL DEFAULT '',
    publication_date TEXT NOT NULL DEFAULT '',
    matter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    submatter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    principle_of_law TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    full_text TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_document_id BIGINT REFERENCES source_documents_normalized(id) ON DELETE SET NULL,
    related_normative_id BIGINT REFERENCES normative(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE (court_name, decision_number, decision_year)
);

CREATE TABLE IF NOT EXISTS prassi (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    issuing_body TEXT NOT NULL DEFAULT '',
    act_type TEXT NOT NULL DEFAULT '',
    act_number TEXT NOT NULL DEFAULT '',
    act_year TEXT NOT NULL DEFAULT '',
    act_date TEXT NOT NULL DEFAULT '',
    matter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    submatter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    summary TEXT NOT NULL DEFAULT '',
    full_text TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_document_id BIGINT REFERENCES source_documents_normalized(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE (issuing_body, act_type, act_number, act_year)
);

CREATE TABLE IF NOT EXISTS news (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    short_summary TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    news_type TEXT NOT NULL DEFAULT 'focus',
    matter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    submatter_id BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    related_normative_id BIGINT REFERENCES normative(id) ON DELETE SET NULL,
    related_jurisprudence_id BIGINT REFERENCES jurisprudence(id) ON DELETE SET NULL,
    related_prassi_id BIGINT REFERENCES prassi(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL DEFAULT '',
    source_document_id BIGINT REFERENCES source_documents_normalized(id) ON DELETE SET NULL,
    is_auto_generated INTEGER NOT NULL DEFAULT 1 CHECK (is_auto_generated IN (0,1)),
    publication_status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS review_queue (
    id BIGSERIAL PRIMARY KEY,
    normalized_document_id BIGINT NOT NULL REFERENCES source_documents_normalized(id) ON DELETE CASCADE,
    analysis_id BIGINT NOT NULL UNIQUE REFERENCES ai_documents_analysis(id) ON DELETE CASCADE,
    proposal_type TEXT NOT NULL DEFAULT '',
    proposed_action TEXT NOT NULL DEFAULT '',
    target_entity_type TEXT NOT NULL DEFAULT '',
    target_entity_id BIGINT,
    proposal_payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 50,
    assigned_to TEXT NOT NULL DEFAULT '',
    review_notes TEXT NOT NULL DEFAULT '',
    reviewed_by TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS web_verification_evidence (
    id BIGSERIAL PRIMARY KEY,
    evidence_key TEXT NOT NULL UNIQUE,
    review_id BIGINT REFERENCES review_queue(id) ON DELETE SET NULL,
    normalized_document_id BIGINT REFERENCES source_documents_normalized(id) ON DELETE SET NULL,
    source_code TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    attachment_url TEXT NOT NULL DEFAULT '',
    attachment_type TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    is_official INTEGER NOT NULL DEFAULT 0,
    context_chars INTEGER NOT NULL DEFAULT 0,
    excerpt TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    matched_terms_json TEXT NOT NULL DEFAULT '[]',
    verification_status TEXT NOT NULL DEFAULT 'verified',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS legal_update_audit_log (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id BIGINT,
    action TEXT NOT NULL,
    old_data_json TEXT NOT NULL DEFAULT '{}',
    new_data_json TEXT NOT NULL DEFAULT '{}',
    performed_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE INDEX IF NOT EXISTS idx_sources_enabled ON sources(enabled, category, code);
CREATE INDEX IF NOT EXISTS idx_raw_source ON source_documents_raw(source_id, published_at, content_hash);
CREATE INDEX IF NOT EXISTS idx_source_agent_runs_source ON source_agent_runs(source_code, started_at);
CREATE INDEX IF NOT EXISTS idx_source_agent_runs_status ON source_agent_runs(status, started_at);
CREATE INDEX IF NOT EXISTS idx_normalized_hash ON source_documents_normalized(normalized_hash);
CREATE INDEX IF NOT EXISTS idx_analysis_classification ON ai_documents_analysis(classification_type, confidence_score);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_web_evidence_review ON web_verification_evidence(review_id, normalized_document_id);
CREATE INDEX IF NOT EXISTS idx_web_evidence_source ON web_verification_evidence(source_code, created_at);
CREATE INDEX IF NOT EXISTS idx_web_evidence_attachment ON web_verification_evidence(attachment_url);
CREATE INDEX IF NOT EXISTS idx_news_publication ON news(publication_status, published_at);
CREATE INDEX IF NOT EXISTS idx_normative_lookup ON normative(norm_type, norm_number, norm_year, issuer);
CREATE INDEX IF NOT EXISTS idx_jurisprudence_lookup ON jurisprudence(court_name, decision_number, decision_year);
CREATE INDEX IF NOT EXISTS idx_prassi_lookup ON prassi(issuing_body, act_type, act_number, act_year);
