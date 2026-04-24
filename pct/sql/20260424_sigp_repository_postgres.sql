CREATE TABLE IF NOT EXISTS sigp_schema_versions (
    id BIGSERIAL PRIMARY KEY,
    version TEXT NOT NULL UNIQUE,
    descrizione TEXT,
    path_locale TEXT NOT NULL,
    main_xsd TEXT,
    attivo INTEGER NOT NULL DEFAULT 0 CHECK (attivo IN (0,1)),
    data_pubblicazione TEXT,
    fonte TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_uffici (
    id BIGSERIAL PRIMARY KEY,
    codice_ufficio TEXT NOT NULL UNIQUE,
    nome_ufficio TEXT NOT NULL,
    distretto TEXT,
    ambiente TEXT NOT NULL DEFAULT 'produzione',
    attivo INTEGER NOT NULL DEFAULT 1 CHECK (attivo IN (0,1))
);

CREATE TABLE IF NOT EXISTS sigp_depositi (
    id BIGSERIAL PRIMARY KEY,
    fascicolo_id TEXT,
    ufficio_id BIGINT REFERENCES sigp_uffici(id),
    schema_version_id BIGINT REFERENCES sigp_schema_versions(id),
    tipo_procedimento TEXT,
    tipo_atto TEXT,
    stato TEXT NOT NULL DEFAULT 'bozza',
    xml_path TEXT,
    busta_path TEXT,
    esito TEXT,
    errori_json TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_allegati (
    id BIGSERIAL PRIMARY KEY,
    deposito_id BIGINT NOT NULL REFERENCES sigp_depositi(id),
    nome_file TEXT NOT NULL,
    path_file TEXT NOT NULL,
    tipo_allegato TEXT,
    mime_type TEXT,
    sha256 TEXT,
    pdfa_ok INTEGER DEFAULT 0 CHECK (pdfa_ok IN (0,1)),
    firmato INTEGER DEFAULT 0 CHECK (firmato IN (0,1)),
    dimensione_bytes INTEGER,
    obbligatorio INTEGER DEFAULT 0 CHECK (obbligatorio IN (0,1)),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_validazioni (
    id BIGSERIAL PRIMARY KEY,
    deposito_id BIGINT NOT NULL REFERENCES sigp_depositi(id),
    fase TEXT NOT NULL,
    ok INTEGER NOT NULL DEFAULT 0 CHECK (ok IN (0,1)),
    messaggio TEXT,
    dettagli_json TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_fascicoli (
    id BIGSERIAL PRIMARY KEY,
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
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_parti (
    id BIGSERIAL PRIMARY KEY,
    sigp_fascicolo_id BIGINT NOT NULL REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE,
    ruolo TEXT,
    tipo TEXT,
    nome TEXT,
    cognome TEXT,
    denominazione TEXT,
    codice_fiscale TEXT,
    partita_iva TEXT,
    difensore TEXT,
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_eventi (
    id BIGSERIAL PRIMARY KEY,
    sigp_fascicolo_id BIGINT NOT NULL REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE,
    evento_uid TEXT,
    tipo_evento TEXT,
    descrizione TEXT,
    data_evento TEXT,
    data_udienza TEXT,
    esito TEXT,
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_udienze (
    id BIGSERIAL PRIMARY KEY,
    sigp_fascicolo_id BIGINT NOT NULL REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE,
    udienza_uid TEXT,
    data_udienza TEXT,
    ora TEXT,
    tipo TEXT,
    descrizione TEXT,
    esito TEXT,
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_documenti (
    id BIGSERIAL PRIMARY KEY,
    sigp_fascicolo_id BIGINT NOT NULL REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE,
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
    tags_json JSONB,
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_comunicazioni (
    id BIGSERIAL PRIMARY KEY,
    sigp_fascicolo_id BIGINT NOT NULL REFERENCES sigp_sync_fascicoli(id) ON DELETE CASCADE,
    comunicazione_uid TEXT,
    tipo TEXT,
    oggetto TEXT,
    data_comunicazione TEXT,
    mittente TEXT,
    destinatario TEXT,
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sigp_sync_log (
    id BIGSERIAL PRIMARY KEY,
    sigp_fascicolo_id BIGINT REFERENCES sigp_sync_fascicoli(id) ON DELETE SET NULL,
    azione TEXT NOT NULL,
    esito TEXT NOT NULL,
    messaggio TEXT,
    dettagli_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sigp_sync_fascicoli_rg
    ON sigp_sync_fascicoli (registro, anno_rg, numero_rg, ufficio_codice);
CREATE INDEX IF NOT EXISTS idx_sigp_sync_documenti_fascicolo
    ON sigp_sync_documenti (sigp_fascicolo_id, documento_uid);
CREATE INDEX IF NOT EXISTS idx_sigp_sync_eventi_fascicolo
    ON sigp_sync_eventi (sigp_fascicolo_id, data_evento);
CREATE INDEX IF NOT EXISTS idx_sigp_sync_udienze_fascicolo
    ON sigp_sync_udienze (sigp_fascicolo_id, data_udienza);

INSERT INTO sigp_schema_versions (
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
) ON CONFLICT (version) DO NOTHING;
