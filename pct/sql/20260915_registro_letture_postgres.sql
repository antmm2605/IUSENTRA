-- Registro delle letture - schema PostgreSQL (gemello del file SQLite).
-- Parità di tabelle obbligatoria con 20260915_registro_letture.sql (test di contratto).
-- Che cosa il gestionale ha già letto, per quale lettore, con quale impronta:
-- un documento o una PEC invariati non si rileggono; cambiano hash, si rilegge
-- solo quell'oggetto. Le anomalie sono i dati letti che un controllo
-- deterministico giudica dubbi (date in primis) e che l'avvocato conferma o corregge.
-- Base normativa della cura documentale: art. 3 D.M. 44/2011 (conservazione e
-- integrità dei documenti informatici) e art. 20 CAD D.Lgs. 82/2005 (impronta).

CREATE TABLE IF NOT EXISTS letture_oggetti (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('documento', 'pec', 'allegato_pec')),
    oggetto_id TEXT NOT NULL,
    nome TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    sha256_archivio TEXT NOT NULL DEFAULT '',
    dimensione INTEGER NOT NULL DEFAULT 0,
    cliente TEXT NOT NULL DEFAULT '',
    numero_rg TEXT NOT NULL DEFAULT '',
    anno_rg TEXT NOT NULL DEFAULT '',
    origine TEXT NOT NULL DEFAULT '',
    data_oggetto TEXT NOT NULL DEFAULT '',
    presente INTEGER NOT NULL DEFAULT 1 CHECK (presente IN (0, 1)),
    censito_il TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL,
    rimosso_il TEXT NOT NULL DEFAULT '',
    UNIQUE (tenant_id, fascicolo_id, tipo, oggetto_id)
);

CREATE INDEX IF NOT EXISTS idx_letture_oggetti_fascicolo
    ON letture_oggetti (tenant_id, fascicolo_id, presente);
CREATE INDEX IF NOT EXISTS idx_letture_oggetti_impronta
    ON letture_oggetti (tenant_id, tipo, sha256_archivio);
CREATE INDEX IF NOT EXISTS idx_letture_oggetti_ruolo
    ON letture_oggetti (tenant_id, numero_rg, anno_rg);

CREATE TABLE IF NOT EXISTS letture (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('documento', 'pec', 'allegato_pec')),
    oggetto_id TEXT NOT NULL,
    sha256 TEXT NOT NULL DEFAULT '',
    lettore TEXT NOT NULL,
    versione_lettore TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL CHECK (stato IN ('letto', 'in_corso', 'errore', 'non_leggibile')),
    esito_json TEXT NOT NULL DEFAULT '{}',
    durata_ms INTEGER NOT NULL DEFAULT 0,
    letto_il TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL,
    UNIQUE (tenant_id, tipo, oggetto_id, sha256, lettore)
);

CREATE INDEX IF NOT EXISTS idx_letture_fascicolo_lettore
    ON letture (tenant_id, fascicolo_id, lettore, stato);

CREATE TABLE IF NOT EXISTS letture_fascicoli (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    lettore TEXT NOT NULL,
    versione_lettore TEXT NOT NULL DEFAULT '',
    impronta TEXT NOT NULL DEFAULT '',
    oggetti_totali INTEGER NOT NULL DEFAULT 0,
    oggetti_letti INTEGER NOT NULL DEFAULT 0,
    stato TEXT NOT NULL DEFAULT 'completa' CHECK (stato IN ('completa', 'parziale', 'errore')),
    esito_json TEXT NOT NULL DEFAULT '{}',
    aggiornato_il TEXT NOT NULL,
    UNIQUE (tenant_id, fascicolo_id, lettore)
);

CREATE TABLE IF NOT EXISTS letture_viste (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    utente_id TEXT NOT NULL,
    impronta TEXT NOT NULL DEFAULT '',
    inventario_json TEXT NOT NULL DEFAULT '[]',
    visto_il TEXT NOT NULL,
    UNIQUE (tenant_id, fascicolo_id, utente_id)
);

CREATE TABLE IF NOT EXISTS letture_anomalie (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('documento', 'pec', 'allegato_pec')),
    oggetto_id TEXT NOT NULL,
    sha256 TEXT NOT NULL DEFAULT '',
    lettore TEXT NOT NULL,
    campo TEXT NOT NULL,
    valore_letto TEXT NOT NULL DEFAULT '',
    valore_proposto TEXT NOT NULL DEFAULT '',
    valore_confermato TEXT NOT NULL DEFAULT '',
    contesto TEXT NOT NULL DEFAULT '',
    motivo TEXT NOT NULL,
    codice TEXT NOT NULL,
    gravita TEXT NOT NULL CHECK (gravita IN ('alta', 'media', 'bassa')),
    stato TEXT NOT NULL CHECK (stato IN ('aperta', 'confermata', 'corretta', 'ignorata')),
    creata_il TEXT NOT NULL,
    risolta_il TEXT NOT NULL DEFAULT '',
    risolta_da TEXT NOT NULL DEFAULT '',
    UNIQUE (tenant_id, tipo, oggetto_id, sha256, lettore, campo, valore_letto)
);

CREATE INDEX IF NOT EXISTS idx_letture_anomalie_fascicolo_stato
    ON letture_anomalie (tenant_id, fascicolo_id, stato, gravita);
