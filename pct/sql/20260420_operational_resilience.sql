CREATE TABLE IF NOT EXISTS operational_crash_test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_slug TEXT NOT NULL DEFAULT '',
    trigger_source TEXT NOT NULL DEFAULT 'manual',
    schedule_code TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    overall_ok INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    total_phases INTEGER NOT NULL DEFAULT 0,
    passed_phases INTEGER NOT NULL DEFAULT 0,
    report_path TEXT NOT NULL DEFAULT '',
    report_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS operational_repair_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crash_run_id INTEGER NOT NULL DEFAULT 0,
    tenant_slug TEXT NOT NULL DEFAULT '',
    action_code TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    status TEXT NOT NULL DEFAULT 'open',
    title TEXT NOT NULL DEFAULT '',
    remediation TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operational_backup_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_slug TEXT NOT NULL DEFAULT '',
    executed_at TEXT NOT NULL,
    backup_scope TEXT NOT NULL DEFAULT 'nightly',
    backup_type TEXT NOT NULL DEFAULT 'COMPLETO',
    status TEXT NOT NULL DEFAULT 'OK',
    primary_record_id TEXT NOT NULL DEFAULT '',
    primary_path TEXT NOT NULL DEFAULT '',
    local_copy_path TEXT NOT NULL DEFAULT '',
    secondary_copy_path TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_operational_crash_test_runs_tenant_started
ON operational_crash_test_runs (tenant_slug, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_operational_repair_tickets_tenant_created
ON operational_repair_tickets (tenant_slug, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_operational_backup_runs_tenant_executed
ON operational_backup_runs (tenant_slug, executed_at DESC);
