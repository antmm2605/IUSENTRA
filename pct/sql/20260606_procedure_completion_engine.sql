-- =============================================================================
--  Procedure Completion Engine - schema SQLite idempotente.
--
--  Completa le schede operative delle procedure partendo da catalogo PST/XSD,
--  template atti, knowledge pipeline e fonti ufficiali governate. Ogni scheda
--  nasce come bozza per revisione avvocato: la pubblicazione richiede fonti
--  ufficiali/tecniche validate, citazioni verificabili e approvazione umana.
--
--  Regole: tenant_id sempre gestito server-side; audit con payload sanificato
--  (mai token, password, PEC reali, codici fiscali, IBAN, path locali).
-- =============================================================================
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS procedure_completion_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    template_code TEXT,
    mode TEXT NOT NULL DEFAULT 'preview',
    status TEXT NOT NULL DEFAULT 'completed',
    requested_by TEXT,
    request_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pce_runs_tenant ON procedure_completion_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pce_runs_code ON procedure_completion_runs(procedure_code);

CREATE TABLE IF NOT EXISTS procedure_completion_cards (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    tenant_id TEXT,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    template_code TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    risk_level TEXT NOT NULL DEFAULT 'medium',
    confidence TEXT NOT NULL DEFAULT 'LOW',
    payload_json TEXT NOT NULL DEFAULT '{}',
    validation_report_json TEXT NOT NULL DEFAULT '{}',
    reviewer TEXT,
    reviewed_at TEXT,
    review_reason TEXT,
    published_at TEXT,
    source_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES procedure_completion_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_pce_cards_tenant ON procedure_completion_cards(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pce_cards_code ON procedure_completion_cards(procedure_code);
CREATE INDEX IF NOT EXISTS idx_pce_cards_status ON procedure_completion_cards(status);

CREATE TABLE IF NOT EXISTS procedure_completion_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    tenant_id TEXT,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    authority TEXT,
    trust_class TEXT,
    copyright_policy TEXT NOT NULL DEFAULT 'metadata_only',
    excerpt TEXT,
    origin TEXT,
    source_hash TEXT,
    last_checked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (card_id) REFERENCES procedure_completion_cards(id)
);
CREATE INDEX IF NOT EXISTS idx_pce_sources_card ON procedure_completion_sources(card_id);

CREATE TABLE IF NOT EXISTS procedure_completion_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    tenant_id TEXT,
    riferimento TEXT NOT NULL,
    atto_normativo TEXT,
    articolo TEXT,
    comma TEXT,
    versione TEXT,
    url TEXT,
    source_id TEXT,
    snippet TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (card_id) REFERENCES procedure_completion_cards(id)
);
CREATE INDEX IF NOT EXISTS idx_pce_citations_card ON procedure_completion_citations(card_id);

CREATE TABLE IF NOT EXISTS procedure_completion_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    tenant_id TEXT,
    codice_gap TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    severita TEXT NOT NULL DEFAULT 'warning',
    azione_suggerita TEXT,
    risolto INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (card_id) REFERENCES procedure_completion_cards(id)
);
CREATE INDEX IF NOT EXISTS idx_pce_gaps_card ON procedure_completion_gaps(card_id);
CREATE INDEX IF NOT EXISTS idx_pce_gaps_severita ON procedure_completion_gaps(severita);

CREATE TABLE IF NOT EXISTS procedure_completion_template_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    tenant_id TEXT,
    template_id TEXT NOT NULL,
    titolo TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    selezionato INTEGER NOT NULL DEFAULT 0,
    motivi_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (card_id) REFERENCES procedure_completion_cards(id)
);
CREATE INDEX IF NOT EXISTS idx_pce_template_links_card ON procedure_completion_template_links(card_id);

CREATE TABLE IF NOT EXISTS procedure_completion_review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    tenant_id TEXT,
    evento TEXT NOT NULL,
    reviewer TEXT,
    reason TEXT,
    from_status TEXT,
    to_status TEXT,
    event_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (card_id) REFERENCES procedure_completion_cards(id)
);
CREATE INDEX IF NOT EXISTS idx_pce_review_events_card ON procedure_completion_review_events(card_id);

CREATE TABLE IF NOT EXISTS procedure_completion_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    action TEXT NOT NULL,
    actor TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    event_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pce_audit_entity ON procedure_completion_audit_log(entity_type, entity_id);
