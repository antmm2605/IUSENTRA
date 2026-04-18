CREATE TABLE IF NOT EXISTS workspace_intelligence_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    actions_json TEXT NOT NULL DEFAULT '[]',
    overview_json TEXT NOT NULL DEFAULT '{}',
    search_text TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
