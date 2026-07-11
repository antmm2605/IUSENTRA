-- Piano del giorno (Lex Oggi): proiezione materializzata dei segnali operativi
-- e dei piani giornalieri per utente. Tenant-aware: ogni riga porta tenant_id
-- e ogni query applicativa filtra per tenant (fail-closed).

CREATE TABLE IF NOT EXISTS operational_signals (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    source_version TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    cliente_id TEXT NOT NULL DEFAULT '',
    lawyer_hint TEXT NOT NULL DEFAULT '',
    responsible_user_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    event_at TEXT NOT NULL DEFAULT '',
    due_at TEXT NOT NULL DEFAULT '',
    legal_risk TEXT NOT NULL DEFAULT '',
    priority_hint TEXT NOT NULL DEFAULT '',
    blocking INTEGER NOT NULL DEFAULT 0,
    peremptory INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'active',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    href TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dp_signals_tenant_dedupe
    ON operational_signals(tenant_id, dedupe_key);
CREATE INDEX IF NOT EXISTS idx_dp_signals_tenant_status_due
    ON operational_signals(tenant_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_dp_signals_tenant_fascicolo
    ON operational_signals(tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_dp_signals_tenant_source
    ON operational_signals(tenant_id, source_type, source_id);

CREATE TABLE IF NOT EXISTS daily_plan_items (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    target_date TEXT NOT NULL,
    assigned_user_id TEXT NOT NULL DEFAULT '',
    assigned_lawyer_label TEXT NOT NULL DEFAULT '',
    plan_version TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    item_rank INTEGER NOT NULL DEFAULT 0,
    action_kind TEXT NOT NULL,
    sector TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'proposed',
    title TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    priority_reason TEXT NOT NULL DEFAULT '',
    priority_rule TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    fascicolo_label TEXT NOT NULL DEFAULT '',
    cliente_id TEXT NOT NULL DEFAULT '',
    cliente_label TEXT NOT NULL DEFAULT '',
    due_at TEXT NOT NULL DEFAULT '',
    blocking INTEGER NOT NULL DEFAULT 0,
    peremptory INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.0,
    review_required INTEGER NOT NULL DEFAULT 0,
    scheduled_start TEXT NOT NULL DEFAULT '',
    estimated_minutes INTEGER NOT NULL DEFAULT 0,
    in_backlog INTEGER NOT NULL DEFAULT 0,
    source_signal_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    available_actions_json TEXT NOT NULL DEFAULT '[]',
    href TEXT NOT NULL DEFAULT '',
    snoozed_until TEXT NOT NULL DEFAULT '',
    status_actor TEXT NOT NULL DEFAULT '',
    status_note TEXT NOT NULL DEFAULT '',
    status_updated_at TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dp_items_tenant_date_dedupe
    ON daily_plan_items(tenant_id, target_date, dedupe_key);
CREATE INDEX IF NOT EXISTS idx_dp_items_tenant_user_date_prio
    ON daily_plan_items(tenant_id, assigned_user_id, target_date, priority, item_rank);
CREATE INDEX IF NOT EXISTS idx_dp_items_tenant_status_due
    ON daily_plan_items(tenant_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_dp_items_tenant_fascicolo
    ON daily_plan_items(tenant_id, fascicolo_id);

CREATE TABLE IF NOT EXISTS daily_plan_snapshots (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    target_date TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    plan_version TEXT NOT NULL DEFAULT '',
    generated_at TEXT NOT NULL DEFAULT '',
    generation_mode TEXT NOT NULL DEFAULT 'full',
    freshness_json TEXT NOT NULL DEFAULT '{}',
    coverage_json TEXT NOT NULL DEFAULT '{}',
    summary_json TEXT NOT NULL DEFAULT '{}',
    fixed_agenda_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    lex_summary TEXT NOT NULL DEFAULT '',
    lex_summary_version TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dp_snapshots_tenant_date_user
    ON daily_plan_snapshots(tenant_id, target_date, user_id);

CREATE TABLE IF NOT EXISTS daily_plan_source_watermarks (
    tenant_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    watermark TEXT NOT NULL DEFAULT '',
    last_success_at TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT 'never',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, source_type)
);

CREATE TABLE IF NOT EXISTS daily_plan_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    requested_by TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    budget_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    report_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dp_jobs_tenant_status
    ON daily_plan_jobs(tenant_id, status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dp_jobs_tenant_idem
    ON daily_plan_jobs(tenant_id, idempotency_key)
    WHERE idempotency_key <> '';

CREATE TABLE IF NOT EXISTS dirty_entities (
    tenant_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    marked_at TEXT NOT NULL,
    consumed_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_dp_dirty_pending
    ON dirty_entities(tenant_id, consumed_at, marked_at);

CREATE TABLE IF NOT EXISTS daily_plan_action_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dp_action_idem
    ON daily_plan_action_log(tenant_id, idempotency_key)
    WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_dp_action_item
    ON daily_plan_action_log(tenant_id, item_id, created_at);
