-- Tentativi fatturazione: stesso contratto su SQLite e PostgreSQL.
-- Stato trasporto separato da esito SdI e da emissione fiscale.
CREATE TABLE IF NOT EXISTS fatturazione_delivery_attempts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    claim_token TEXT NOT NULL,
    state TEXT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, invoice_id, channel, request_hash)
);
CREATE INDEX IF NOT EXISTS idx_fatturazione_delivery_pending
    ON fatturazione_delivery_attempts (tenant_id, invoice_id, state);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fatturazione_delivery_open ON fatturazione_delivery_attempts(tenant_id, invoice_id, channel) WHERE state IN ('sending', 'uncertain', 'sent_unrecorded');

CREATE TABLE IF NOT EXISTS fatturazione_sdi_receipts (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, invoice_id TEXT NOT NULL,
 receipt_hash TEXT NOT NULL, status TEXT NOT NULL, receipt_json TEXT NOT NULL,
 source_json TEXT NOT NULL, received_at TEXT NOT NULL,
 verification_state TEXT NOT NULL DEFAULT 'pending', next_attempt_at TEXT NOT NULL DEFAULT '',
 UNIQUE(tenant_id, receipt_hash)
);
CREATE INDEX IF NOT EXISTS idx_fatturazione_sdi_receipts_invoice ON fatturazione_sdi_receipts(tenant_id, invoice_id, received_at);
