CREATE TABLE IF NOT EXISTS mediazione_procedimenti (
    id TEXT PRIMARY KEY,
    fascicolo_id TEXT NOT NULL REFERENCES fascicoli(id),
    versione INTEGER NOT NULL,
    stato TEXT NOT NULL,
    dati_json TEXT NOT NULL,
    creato_il TEXT NOT NULL,
    modificato_il TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS mediazione_per_fascicolo ON mediazione_procedimenti(fascicolo_id);
CREATE TABLE IF NOT EXISTS mediazione_procedimenti_audit (
    id TEXT PRIMARY KEY,
    procedimento_id TEXT NOT NULL REFERENCES mediazione_procedimenti(id),
    versione INTEGER NOT NULL,
    attore TEXT NOT NULL,
    azione TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    hash_payload TEXT NOT NULL
);
