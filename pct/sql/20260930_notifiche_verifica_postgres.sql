CREATE TABLE IF NOT EXISTS notifiche_verifiche (
 tenant_id TEXT NOT NULL, fascicolo_id TEXT NOT NULL, documento_id TEXT NOT NULL,
 dati_json TEXT NOT NULL, revisione INTEGER NOT NULL CHECK(revisione > 0),
 attore TEXT NOT NULL, aggiornato_il TEXT NOT NULL,
 PRIMARY KEY(tenant_id, fascicolo_id, documento_id)
);
CREATE TABLE IF NOT EXISTS notifiche_verifiche_audit (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, fascicolo_id TEXT NOT NULL,
 documento_id TEXT NOT NULL, prima_json TEXT NOT NULL, dopo_json TEXT NOT NULL,
 attore TEXT NOT NULL, registrato_il TEXT NOT NULL, impronta TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_notifiche_verifiche_audit_caso ON notifiche_verifiche_audit(tenant_id,fascicolo_id,documento_id);
