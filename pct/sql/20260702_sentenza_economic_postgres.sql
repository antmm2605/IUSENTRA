-- Sentenza Economic Control V1 — schema PostgreSQL (gemello del file SQLite).
-- Parità di tabelle obbligatoria con 20260702_sentenza_economic.sql (test di parità).

CREATE TABLE IF NOT EXISTS sentenza_economic_audits (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    documento_id TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    document_hash_sha256 TEXT NOT NULL DEFAULT '',
    fonte TEXT NOT NULL DEFAULT '',
    rg_numero_rilevato TEXT NOT NULL DEFAULT '',
    rg_anno_rilevato TEXT NOT NULL DEFAULT '',
    cliente_rilevato TEXT NOT NULL DEFAULT '',
    tribunale_rilevato TEXT NOT NULL DEFAULT '',
    match_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    safe_to_attach INTEGER NOT NULL DEFAULT 0,
    human_review_required INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'to_review',
    audit_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sentenza_economic_audits_fascicolo
    ON sentenza_economic_audits (tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_sentenza_economic_audits_status
    ON sentenza_economic_audits (tenant_id, status);

CREATE TABLE IF NOT EXISTS contributo_unificato_audits (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    sentenza_audit_id TEXT NOT NULL DEFAULT '',
    documento_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'incerto',
    importo_pagato DOUBLE PRECISION,
    importo_atteso DOUBLE PRECISION,
    differenza DOUBLE PRECISION,
    iuv TEXT NOT NULL DEFAULT '',
    ricevuta_id TEXT NOT NULL DEFAULT '',
    data_pagamento TEXT NOT NULL DEFAULT '',
    fonte_prova TEXT NOT NULL DEFAULT '',
    evidence_hash_sha256 TEXT NOT NULL DEFAULT '',
    human_review_required INTEGER NOT NULL DEFAULT 1,
    audit_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contributo_unificato_audits_fascicolo
    ON contributo_unificato_audits (tenant_id, fascicolo_id);

CREATE TABLE IF NOT EXISTS fascicolo_economic_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    beneficiary_type TEXT NOT NULL DEFAULT '',
    amount DOUBLE PRECISION,
    currency TEXT NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL DEFAULT 'to_review',
    priority TEXT NOT NULL DEFAULT 'P2',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT '',
    reviewed_by TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_fascicolo_economic_events_fascicolo
    ON fascicolo_economic_events (tenant_id, fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_fascicolo_economic_events_status
    ON fascicolo_economic_events (tenant_id, status);

CREATE TABLE IF NOT EXISTS sentenza_economic_audit_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    actor_type TEXT NOT NULL DEFAULT '',
    actor_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL DEFAULT '',
    resource_type TEXT NOT NULL DEFAULT '',
    resource_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sentenza_economic_audit_events_tenant
    ON sentenza_economic_audit_events (tenant_id, created_at);
