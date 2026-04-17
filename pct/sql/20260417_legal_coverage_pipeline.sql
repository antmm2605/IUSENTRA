BEGIN;

CREATE TABLE IF NOT EXISTS coverage_snapshots (
    id BIGSERIAL PRIMARY KEY,
    subbranch_code VARCHAR(128) NOT NULL,
    coverage_score INTEGER NOT NULL,
    coverage_status VARCHAR(32) NOT NULL,
    missing_blocks_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    procedure_count INTEGER NOT NULL DEFAULT 0,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coverage_gap_queue (
    id BIGSERIAL PRIMARY KEY,
    subbranch_code VARCHAR(128) NOT NULL,
    gap_type VARCHAR(64) NOT NULL,
    priority_score INTEGER NOT NULL DEFAULT 0,
    gap_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS generated_procedure_drafts (
    id BIGSERIAL PRIMARY KEY,
    subbranch_code VARCHAR(128) NOT NULL,
    procedure_code VARCHAR(128),
    draft_source VARCHAR(32) NOT NULL DEFAULT 'AI',
    prompt_used TEXT,
    retrieval_examples_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    spec_json JSONB NOT NULL,
    validation_report_json JSONB,
    status VARCHAR(32) NOT NULL DEFAULT 'generated',
    risk_level VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    auto_publish_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewer VARCHAR(255),
    published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS published_procedure_history (
    id BIGSERIAL PRIMARY KEY,
    draft_id BIGINT NOT NULL REFERENCES generated_procedure_drafts(id),
    procedure_code VARCHAR(128) NOT NULL,
    subbranch_code VARCHAR(128) NOT NULL,
    sql_payload TEXT,
    published_mode VARCHAR(32) NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coverage_policies (
    id BIGSERIAL PRIMARY KEY,
    subbranch_code VARCHAR(128),
    complexity_level VARCHAR(32),
    auto_publish_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    min_score_to_skip_generation INTEGER NOT NULL DEFAULT 100,
    require_human_review BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS coverage_learning_events (
    id BIGSERIAL PRIMARY KEY,
    history_id BIGINT REFERENCES published_procedure_history(id),
    subbranch_code VARCHAR(128) NOT NULL,
    procedure_code VARCHAR(128) NOT NULL,
    signal_type VARCHAR(64) NOT NULL DEFAULT 'PUBLISHED_SPEC',
    signal_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cov_snapshots_subbranch
    ON coverage_snapshots (subbranch_code, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cov_gap_status
    ON coverage_gap_queue (status, priority_score DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_cov_drafts_status
    ON generated_procedure_drafts (status, risk_level, auto_publish_eligible, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_cov_history_subbranch
    ON published_procedure_history (subbranch_code, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_cov_learning_subbranch
    ON coverage_learning_events (subbranch_code, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_cov_policies_subbranch_complexity
    ON coverage_policies (COALESCE(subbranch_code, ''), COALESCE(complexity_level, ''));

INSERT INTO coverage_policies (
    subbranch_code,
    complexity_level,
    auto_publish_allowed,
    min_score_to_skip_generation,
    require_human_review,
    notes
) VALUES
    (NULL, 'LOW', TRUE, 95, FALSE, 'Default auto publish per casi standard e basso rischio.'),
    (NULL, 'MEDIUM', FALSE, 100, TRUE, 'Review umana obbligatoria per complessita media.'),
    (NULL, 'HIGH', FALSE, 100, TRUE, 'Review umana obbligatoria per alta complessita.'),
    (NULL, 'SPECIALIST', FALSE, 100, TRUE, 'Review umana obbligatoria per aree specialistiche.'),
    ('CONSUMATORI_GARANZIE_E_RECESSO', 'LOW', TRUE, 90, FALSE, 'Branch consumer standard con preset forte.'),
    ('DIG_PRIVACY_INFORMATIVE_E_BASI_GIURIDICHE', 'LOW', TRUE, 90, FALSE, 'Compliance standard con documenti e template ripetibili.'),
    ('PENALE_DENUNCIA', 'MEDIUM', FALSE, 100, TRUE, 'Penale sempre in review.')
ON CONFLICT DO NOTHING;

COMMIT;
