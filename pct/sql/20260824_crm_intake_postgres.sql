-- Intake CRM ed Entity Graph - PostgreSQL
-- Fonte operativa: database del tenant. Il JSON storico resta solo mirror.

-- Registro delle migrazioni runtime: mantiene la stessa semantica SQLite e
-- impedisce il reinserimento di archivi storici già consolidati.
CREATE TABLE IF NOT EXISTS crm_runtime_migrations (
    migration_key TEXT PRIMARY KEY,
    source_path TEXT NOT NULL DEFAULT '',
    applied_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS crm_leads (
    id TEXT PRIMARY KEY,
    denominazione TEXT NOT NULL,
    codice_fiscale TEXT NOT NULL DEFAULT '',
    partita_iva TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    telefono TEXT NOT NULL DEFAULT '',
    fonte TEXT NOT NULL DEFAULT 'altro',
    materia TEXT NOT NULL DEFAULT '',
    esigenza TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL DEFAULT 'NUOVO',
    conflitto_verificato BOOLEAN NOT NULL DEFAULT FALSE,
    conflitto_esito_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    cliente_id TEXT NOT NULL DEFAULT '',
    preventivo_id TEXT NOT NULL DEFAULT '',
    motivo_perso TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    referente TEXT NOT NULL DEFAULT '',
    versione INTEGER NOT NULL DEFAULT 1,
    creato_il TIMESTAMPTZ NOT NULL,
    modificato_il TIMESTAMPTZ NOT NULL,
    dati_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_crm_leads_stato ON crm_leads(stato, creato_il DESC);
CREATE INDEX IF NOT EXISTS idx_crm_leads_codice_fiscale ON crm_leads(codice_fiscale);
CREATE INDEX IF NOT EXISTS idx_crm_leads_partita_iva ON crm_leads(partita_iva);

CREATE TABLE IF NOT EXISTS entity_nodes (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL DEFAULT '',
    codice_fiscale TEXT NOT NULL DEFAULT '',
    partita_iva TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    creato_il TIMESTAMPTZ NOT NULL,
    modificato_il TIMESTAMPTZ NOT NULL,
    UNIQUE(source_type, source_id)
);
CREATE INDEX IF NOT EXISTS idx_entity_nodes_identity ON entity_nodes(codice_fiscale, partita_iva, normalized_name);

CREATE TABLE IF NOT EXISTS entity_relationships (
    id TEXT PRIMARY KEY,
    from_entity_id TEXT NOT NULL REFERENCES entity_nodes(id) ON DELETE CASCADE,
    to_entity_id TEXT NOT NULL REFERENCES entity_nodes(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ATTIVA',
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    creato_il TIMESTAMPTZ NOT NULL,
    modificato_il TIMESTAMPTZ NOT NULL,
    UNIQUE(from_entity_id, to_entity_id, relationship_type, source_type, source_id)
);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_from ON entity_relationships(from_entity_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_to ON entity_relationships(to_entity_id, relationship_type);

CREATE TABLE IF NOT EXISTS intake_compliance_assessments (
    id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL DEFAULT '',
    assessment_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DA_VALUTARE',
    source_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    creato_il TIMESTAMPTZ NOT NULL,
    modificato_il TIMESTAMPTZ NOT NULL,
    UNIQUE(lead_id, assessment_type)
);
CREATE INDEX IF NOT EXISTS idx_intake_compliance_lead ON intake_compliance_assessments(lead_id, assessment_type);

CREATE TABLE IF NOT EXISTS intake_compliance_audit (
    id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    creato_il TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intake_compliance_audit_lead ON intake_compliance_audit(lead_id, creato_il DESC);

-- Barriere informative: misura organizzativa di riservatezza legata al lead
-- e alla relativa entità del grafo. Non sostituisce la decisione di
-- astensione ex art. 24 CDF, che resta nel controllo conflitti.
CREATE TABLE IF NOT EXISTS ethical_walls (
    id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
    subject_entity_id TEXT NOT NULL REFERENCES entity_nodes(id) ON DELETE RESTRICT,
    titolo TEXT NOT NULL,
    motivazione TEXT NOT NULL,
    stato TEXT NOT NULL DEFAULT 'ATTIVA',
    creato_da TEXT NOT NULL,
    creato_il TIMESTAMPTZ NOT NULL,
    modificato_il TIMESTAMPTZ NOT NULL,
    revocato_da TEXT NOT NULL DEFAULT '',
    revocato_il TEXT NOT NULL DEFAULT '',
    motivazione_revoca TEXT NOT NULL DEFAULT '',
    versione INTEGER NOT NULL DEFAULT 1,
    UNIQUE(lead_id)
);
CREATE INDEX IF NOT EXISTS idx_ethical_walls_subject ON ethical_walls(subject_entity_id, stato);

CREATE TABLE IF NOT EXISTS ethical_wall_members (
    id TEXT PRIMARY KEY,
    wall_id TEXT NOT NULL REFERENCES ethical_walls(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    access_level TEXT NOT NULL DEFAULT 'AUTORIZZATO',
    aggiunto_da TEXT NOT NULL,
    aggiunto_il TIMESTAMPTZ NOT NULL,
    UNIQUE(wall_id, username)
);
CREATE INDEX IF NOT EXISTS idx_ethical_wall_members_access ON ethical_wall_members(wall_id, username);

CREATE TABLE IF NOT EXISTS ethical_wall_audit (
    id TEXT PRIMARY KEY,
    wall_id TEXT NOT NULL REFERENCES ethical_walls(id) ON DELETE CASCADE,
    lead_id TEXT NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    creato_il TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ethical_wall_audit_wall ON ethical_wall_audit(wall_id, creato_il DESC);

-- Adeguata verifica antiriciclaggio. PostgreSQL è fonte operativa del tenant;
-- il JSON storico è un mirror rigenerabile, non una seconda sorgente.
CREATE TABLE IF NOT EXISTS aml_verifications (
    id TEXT PRIMARY KEY,
    cliente_id TEXT NOT NULL,
    lead_id TEXT NOT NULL DEFAULT '',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    prestazione TEXT NOT NULL DEFAULT '',
    descrizione_prestazione TEXT NOT NULL DEFAULT '',
    scopo_natura TEXT NOT NULL DEFAULT '',
    cliente_pep BOOLEAN NOT NULL DEFAULT FALSE,
    paese_alto_rischio BOOLEAN NOT NULL DEFAULT FALSE,
    titolare_effettivo_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    indici_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    livello_scelto TEXT NOT NULL DEFAULT '',
    motivazione_scostamento TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL DEFAULT 'BOZZA',
    operatore TEXT NOT NULL DEFAULT '',
    data_verifica TEXT NOT NULL DEFAULT '',
    scadenza_controllo TEXT NOT NULL DEFAULT '',
    fine_rapporto TEXT NOT NULL DEFAULT '',
    fonte_normativa TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    versione INTEGER NOT NULL DEFAULT 1,
    creato_il TIMESTAMPTZ NOT NULL,
    modificato_il TIMESTAMPTZ NOT NULL,
    dati_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_aml_verifications_cliente ON aml_verifications(cliente_id, modificato_il DESC);
CREATE INDEX IF NOT EXISTS idx_aml_verifications_lead ON aml_verifications(lead_id, modificato_il DESC);
CREATE INDEX IF NOT EXISTS idx_aml_verifications_rinnovo ON aml_verifications(stato, scadenza_controllo);

CREATE TABLE IF NOT EXISTS aml_screening_evidence (
    id TEXT PRIMARY KEY,
    verifica_id TEXT NOT NULL REFERENCES aml_verifications(id) ON DELETE CASCADE,
    provider_key TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_version TEXT NOT NULL DEFAULT '',
    snapshot_hash TEXT NOT NULL DEFAULT '',
    subject_label TEXT NOT NULL DEFAULT '',
    outcome TEXT NOT NULL DEFAULT 'NON_ESEGUITO',
    matches_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    checked_by TEXT NOT NULL DEFAULT '',
    checked_at TIMESTAMPTZ NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_aml_screening_verifica ON aml_screening_evidence(verifica_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS aml_audit (
    id TEXT PRIMARY KEY,
    verifica_id TEXT NOT NULL REFERENCES aml_verifications(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    creato_il TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aml_audit_verifica ON aml_audit(verifica_id, creato_il DESC);
