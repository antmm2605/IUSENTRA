CREATE TABLE IF NOT EXISTS audit_events_index (
    event_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    actor_id TEXT,
    kind TEXT NOT NULL,
    event_ts_utc TIMESTAMPTZ NOT NULL,
    event_hash TEXT NOT NULL CHECK (length(event_hash) = 64),
    prev_event_hash TEXT,
    payload_hash TEXT NOT NULL CHECK (length(payload_hash) = 64),
    files_hashes_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    signature_alg TEXT NOT NULL,
    signer_kid TEXT NOT NULL,
    signer_cert_fingerprint TEXT,
    worm_bucket TEXT NOT NULL,
    worm_key TEXT NOT NULL,
    worm_version_id TEXT NOT NULL,
    worm_retention_until TIMESTAMPTZ NOT NULL,
    snapshot_id UUID,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_events_idempotency
    ON audit_events_index(tenant_id, fascicolo_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_audit_events_chain
    ON audit_events_index(tenant_id, fascicolo_id, event_ts_utc, event_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_snapshot
    ON audit_events_index(tenant_id, snapshot_id);

CREATE TABLE IF NOT EXISTS audit_snapshots_index (
    snapshot_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period_start_utc TIMESTAMPTZ NOT NULL,
    period_end_utc TIMESTAMPTZ NOT NULL,
    merkle_root TEXT NOT NULL CHECK (length(merkle_root) = 64),
    events_count INTEGER NOT NULL CHECK (events_count >= 0),
    snapshot_hash TEXT NOT NULL CHECK (length(snapshot_hash) = 64),
    signature_alg TEXT NOT NULL,
    signer_kid TEXT NOT NULL,
    tsa_token_worm_key TEXT,
    worm_bucket TEXT NOT NULL,
    worm_key TEXT NOT NULL,
    worm_version_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_snapshots_period
    ON audit_snapshots_index(tenant_id, period_start_utc, period_end_utc);

CREATE TABLE IF NOT EXISTS audit_emit_failures (
    failure_id UUID PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT,
    attempted_kind TEXT,
    idempotency_key TEXT,
    failure_stage TEXT NOT NULL,
    error_code TEXT NOT NULL,
    error_message_sanitized TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_emit_failures_tenant_created
    ON audit_emit_failures(tenant_id, created_at);

CREATE TABLE IF NOT EXISTS audit_reconciliation_runs (
    run_id UUID PRIMARY KEY,
    tenant_id TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    objects_seen INTEGER NOT NULL DEFAULT 0,
    missing_index_rows_created INTEGER NOT NULL DEFAULT 0,
    conflicts_found INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_reconciliation_tenant_started
    ON audit_reconciliation_runs(tenant_id, started_at);
