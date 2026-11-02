-- Regole dello studio (PostgreSQL): stessa struttura dello schema SQLite 20261102_regole_studio.sql.
-- Sostituzioni deterministiche, mai dati di addestramento. Ogni riga è dello studio (tenant_id).
CREATE TABLE IF NOT EXISTS regole_studio (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    regola_id TEXT NOT NULL,
    produttore TEXT NOT NULL DEFAULT '',
    azione TEXT NOT NULL CHECK (azione IN ('modifica_valore', 'non_proporre', 'chiedi_sempre', 'non_chiedere_conferma')),
    campo TEXT NOT NULL DEFAULT '',
    valore TEXT NOT NULL DEFAULT '',
    ambito TEXT NOT NULL CHECK (ambito IN ('fascicolo', 'giudice', 'ufficio', 'tipo')),
    fascicolo_id TEXT NOT NULL DEFAULT '',
    ufficio TEXT NOT NULL DEFAULT '',
    giudice TEXT NOT NULL DEFAULT '',
    materia TEXT NOT NULL DEFAULT '',
    motivo TEXT NOT NULL DEFAULT '',
    autore_id TEXT NOT NULL,
    autore_nome TEXT NOT NULL DEFAULT '',
    attiva INTEGER NOT NULL DEFAULT 1,
    passaggio_json TEXT NOT NULL DEFAULT '{}',
    creata_il TEXT NOT NULL,
    aggiornata_il TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_regole_studio_regola ON regole_studio (tenant_id, regola_id, attiva);

CREATE TABLE IF NOT EXISTS regole_studio_eventi (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    regola_studio_id TEXT NOT NULL DEFAULT '',
    evento TEXT NOT NULL CHECK (evento IN ('creata', 'modificata', 'disattivata', 'riattivata', 'rifiutata')),
    autore_id TEXT NOT NULL DEFAULT '',
    dati_json TEXT NOT NULL DEFAULT '{}',
    creato_il TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_regole_studio_eventi ON regole_studio_eventi (tenant_id, regola_studio_id, creato_il);

-- Una riga per regola e caso: la prima applicazione (o il primo rifiuto) resta registrata.
CREATE TABLE IF NOT EXISTS regole_studio_applicazioni (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    regola_studio_id TEXT NOT NULL,
    chiave_passaggio TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    esito TEXT NOT NULL CHECK (esito IN ('applicata', 'rifiutata')),
    motivo TEXT NOT NULL DEFAULT '',
    prima_il TEXT NOT NULL,
    UNIQUE (tenant_id, regola_studio_id, chiave_passaggio, esito)
);
CREATE INDEX IF NOT EXISTS idx_regole_studio_applicazioni ON regole_studio_applicazioni (tenant_id, regola_studio_id);
