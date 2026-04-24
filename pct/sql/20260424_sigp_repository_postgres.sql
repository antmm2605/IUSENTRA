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
