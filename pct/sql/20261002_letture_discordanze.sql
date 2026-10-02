-- Proiezioni SQL tenant-aware degli esiti e delle discordanze dopo le letture.
CREATE TABLE IF NOT EXISTS letture_verifiche_esiti (
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    revisione TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL,
    PRIMARY KEY (tenant_id, fascicolo_id)
);
CREATE TABLE IF NOT EXISTS letture_discordanze (
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    codice TEXT NOT NULL,
    chiave TEXT NOT NULL,
    stato TEXT NOT NULL CHECK(stato IN ('aperta','superata')),
    payload_json TEXT NOT NULL,
    revisione TEXT NOT NULL,
    aggiornata_il TEXT NOT NULL,
    PRIMARY KEY (tenant_id, fascicolo_id, codice, chiave)
);
CREATE INDEX IF NOT EXISTS idx_letture_discordanze_aperte
    ON letture_discordanze(tenant_id, stato, aggiornata_il, fascicolo_id);
CREATE TABLE IF NOT EXISTS letture_discordanze_audit (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    codice TEXT NOT NULL,
    chiave TEXT NOT NULL,
    stato TEXT NOT NULL,
    revisione TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    registrato_il TEXT NOT NULL
);
