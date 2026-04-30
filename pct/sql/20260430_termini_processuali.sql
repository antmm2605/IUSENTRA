-- IUSENTRA - Calcolatore termini processuali, SQLite
-- Fondazione SQL locale per template, calendario ufficiale e audit hashato.

CREATE TABLE IF NOT EXISTS deadline_templates (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    matter_type TEXT NOT NULL DEFAULT 'civil'
        CHECK (matter_type IN ('civil', 'penal', 'admin', 'labor', 'tax', 'custom')),
    base_value INTEGER NOT NULL CHECK (base_value > 0),
    period_type TEXT NOT NULL DEFAULT 'days' CHECK (period_type IN ('days', 'months')),
    direction TEXT NOT NULL DEFAULT 'forward' CHECK (direction IN ('forward', 'backward')),
    suspend_august INTEGER NOT NULL DEFAULT 1 CHECK (suspend_august IN (0, 1)),
    ferial_suspension_policy TEXT NOT NULL DEFAULT 'applies'
        CHECK (ferial_suspension_policy IN ('applies', 'excluded', 'partial', 'manual_review')),
    free_term INTEGER NOT NULL DEFAULT 0 CHECK (free_term IN (0, 1)),
    urgent INTEGER NOT NULL DEFAULT 0 CHECK (urgent IN (0, 1)),
    extend_saturday INTEGER NOT NULL DEFAULT 1 CHECK (extend_saturday IN (0, 1)),
    extend_holiday INTEGER NOT NULL DEFAULT 1 CHECK (extend_holiday IN (0, 1)),
    reference_law TEXT NOT NULL DEFAULT '',
    cartabia_compliant INTEGER NOT NULL DEFAULT 1 CHECK (cartabia_compliant IN (0, 1)),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS deadline_audit_logs (
    id TEXT PRIMARY KEY,
    template_code TEXT NOT NULL REFERENCES deadline_templates(code),
    template_version INTEGER NOT NULL,
    case_reference TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    input_date TEXT NOT NULL,
    calculated_deadline TEXT NOT NULL,
    rules_applied_json TEXT NOT NULL DEFAULT '[]',
    engine_version TEXT NOT NULL,
    ruleset_version TEXT NOT NULL,
    calendar_version TEXT NOT NULL,
    is_override INTEGER NOT NULL DEFAULT 0 CHECK (is_override IN (0, 1)),
    override_reason TEXT NOT NULL DEFAULT '',
    raw_input_json TEXT NOT NULL DEFAULT '{}',
    raw_output_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    immutable_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS official_holidays (
    day TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'national',
    source_year INTEGER NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    checksum_sha256 TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calendar_versions (
    version TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    checksum_sha256 TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS deadline_notification_logs (
    id TEXT PRIMARY KEY,
    deadline_id TEXT NOT NULL,
    case_reference TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT 'PEC',
    days_left INTEGER NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    idempotency_key TEXT NOT NULL UNIQUE,
    message_id TEXT NOT NULL DEFAULT '',
    receipt_status TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_deadline_audit_deadline ON deadline_audit_logs(calculated_deadline);
CREATE INDEX IF NOT EXISTS idx_deadline_audit_case ON deadline_audit_logs(case_reference);
CREATE INDEX IF NOT EXISTS idx_deadline_template_matter ON deadline_templates(matter_type, urgent);
CREATE INDEX IF NOT EXISTS idx_deadline_notification_due ON deadline_notification_logs(scheduled_at, status);
