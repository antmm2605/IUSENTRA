CREATE TABLE IF NOT EXISTS time_tracking_timers (
    id                 TEXT PRIMARY KEY,
    user_id            TEXT,
    username           TEXT,
    id_fascicolo       TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    id_cliente         TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    activity_type      TEXT NOT NULL DEFAULT 'other',
    description        TEXT,
    started_at         TIMESTAMPTZ NOT NULL,
    paused_at          TIMESTAMPTZ,
    ended_at           TIMESTAMPTZ,
    elapsed_seconds    INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'running',
    timesheet_entry_id TEXT REFERENCES timesheet_entries(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ,
    dati_json          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_time_tracking_user_status
    ON time_tracking_timers(user_id, status);
CREATE INDEX IF NOT EXISTS idx_time_tracking_fascicolo
    ON time_tracking_timers(id_fascicolo);
CREATE INDEX IF NOT EXISTS idx_time_tracking_cliente
    ON time_tracking_timers(id_cliente);
CREATE INDEX IF NOT EXISTS idx_time_tracking_started
    ON time_tracking_timers(started_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_time_tracking_one_active_user
    ON time_tracking_timers(user_id)
    WHERE status IN ('running', 'paused');
