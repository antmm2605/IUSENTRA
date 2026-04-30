-- IUSENTRA - Registro uffici giudiziari e indirizzi telematici PEC - PostgreSQL

CREATE TABLE IF NOT EXISTS uffici_giudiziari (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    denominazione TEXT NOT NULL,
    tipo_ufficio TEXT NOT NULL DEFAULT '',
    comune TEXT NOT NULL DEFAULT '',
    provincia TEXT NOT NULL DEFAULT '',
    regione TEXT NOT NULL DEFAULT '',
    distretto TEXT NOT NULL DEFAULT '',
    codice_ufficio TEXT NOT NULL,
    codice_ministero TEXT NOT NULL DEFAULT '',
    fonte_prevalente TEXT NOT NULL DEFAULT 'PST',
    data_verifica TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (tenant_id, codice_ufficio)
);

CREATE TABLE IF NOT EXISTS indirizzi_telematici (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    ufficio_id TEXT NOT NULL REFERENCES uffici_giudiziari(id) ON DELETE CASCADE,
    pec TEXT NOT NULL,
    uso TEXT NOT NULL,
    fonte TEXT NOT NULL,
    url_fonte TEXT NOT NULL DEFAULT '',
    data_rilevazione TIMESTAMPTZ NOT NULL DEFAULT now(),
    attiva BOOLEAN NOT NULL DEFAULT true,
    note TEXT NOT NULL DEFAULT '',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (uso IN (
        'deposito_pct',
        'deposito_penale',
        'deposito_amministrativo',
        'deposito_tributario',
        'amministrativa',
        'protocollo',
        'verifica_manualizzata'
    )),
    CHECK (fonte IN ('PST', 'IPA', 'sito_ufficiale', 'bundle_interno', 'manuale')),
    UNIQUE (tenant_id, ufficio_id, pec, uso, fonte)
);

CREATE TABLE IF NOT EXISTS uffici_giudiziari_verifiche (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    verificato_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    modalita TEXT NOT NULL DEFAULT '',
    sorgente TEXT NOT NULL DEFAULT '',
    ok BOOLEAN NOT NULL DEFAULT false,
    n_variazioni INTEGER NOT NULL DEFAULT 0,
    bundle_n INTEGER NOT NULL DEFAULT 0,
    remoto_n INTEGER NOT NULL DEFAULT 0,
    messaggio TEXT NOT NULL DEFAULT '',
    report_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS uffici_giudiziari_variazioni (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT '',
    verifica_id TEXT NOT NULL REFERENCES uffici_giudiziari_verifiche(id) ON DELETE CASCADE,
    codice_ufficio TEXT NOT NULL DEFAULT '',
    tipo_variazione TEXT NOT NULL,
    uso TEXT NOT NULL DEFAULT '',
    fonte_prevalente TEXT NOT NULL DEFAULT '',
    valore_precedente TEXT NOT NULL DEFAULT '',
    valore_nuovo TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_uffici_giudiziari_tipo ON uffici_giudiziari(tenant_id, tipo_ufficio);
CREATE INDEX IF NOT EXISTS idx_uffici_giudiziari_distretto ON uffici_giudiziari(tenant_id, distretto);
CREATE INDEX IF NOT EXISTS idx_indirizzi_telematici_uso ON indirizzi_telematici(tenant_id, uso, attiva);
CREATE INDEX IF NOT EXISTS idx_indirizzi_telematici_pec ON indirizzi_telematici(pec);
CREATE INDEX IF NOT EXISTS idx_uffici_verifiche_tenant ON uffici_giudiziari_verifiche(tenant_id, verificato_il);
