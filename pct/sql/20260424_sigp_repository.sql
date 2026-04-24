PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS sigp_schema_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    descrizione TEXT,
    path_locale TEXT NOT NULL,
    main_xsd TEXT,
    attivo INTEGER NOT NULL DEFAULT 0 CHECK (attivo IN (0,1)),
    data_pubblicazione TEXT,
    fonte TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_uffici (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice_ufficio TEXT NOT NULL UNIQUE,
    nome_ufficio TEXT NOT NULL,
    distretto TEXT,
    ambiente TEXT NOT NULL DEFAULT 'produzione',
    attivo INTEGER NOT NULL DEFAULT 1 CHECK (attivo IN (0,1))
);

CREATE TABLE IF NOT EXISTS sigp_depositi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fascicolo_id TEXT,
    ufficio_id INTEGER,
    schema_version_id INTEGER,
    tipo_procedimento TEXT,
    tipo_atto TEXT,
    stato TEXT NOT NULL DEFAULT 'bozza',
    xml_path TEXT,
    busta_path TEXT,
    esito TEXT,
    errori_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ufficio_id) REFERENCES sigp_uffici(id),
    FOREIGN KEY (schema_version_id) REFERENCES sigp_schema_versions(id)
);

CREATE TABLE IF NOT EXISTS sigp_allegati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deposito_id INTEGER NOT NULL,
    nome_file TEXT NOT NULL,
    path_file TEXT NOT NULL,
    tipo_allegato TEXT,
    mime_type TEXT,
    sha256 TEXT,
    pdfa_ok INTEGER DEFAULT 0 CHECK (pdfa_ok IN (0,1)),
    firmato INTEGER DEFAULT 0 CHECK (firmato IN (0,1)),
    dimensione_bytes INTEGER,
    obbligatorio INTEGER DEFAULT 0 CHECK (obbligatorio IN (0,1)),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deposito_id) REFERENCES sigp_depositi(id)
);

CREATE TABLE IF NOT EXISTS sigp_validazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deposito_id INTEGER NOT NULL,
    fase TEXT NOT NULL,
    ok INTEGER NOT NULL DEFAULT 0 CHECK (ok IN (0,1)),
    messaggio TEXT,
    dettagli_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deposito_id) REFERENCES sigp_depositi(id)
);

CREATE TABLE IF NOT EXISTS sigp_sync_fascicoli (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigp_uid TEXT NOT NULL UNIQUE,
    fascicolo_locale_id TEXT,
    ufficio_codice TEXT,
    ufficio TEXT,
    registro TEXT NOT NULL DEFAULT 'GDP',
    numero_rg TEXT,
    anno_rg TEXT,
    atto_introduttivo TEXT,
    rito TEXT,
    ruolo TEXT,
    materia TEXT,
    oggetto TEXT,
    giudice TEXT,
    sezione TEXT,
    stato TEXT,
    data_iscrizione TEXT,
    data_prima_comparizione TEXT,
    data_ultima_udienza TEXT,
    hash_snapshot TEXT NOT NULL,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_parti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigp_fascicolo_id INTEGER NOT NULL,
    ruolo TEXT,
    tipo TEXT,
    nome TEXT,
    cognome TEXT,
    denominazione TEXT,
    codice_fiscale TEXT,
    partita_iva TEXT,
    difensore TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sigp_fascicolo_id) REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sigp_sync_eventi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigp_fascicolo_id INTEGER NOT NULL,
    evento_uid TEXT,
    tipo_evento TEXT,
    descrizione TEXT,
    data_evento TEXT,
    data_udienza TEXT,
    esito TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sigp_fascicolo_id) REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sigp_sync_udienze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigp_fascicolo_id INTEGER NOT NULL,
    udienza_uid TEXT,
    data_udienza TEXT,
    ora TEXT,
    tipo TEXT,
    descrizione TEXT,
    esito TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sigp_fascicolo_id) REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sigp_sync_documenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigp_fascicolo_id INTEGER NOT NULL,
    documento_uid TEXT,
    id_deposito TEXT,
    id_repeatto TEXT,
    nome_file TEXT,
    nome_originario TEXT,
    sezione TEXT,
    classificazione TEXT,
    tipo_atto TEXT,
    data_deposito TEXT,
    data_documento TEXT,
    depositante TEXT,
    mime_type TEXT,
    dimensione_bytes INTEGER DEFAULT 0,
    scaricabile INTEGER DEFAULT 1 CHECK (scaricabile IN (0,1)),
    path_locale TEXT,
    sha256 TEXT,
    tags_json TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sigp_fascicolo_id) REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sigp_sync_comunicazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigp_fascicolo_id INTEGER NOT NULL,
    comunicazione_uid TEXT,
    tipo TEXT,
    oggetto TEXT,
    data_comunicazione TEXT,
    mittente TEXT,
    destinatario TEXT,
    raw_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sigp_fascicolo_id) REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sigp_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sigp_fascicolo_id INTEGER,
    azione TEXT NOT NULL,
    esito TEXT NOT NULL,
    messaggio TEXT,
    dettagli_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sigp_fascicolo_id) REFERENCES sigp_sync_fascicoli(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sigp_sync_fascicoli_rg
    ON sigp_sync_fascicoli (registro, anno_rg, numero_rg, ufficio_codice);
CREATE INDEX IF NOT EXISTS idx_sigp_sync_documenti_fascicolo
    ON sigp_sync_documenti (sigp_fascicolo_id, documento_uid);
CREATE INDEX IF NOT EXISTS idx_sigp_sync_eventi_fascicolo
    ON sigp_sync_eventi (sigp_fascicolo_id, data_evento);
CREATE INDEX IF NOT EXISTS idx_sigp_sync_udienze_fascicolo
    ON sigp_sync_udienze (sigp_fascicolo_id, data_udienza);

INSERT OR IGNORE INTO sigp_schema_versions (
    version,
    descrizione,
    path_locale,
    main_xsd,
    attivo,
    data_pubblicazione,
    fonte
) VALUES (
    '2024-08-27',
    'Schemi XSD SIGP - aggiornamento 27/08/2024',
    'integrations/sigp/schemas/2024-08-27/xsd',
    'Professionista.xsd',
    1,
    '2024-08-27',
    'https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3460'
);

COMMIT;
