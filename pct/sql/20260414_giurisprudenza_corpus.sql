PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS fonti_giurisprudenza (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    tipo_fonte TEXT NOT NULL CHECK (
        tipo_fonte IN (
            'ufficiale',
            'istituzionale',
            'banca_dati_interna',
            'import_manuale',
            'altra'
        )
    ),
    ente TEXT,
    url_home TEXT,
    url_ricerca TEXT,
    url_feed TEXT,
    paese TEXT NOT NULL DEFAULT 'IT',
    attiva INTEGER NOT NULL DEFAULT 1 CHECK (attiva IN (0,1)),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    descrizione TEXT,
    parent_id INTEGER REFERENCES materie(id) ON DELETE SET NULL,
    livello INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    attiva INTEGER NOT NULL DEFAULT 1 CHECK (attiva IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sottocategorie_materia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    materia_id INTEGER NOT NULL REFERENCES materie(id) ON DELETE CASCADE,
    codice TEXT NOT NULL,
    nome TEXT NOT NULL,
    descrizione TEXT,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    attiva INTEGER NOT NULL DEFAULT 1 CHECK (attiva IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(materia_id, codice)
);

CREATE TABLE IF NOT EXISTS sentenze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte_id INTEGER NOT NULL REFERENCES fonti_giurisprudenza(id) ON DELETE RESTRICT,
    uuid_interno TEXT NOT NULL UNIQUE,
    ecli TEXT UNIQUE,
    numero_sentenza TEXT,
    anno_sentenza INTEGER,
    numero_ruolo TEXT,
    numero_registro TEXT,
    organo_giudicante TEXT NOT NULL,
    sezione TEXT,
    collegio TEXT,
    relatore TEXT,
    presidente TEXT,
    data_decisione TEXT,
    data_deposito TEXT,
    data_pubblicazione TEXT,
    data_importazione TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    area_diritto TEXT,
    materia_principale TEXT,
    sottomateria_principale TEXT,
    rito TEXT,
    grado_giudizio TEXT,
    tipo_provvedimento TEXT NOT NULL CHECK (
        tipo_provvedimento IN (
            'sentenza',
            'ordinanza',
            'decreto',
            'provvedimento',
            'massima',
            'altro'
        )
    ),
    titolo TEXT,
    oggetto TEXT,
    abstract TEXT,
    principio_sintetico TEXT,
    massima_ufficiale TEXT,
    testo_integrale TEXT,
    esito TEXT,
    orientamento TEXT NOT NULL DEFAULT 'non_classificato' CHECK (
        orientamento IN (
            'favorevole',
            'contrario',
            'misto',
            'neutro',
            'non_classificato'
        )
    ),
    rilevanza INTEGER NOT NULL DEFAULT 0,
    precedente_guida INTEGER NOT NULL DEFAULT 0 CHECK (precedente_guida IN (0,1)),
    sezioni_unite INTEGER NOT NULL DEFAULT 0 CHECK (sezioni_unite IN (0,1)),
    nomofilattica INTEGER NOT NULL DEFAULT 0 CHECK (nomofilattica IN (0,1)),
    stato_verifica TEXT NOT NULL DEFAULT 'da_verificare' CHECK (
        stato_verifica IN (
            'verificata',
            'parzialmente_verificata',
            'da_verificare',
            'non_verificata',
            'errore_fonte'
        )
    ),
    fonte_ufficiale_confermata INTEGER NOT NULL DEFAULT 0 CHECK (fonte_ufficiale_confermata IN (0,1)),
    pdf_ufficiale_presente INTEGER NOT NULL DEFAULT 0 CHECK (pdf_ufficiale_presente IN (0,1)),
    testo_integrale_presente INTEGER NOT NULL DEFAULT 0 CHECK (testo_integrale_presente IN (0,1)),
    url_pagina_ufficiale TEXT,
    url_pdf_ufficiale TEXT,
    url_html_ufficiale TEXT,
    hash_contenuto TEXT,
    hash_pdf TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sentenze_fonte_numero_anno_organo
ON sentenze(
    fonte_id,
    organo_giudicante,
    COALESCE(sezione, ''),
    COALESCE(numero_sentenza, ''),
    COALESCE(anno_sentenza, 0),
    COALESCE(data_deposito, '')
);

CREATE INDEX IF NOT EXISTS idx_sentenze_organo ON sentenze(organo_giudicante);
CREATE INDEX IF NOT EXISTS idx_sentenze_sezione ON sentenze(sezione);
CREATE INDEX IF NOT EXISTS idx_sentenze_data_deposito ON sentenze(data_deposito);
CREATE INDEX IF NOT EXISTS idx_sentenze_data_pubblicazione ON sentenze(data_pubblicazione);
CREATE INDEX IF NOT EXISTS idx_sentenze_tipo ON sentenze(tipo_provvedimento);
CREATE INDEX IF NOT EXISTS idx_sentenze_area_materia ON sentenze(area_diritto, materia_principale, sottomateria_principale);
CREATE INDEX IF NOT EXISTS idx_sentenze_stato_verifica ON sentenze(stato_verifica);
CREATE INDEX IF NOT EXISTS idx_sentenze_ecli ON sentenze(ecli);

CREATE TABLE IF NOT EXISTS documenti_sentenza (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentenza_id INTEGER NOT NULL REFERENCES sentenze(id) ON DELETE CASCADE,
    tipo_documento TEXT NOT NULL CHECK (
        tipo_documento IN (
            'pdf_ufficiale',
            'html_ufficiale',
            'testo_plain',
            'massima_pdf',
            'scheda',
            'allegato',
            'altro'
        )
    ),
    titolo TEXT,
    nome_file TEXT,
    mime_type TEXT,
    url_origine TEXT,
    path_locale TEXT,
    dimensione_bytes INTEGER,
    sha256 TEXT,
    testo_estratto TEXT,
    testo_estratto_chars INTEGER NOT NULL DEFAULT 0,
    pages INTEGER,
    lingua TEXT NOT NULL DEFAULT 'it',
    ufficiale INTEGER NOT NULL DEFAULT 1 CHECK (ufficiale IN (0,1)),
    scaricato INTEGER NOT NULL DEFAULT 0 CHECK (scaricato IN (0,1)),
    valido INTEGER NOT NULL DEFAULT 1 CHECK (valido IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documenti_sentenza_sentenza ON documenti_sentenza(sentenza_id);
CREATE INDEX IF NOT EXISTS idx_documenti_sentenza_tipo ON documenti_sentenza(tipo_documento);

CREATE TABLE IF NOT EXISTS massime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentenza_id INTEGER NOT NULL REFERENCES sentenze(id) ON DELETE CASCADE,
    testo TEXT NOT NULL,
    sintetica TEXT,
    ufficiale INTEGER NOT NULL DEFAULT 0 CHECK (ufficiale IN (0,1)),
    fonte_massima TEXT,
    numero_massima TEXT,
    anno_massima INTEGER,
    stato_verifica TEXT NOT NULL DEFAULT 'da_verificare' CHECK (
        stato_verifica IN (
            'verificata',
            'parzialmente_verificata',
            'da_verificare',
            'non_verificata'
        )
    ),
    principale INTEGER NOT NULL DEFAULT 0 CHECK (principale IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_massime_sentenza ON massime(sentenza_id);

CREATE TABLE IF NOT EXISTS principi_diritto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentenza_id INTEGER NOT NULL REFERENCES sentenze(id) ON DELETE CASCADE,
    testo TEXT NOT NULL,
    formulazione_breve TEXT,
    ufficiale INTEGER NOT NULL DEFAULT 0 CHECK (ufficiale IN (0,1)),
    estratto_da_testo INTEGER NOT NULL DEFAULT 0 CHECK (estratto_da_testo IN (0,1)),
    livello_affidabilita INTEGER NOT NULL DEFAULT 50,
    tema TEXT,
    sotto_tema TEXT,
    favorevole_tesi_attorea INTEGER CHECK (favorevole_tesi_attorea IN (0,1)),
    favorevole_tesi_convenuta INTEGER CHECK (favorevole_tesi_convenuta IN (0,1)),
    principale INTEGER NOT NULL DEFAULT 0 CHECK (principale IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_principi_sentenza ON principi_diritto(sentenza_id);
CREATE INDEX IF NOT EXISTS idx_principi_tema ON principi_diritto(tema, sotto_tema);

CREATE TABLE IF NOT EXISTS norme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_norma TEXT NOT NULL,
    sigla TEXT,
    articolo TEXT,
    comma TEXT,
    lettera TEXT,
    rubrica TEXT,
    testo_riferimento TEXT,
    ecli_normativo TEXT,
    url_ufficiale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_norme_univoca
ON norme(
    COALESCE(tipo_norma, ''),
    COALESCE(sigla, ''),
    COALESCE(articolo, ''),
    COALESCE(comma, ''),
    COALESCE(lettera, '')
);

CREATE TABLE IF NOT EXISTS sentenza_norme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentenza_id INTEGER NOT NULL REFERENCES sentenze(id) ON DELETE CASCADE,
    norma_id INTEGER NOT NULL REFERENCES norme(id) ON DELETE CASCADE,
    tipo_richiamo TEXT NOT NULL DEFAULT 'citata' CHECK (
        tipo_richiamo IN (
            'citata',
            'applicata',
            'interpretata',
            'distinta',
            'superata',
            'richiamata'
        )
    ),
    primaria INTEGER NOT NULL DEFAULT 0 CHECK (primaria IN (0,1)),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sentenza_id, norma_id, tipo_richiamo)
);

CREATE INDEX IF NOT EXISTS idx_sentenza_norme_sentenza ON sentenza_norme(sentenza_id);
CREATE INDEX IF NOT EXISTS idx_sentenza_norme_norma ON sentenza_norme(norma_id);

CREATE TABLE IF NOT EXISTS sentenza_precedenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentenza_id INTEGER NOT NULL REFERENCES sentenze(id) ON DELETE CASCADE,
    sentenza_citata_id INTEGER REFERENCES sentenze(id) ON DELETE SET NULL,
    riferimento_testuale TEXT NOT NULL,
    organo_giudicante TEXT,
    sezione TEXT,
    numero_sentenza TEXT,
    anno_sentenza INTEGER,
    data_sentenza TEXT,
    ecli TEXT,
    tipo_relazione TEXT NOT NULL DEFAULT 'citata' CHECK (
        tipo_relazione IN (
            'citata',
            'conforme',
            'difforme',
            'superata',
            'richiamata',
            'distinta',
            'segnalata'
        )
    ),
    verificata INTEGER NOT NULL DEFAULT 0 CHECK (verificata IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sentenza_precedenti_sentenza ON sentenza_precedenti(sentenza_id);

CREATE TABLE IF NOT EXISTS sentenza_materie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentenza_id INTEGER NOT NULL REFERENCES sentenze(id) ON DELETE CASCADE,
    materia_id INTEGER NOT NULL REFERENCES materie(id) ON DELETE CASCADE,
    sottocategoria_id INTEGER REFERENCES sottocategorie_materia(id) ON DELETE SET NULL,
    principale INTEGER NOT NULL DEFAULT 0 CHECK (principale IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sentenza_id, materia_id, sottocategoria_id)
);

CREATE INDEX IF NOT EXISTS idx_sentenza_materie_sentenza ON sentenza_materie(sentenza_id);

CREATE TABLE IF NOT EXISTS importazioni_giurisprudenza (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte_id INTEGER REFERENCES fonti_giurisprudenza(id) ON DELETE SET NULL,
    tipo_importazione TEXT NOT NULL CHECK (
        tipo_importazione IN (
            'crawler',
            'feed',
            'manuale',
            'api',
            'batch_pdf',
            'batch_html'
        )
    ),
    stato TEXT NOT NULL CHECK (
        stato IN (
            'avviata',
            'completata',
            'parziale',
            'errore'
        )
    ),
    query_origine TEXT,
    url_origine TEXT,
    file_origine TEXT,
    record_letti INTEGER NOT NULL DEFAULT 0,
    record_creati INTEGER NOT NULL DEFAULT 0,
    record_aggiornati INTEGER NOT NULL DEFAULT 0,
    record_scartati INTEGER NOT NULL DEFAULT 0,
    log_errore TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS verifiche_fonti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentenza_id INTEGER NOT NULL REFERENCES sentenze(id) ON DELETE CASCADE,
    fonte_id INTEGER REFERENCES fonti_giurisprudenza(id) ON DELETE SET NULL,
    tipo_verifica TEXT NOT NULL CHECK (
        tipo_verifica IN (
            'esistenza_url',
            'pdf_presente',
            'hash_documento',
            'metadati_coerenti',
            'ecli_coerente',
            'numero_data_coerenti',
            'verifica_manuale'
        )
    ),
    esito TEXT NOT NULL CHECK (
        esito IN (
            'ok',
            'warning',
            'errore'
        )
    ),
    dettaglio TEXT,
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checked_by TEXT NOT NULL DEFAULT 'system'
);

CREATE VIRTUAL TABLE IF NOT EXISTS sentenze_fts USING fts5(
    titolo,
    oggetto,
    abstract,
    principio_sintetico,
    massima_ufficiale,
    testo_integrale,
    content='',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS trg_sentenze_fts_ai
AFTER INSERT ON sentenze
BEGIN
    INSERT INTO sentenze_fts (
        rowid,
        titolo,
        oggetto,
        abstract,
        principio_sintetico,
        massima_ufficiale,
        testo_integrale
    )
    VALUES (
        NEW.id,
        COALESCE(NEW.titolo, ''),
        COALESCE(NEW.oggetto, ''),
        COALESCE(NEW.abstract, ''),
        COALESCE(NEW.principio_sintetico, ''),
        COALESCE(NEW.massima_ufficiale, ''),
        COALESCE(NEW.testo_integrale, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_sentenze_fts_au
AFTER UPDATE ON sentenze
BEGIN
    INSERT INTO sentenze_fts(
        sentenze_fts,
        rowid,
        titolo,
        oggetto,
        abstract,
        principio_sintetico,
        massima_ufficiale,
        testo_integrale
    )
    VALUES (
        'delete',
        OLD.id,
        COALESCE(OLD.titolo, ''),
        COALESCE(OLD.oggetto, ''),
        COALESCE(OLD.abstract, ''),
        COALESCE(OLD.principio_sintetico, ''),
        COALESCE(OLD.massima_ufficiale, ''),
        COALESCE(OLD.testo_integrale, '')
    );
    INSERT INTO sentenze_fts (
        rowid,
        titolo,
        oggetto,
        abstract,
        principio_sintetico,
        massima_ufficiale,
        testo_integrale
    )
    VALUES (
        NEW.id,
        COALESCE(NEW.titolo, ''),
        COALESCE(NEW.oggetto, ''),
        COALESCE(NEW.abstract, ''),
        COALESCE(NEW.principio_sintetico, ''),
        COALESCE(NEW.massima_ufficiale, ''),
        COALESCE(NEW.testo_integrale, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_sentenze_fts_ad
AFTER DELETE ON sentenze
BEGIN
    INSERT INTO sentenze_fts(
        sentenze_fts,
        rowid,
        titolo,
        oggetto,
        abstract,
        principio_sintetico,
        massima_ufficiale,
        testo_integrale
    )
    VALUES (
        'delete',
        OLD.id,
        COALESCE(OLD.titolo, ''),
        COALESCE(OLD.oggetto, ''),
        COALESCE(OLD.abstract, ''),
        COALESCE(OLD.principio_sintetico, ''),
        COALESCE(OLD.massima_ufficiale, ''),
        COALESCE(OLD.testo_integrale, '')
    );
END;

COMMIT;
