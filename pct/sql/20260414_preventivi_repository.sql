PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS preventivi_repository_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preventivi_workflow_states (
    scope TEXT NOT NULL,
    state_code TEXT NOT NULL,
    label TEXT NOT NULL,
    operational_meaning TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0,1)),
    is_terminal INTEGER NOT NULL DEFAULT 0 CHECK (is_terminal IN (0,1)),
    allowed_actions_json TEXT NOT NULL DEFAULT '[]',
    next_actions_json TEXT NOT NULL DEFAULT '[]',
    channel_modes_json TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (scope, state_code)
);

CREATE TABLE IF NOT EXISTS preventivi_field_map (
    scope TEXT NOT NULL,
    field_name TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT NOT NULL,
    section_name TEXT NOT NULL,
    help_text TEXT NOT NULL DEFAULT '',
    required_runtime INTEGER NOT NULL DEFAULT 0 CHECK (required_runtime IN (0,1)),
    derived INTEGER NOT NULL DEFAULT 0 CHECK (derived IN (0,1)),
    source_model TEXT NOT NULL,
    step_key TEXT NOT NULL DEFAULT '',
    enum_values_json TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (scope, field_name)
);

CREATE TABLE IF NOT EXISTS preventivi_rules (
    rule_code TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    formula TEXT NOT NULL DEFAULT '',
    operational_text TEXT NOT NULL,
    warning_text TEXT NOT NULL DEFAULT '',
    deterministic INTEGER NOT NULL DEFAULT 1 CHECK (deterministic IN (0,1)),
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS preventivi_wizard_steps (
    step_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    section_names_json TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS preventivi_practice_catalog (
    practice_id TEXT PRIMARY KEY,
    wizard_area TEXT NOT NULL,
    area TEXT NOT NULL,
    label TEXT NOT NULL,
    tipo_compenso_default TEXT NOT NULL DEFAULT '',
    richiede_valore INTEGER NOT NULL DEFAULT 0 CHECK (richiede_valore IN (0,1)),
    grado_default TEXT NOT NULL DEFAULT '',
    fasi_default_json TEXT NOT NULL DEFAULT '[]',
    fasi_default_keys_json TEXT NOT NULL DEFAULT '[]',
    base_normativa TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    when_to_use TEXT NOT NULL DEFAULT '',
    checklist_json TEXT NOT NULL DEFAULT '[]',
    normative_references_json TEXT NOT NULL DEFAULT '[]',
    regole_tariffarie_json TEXT NOT NULL DEFAULT '[]',
    tassonomia_json TEXT NOT NULL DEFAULT '{}',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS preventivi_records (
    preventivo_id TEXT PRIMARY KEY,
    numero TEXT NOT NULL,
    data_emissione TEXT NOT NULL DEFAULT '',
    data_scadenza TEXT NOT NULL DEFAULT '',
    id_cliente TEXT NOT NULL DEFAULT '',
    id_fascicolo TEXT NOT NULL DEFAULT '',
    oggetto TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL DEFAULT '',
    workflow_channel TEXT NOT NULL DEFAULT '',
    workflow_channel_label TEXT NOT NULL DEFAULT '',
    tipo_compenso TEXT NOT NULL DEFAULT '',
    tipo_procedimento TEXT NOT NULL DEFAULT '',
    area_pratica TEXT NOT NULL DEFAULT '',
    id_pratica TEXT NOT NULL DEFAULT '',
    procedura_operativa_codice TEXT NOT NULL DEFAULT '',
    procedura_operativa_nome TEXT NOT NULL DEFAULT '',
    subbranch_operativa_codice TEXT NOT NULL DEFAULT '',
    workflow_operativo_codice TEXT NOT NULL DEFAULT '',
    copertura_operativa TEXT NOT NULL DEFAULT '',
    canale_operativo TEXT NOT NULL DEFAULT '',
    registro_operativo TEXT NOT NULL DEFAULT '',
    valore_controversia REAL NOT NULL DEFAULT 0,
    tariffa_oraria REAL NOT NULL DEFAULT 0,
    ore_stimate REAL NOT NULL DEFAULT 0,
    complessita TEXT NOT NULL DEFAULT '',
    applica_cassa INTEGER NOT NULL DEFAULT 1 CHECK (applica_cassa IN (0,1)),
    applica_iva INTEGER NOT NULL DEFAULT 1 CHECK (applica_iva IN (0,1)),
    anticipazioni_art15 REAL NOT NULL DEFAULT 0,
    imponibile REAL NOT NULL DEFAULT 0,
    cassa_forense REAL NOT NULL DEFAULT 0,
    base_iva REAL NOT NULL DEFAULT 0,
    iva REAL NOT NULL DEFAULT 0,
    totale REAL NOT NULL DEFAULT 0,
    piano_pagamenti_count INTEGER NOT NULL DEFAULT 0,
    clausola_controversie_attiva INTEGER NOT NULL DEFAULT 0 CHECK (clausola_controversie_attiva IN (0,1)),
    clausola_controversie_modello TEXT NOT NULL DEFAULT '',
    token_portale_present INTEGER NOT NULL DEFAULT 0 CHECK (token_portale_present IN (0,1)),
    inviato_cliente_il TEXT NOT NULL DEFAULT '',
    accettato_il TEXT NOT NULL DEFAULT '',
    versione INTEGER NOT NULL DEFAULT 1,
    id_preventivo_precedente TEXT NOT NULL DEFAULT '',
    wizard_step TEXT NOT NULL DEFAULT '',
    wizard_step_label TEXT NOT NULL DEFAULT '',
    classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]',
    classificazioni_tassonomiche_count INTEGER NOT NULL DEFAULT 0,
    campi_mancanti_json TEXT NOT NULL DEFAULT '[]',
    warning_json TEXT NOT NULL DEFAULT '[]',
    next_action TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS conferimenti_records (
    conferimento_id TEXT PRIMARY KEY,
    numero TEXT NOT NULL,
    data_incarico TEXT NOT NULL DEFAULT '',
    id_preventivo TEXT NOT NULL DEFAULT '',
    id_cliente TEXT NOT NULL DEFAULT '',
    id_fascicolo TEXT NOT NULL DEFAULT '',
    oggetto TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL DEFAULT '',
    workflow_channel TEXT NOT NULL DEFAULT '',
    workflow_channel_label TEXT NOT NULL DEFAULT '',
    tipo_compenso TEXT NOT NULL DEFAULT '',
    tipo_procedimento TEXT NOT NULL DEFAULT '',
    area_pratica TEXT NOT NULL DEFAULT '',
    id_pratica TEXT NOT NULL DEFAULT '',
    procedura_operativa_codice TEXT NOT NULL DEFAULT '',
    procedura_operativa_nome TEXT NOT NULL DEFAULT '',
    subbranch_operativa_codice TEXT NOT NULL DEFAULT '',
    workflow_operativo_codice TEXT NOT NULL DEFAULT '',
    copertura_operativa TEXT NOT NULL DEFAULT '',
    canale_operativo TEXT NOT NULL DEFAULT '',
    registro_operativo TEXT NOT NULL DEFAULT '',
    compenso_pattuito REAL NOT NULL DEFAULT 0,
    informativa_art13_resa INTEGER NOT NULL DEFAULT 0 CHECK (informativa_art13_resa IN (0,1)),
    clausola_adr_resa INTEGER NOT NULL DEFAULT 0 CHECK (clausola_adr_resa IN (0,1)),
    firma_cliente_richiesta INTEGER NOT NULL DEFAULT 1 CHECK (firma_cliente_richiesta IN (0,1)),
    firma_cliente_eseguita INTEGER NOT NULL DEFAULT 0 CHECK (firma_cliente_eseguita IN (0,1)),
    firma_cliente_il TEXT NOT NULL DEFAULT '',
    fascicolo_aperto_il TEXT NOT NULL DEFAULT '',
    clausola_controversie_attiva INTEGER NOT NULL DEFAULT 0 CHECK (clausola_controversie_attiva IN (0,1)),
    clausola_controversie_modello TEXT NOT NULL DEFAULT '',
    classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]',
    classificazioni_tassonomiche_count INTEGER NOT NULL DEFAULT 0,
    warning_json TEXT NOT NULL DEFAULT '[]',
    next_action TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_preventivi_workflow_states_scope
ON preventivi_workflow_states(scope, sort_order);

CREATE INDEX IF NOT EXISTS idx_preventivi_field_map_scope
ON preventivi_field_map(scope, section_name, sort_order);

CREATE INDEX IF NOT EXISTS idx_preventivi_rules_category
ON preventivi_rules(category, sort_order);

CREATE INDEX IF NOT EXISTS idx_preventivi_wizard_steps_order
ON preventivi_wizard_steps(sort_order);

CREATE INDEX IF NOT EXISTS idx_preventivi_practice_catalog_area
ON preventivi_practice_catalog(wizard_area, area, label);

CREATE INDEX IF NOT EXISTS idx_preventivi_records_state
ON preventivi_records(stato, workflow_channel, data_emissione);

CREATE INDEX IF NOT EXISTS idx_preventivi_records_practice
ON preventivi_records(id_pratica, area_pratica);

CREATE INDEX IF NOT EXISTS idx_conferimenti_records_state
ON conferimenti_records(stato, workflow_channel, data_incarico);

CREATE INDEX IF NOT EXISTS idx_conferimenti_records_practice
ON conferimenti_records(id_pratica, area_pratica);

COMMIT;
