PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS moduli_dati (
    nome              TEXT PRIMARY KEY,
    percorso          TEXT NOT NULL,
    storage_kind      TEXT NOT NULL DEFAULT 'json',
    inizializzato_il  TEXT,
    payload_json      TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS moduli_json_records (
    modulo        TEXT NOT NULL,
    record_key    TEXT NOT NULL,
    record_index  INTEGER NOT NULL DEFAULT 0,
    record_kind   TEXT NOT NULL DEFAULT 'dict',
    payload_json  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (modulo, record_key),
    FOREIGN KEY (modulo) REFERENCES moduli_dati(nome) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_moduli_json_records_modulo
    ON moduli_json_records(modulo);

COMMIT;
