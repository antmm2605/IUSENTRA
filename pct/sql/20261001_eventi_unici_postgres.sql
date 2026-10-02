CREATE TABLE IF NOT EXISTS eventi_unici_correlazioni (
 tenant_id TEXT NOT NULL, area TEXT NOT NULL, origine_id TEXT NOT NULL,
 canonico_id TEXT NOT NULL, fascicolo_id TEXT NOT NULL, prova_sha256 TEXT NOT NULL,
 evidenza_json TEXT NOT NULL, operazione_id TEXT NOT NULL, creato_il TEXT NOT NULL,
 PRIMARY KEY (tenant_id, area, origine_id),
 CHECK (area IN ('agenda','scadenze','notifiche'))
);
CREATE INDEX IF NOT EXISTS idx_eventi_unici_fascicolo ON eventi_unici_correlazioni(tenant_id,fascicolo_id,area,canonico_id);
CREATE INDEX IF NOT EXISTS idx_eventi_unici_destinazione ON eventi_unici_correlazioni(tenant_id,area,canonico_id);
CREATE TABLE IF NOT EXISTS eventi_unici_audit (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, fascicolo_id TEXT NOT NULL,
 attore TEXT NOT NULL, evidenza_json TEXT NOT NULL, evidenza_sha256 TEXT NOT NULL,
 creato_il TEXT NOT NULL
);
