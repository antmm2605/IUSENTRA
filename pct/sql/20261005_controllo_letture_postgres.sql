-- Presa visione per utente e revisione, distinta dalla risoluzione documentale.
CREATE TABLE IF NOT EXISTS controllo_discordanze_viste (
 tenant_id TEXT NOT NULL, utente_id TEXT NOT NULL, fascicolo_id TEXT NOT NULL,
 codice TEXT NOT NULL, chiave TEXT NOT NULL, revisione TEXT NOT NULL, letta_il TEXT NOT NULL,
 PRIMARY KEY(tenant_id,utente_id,fascicolo_id,codice,chiave)
);
-- Stato condiviso di lettura PEC: fonte SQL; casella JSON come mirror storico.
CREATE TABLE IF NOT EXISTS controllo_pec_letture (
 tenant_id TEXT NOT NULL, email_id TEXT NOT NULL, utente_id TEXT NOT NULL,
 letta_il TEXT NOT NULL, stato TEXT NOT NULL DEFAULT 'LETTA' CHECK(stato IN ('LETTA','NON_LETTA')), PRIMARY KEY(tenant_id,email_id)
);

-- La presa visione non completa il termine; cambia con la revisione del contenuto.
CREATE TABLE IF NOT EXISTS controllo_scadenze_viste (
 tenant_id TEXT NOT NULL, utente_id TEXT NOT NULL, scadenza_id TEXT NOT NULL,
 revisione TEXT NOT NULL, letta_il TEXT NOT NULL,
 PRIMARY KEY(tenant_id,utente_id,scadenza_id)
);
