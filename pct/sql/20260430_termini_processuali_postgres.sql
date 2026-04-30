-- IUSENTRA - Calcolatore termini processuali, PostgreSQL
-- Fondazione SQL per template, calendario ufficiale e audit hashato.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS deadline_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(80) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    matter_type VARCHAR(50) NOT NULL DEFAULT 'civil'
        CHECK (matter_type IN ('civil', 'penal', 'admin', 'labor', 'tax', 'custom')),
    base_value INTEGER NOT NULL CHECK (base_value > 0),
    period_type VARCHAR(10) NOT NULL DEFAULT 'days' CHECK (period_type IN ('days', 'months')),
    direction VARCHAR(10) NOT NULL DEFAULT 'forward' CHECK (direction IN ('forward', 'backward')),
    suspend_august BOOLEAN NOT NULL DEFAULT TRUE,
    ferial_suspension_policy VARCHAR(20) NOT NULL DEFAULT 'applies'
        CHECK (ferial_suspension_policy IN ('applies', 'excluded', 'partial', 'manual_review')),
    free_term BOOLEAN NOT NULL DEFAULT FALSE,
    urgent BOOLEAN NOT NULL DEFAULT FALSE,
    extend_saturday BOOLEAN NOT NULL DEFAULT TRUE,
    extend_holiday BOOLEAN NOT NULL DEFAULT TRUE,
    reference_law VARCHAR(255) NOT NULL DEFAULT '',
    cartabia_compliant BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS deadline_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_code VARCHAR(80) NOT NULL REFERENCES deadline_templates(code),
    template_version INTEGER NOT NULL,
    case_reference VARCHAR(80) NOT NULL DEFAULT '',
    user_id UUID,
    input_date DATE NOT NULL,
    calculated_deadline DATE NOT NULL,
    rules_applied JSONB NOT NULL DEFAULT '[]'::jsonb,
    engine_version VARCHAR(40) NOT NULL,
    ruleset_version VARCHAR(80) NOT NULL,
    calendar_version VARCHAR(80) NOT NULL,
    is_override BOOLEAN NOT NULL DEFAULT FALSE,
    override_reason TEXT NOT NULL DEFAULT '',
    raw_input JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_output JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    immutable_hash CHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS official_holidays (
    day DATE PRIMARY KEY,
    description TEXT NOT NULL,
    type VARCHAR(40) NOT NULL DEFAULT 'national',
    source_year INTEGER NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    checksum_sha256 CHAR(64) NOT NULL DEFAULT '',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS calendar_versions (
    version VARCHAR(80) PRIMARY KEY,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    checksum_sha256 CHAR(64) NOT NULL DEFAULT '',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS deadline_notification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deadline_id UUID NOT NULL,
    case_reference VARCHAR(80) NOT NULL DEFAULT '',
    user_id UUID,
    channel VARCHAR(20) NOT NULL DEFAULT 'PEC',
    days_left INTEGER NOT NULL,
    scheduled_at DATE NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'planned',
    idempotency_key CHAR(64) NOT NULL UNIQUE,
    message_id TEXT NOT NULL DEFAULT '',
    receipt_status VARCHAR(60) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deadline_audit_deadline ON deadline_audit_logs(calculated_deadline);
CREATE INDEX IF NOT EXISTS idx_deadline_audit_case ON deadline_audit_logs(case_reference);
CREATE INDEX IF NOT EXISTS idx_deadline_template_matter ON deadline_templates(matter_type, urgent);
CREATE INDEX IF NOT EXISTS idx_deadline_notification_due ON deadline_notification_logs(scheduled_at, status);
