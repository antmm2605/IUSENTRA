"""
Catalogo strutturale relazionale del gestionale.

Questa base dati crea la fondazione comune per:
- classificazione procedurale
- motore tariffario forense versionato
- pratica economica e preventivo strutturato

In questa fase il seed resta volutamente leggero:
- anagrafiche base
- versioni e fasi
- canali/portali
- spese standard e controlli minimi

Le associazioni puntuali ai cataloghi legacy, alle tabelle ministeriali e ai
procedimenti reali verranno curate in un passaggio successivo.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime


STRUCTURAL_TABLES = [
    "preventivo_controllo_map",
    "controlli_forensi",
    "preventivo_accettazioni",
    "preventivo_snapshot",
    "accordi_compenso",
    "preventivo_accessori",
    "preventivo_voci",
    "preventivi",
    "pratiche_economiche",
    "atto_fase_tariffaria_map",
    "procedimento_tariffario_map",
    "forense_regole_applicative",
    "forense_spese_standard",
    "forense_maggiorazioni_riduzioni",
    "forense_parametri_compenso",
    "forense_scaglioni_valore",
    "forense_fasi",
    "forense_tabelle",
    "forense_versioni",
    "template_atto_versioni",
    "fascicoli_strutturati",
    "atto_controllo",
    "atto_allegato",
    "procedimento_atto",
    "procedimento_portale_rito",
    "controlli_conformita",
    "allegati_obbligatori",
    "atti",
    "procedimenti",
    "portali_riti",
    "sottobranche",
    "macro_aree",
]


SCHEMA_STRUTTURALE_SQL = """
CREATE TABLE IF NOT EXISTS macro_aree (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL UNIQUE,
    descrizione TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS sottobranche (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    macro_area_id INTEGER NOT NULL,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    descrizione TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (macro_area_id) REFERENCES macro_aree(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sottobranche_macro_area_id
ON sottobranche(macro_area_id);

CREATE TABLE IF NOT EXISTS portali_riti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descrizione TEXT,
    piattaforma TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS procedimenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sottobranca_id INTEGER NOT NULL,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    descrizione TEXT,
    ambito TEXT,
    grado_default TEXT,
    ufficio_default TEXT,
    competenza_default TEXT,
    valore_causa_obbligatorio INTEGER NOT NULL DEFAULT 0,
    contributo_unificato_previsto INTEGER NOT NULL DEFAULT 0,
    firma_digitale_richiesta INTEGER NOT NULL DEFAULT 0,
    procura_richiesta INTEGER NOT NULL DEFAULT 0,
    notificazione_richiesta INTEGER NOT NULL DEFAULT 0,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    wizard_config_json TEXT,
    regole_json TEXT,
    campi_obbligatori_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (sottobranca_id) REFERENCES sottobranche(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_procedimenti_sottobranca_id
ON procedimenti(sottobranca_id);
CREATE INDEX IF NOT EXISTS idx_procedimenti_nome
ON procedimenti(nome);

CREATE TABLE IF NOT EXISTS atti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    tipologia TEXT NOT NULL,
    descrizione TEXT,
    titolo_default TEXT,
    richiede_firma_digitale INTEGER NOT NULL DEFAULT 0,
    richiede_procura INTEGER NOT NULL DEFAULT 0,
    richiede_contributo INTEGER NOT NULL DEFAULT 0,
    richiede_nota_iscrizione_ruolo INTEGER NOT NULL DEFAULT 0,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    template_json TEXT,
    wizard_step_json TEXT,
    validazioni_json TEXT,
    placeholder_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_atti_nome
ON atti(nome);
CREATE INDEX IF NOT EXISTS idx_atti_tipologia
ON atti(tipologia);

CREATE TABLE IF NOT EXISTS allegati_obbligatori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    descrizione TEXT,
    obbligatorio INTEGER NOT NULL DEFAULT 1,
    uno_solo INTEGER NOT NULL DEFAULT 1,
    formato_ammesso TEXT,
    dimensione_massima_mb INTEGER,
    firmato_richiesto INTEGER NOT NULL DEFAULT 0,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS controlli_conformita (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    descrizione TEXT,
    severita TEXT NOT NULL DEFAULT 'errore',
    espressione_check TEXT,
    messaggio_errore TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_controlli_categoria
ON controlli_conformita(categoria);

CREATE TABLE IF NOT EXISTS procedimento_portale_rito (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    procedimento_id INTEGER NOT NULL,
    portale_rito_id INTEGER NOT NULL,
    predefinito INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    UNIQUE (procedimento_id, portale_rito_id),
    FOREIGN KEY (procedimento_id) REFERENCES procedimenti(id) ON DELETE CASCADE,
    FOREIGN KEY (portale_rito_id) REFERENCES portali_riti(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ppr_procedimento_id
ON procedimento_portale_rito(procedimento_id);
CREATE INDEX IF NOT EXISTS idx_ppr_portale_rito_id
ON procedimento_portale_rito(portale_rito_id);

CREATE TABLE IF NOT EXISTS procedimento_atto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    procedimento_id INTEGER NOT NULL,
    atto_id INTEGER NOT NULL,
    fase TEXT,
    obbligatorio INTEGER NOT NULL DEFAULT 0,
    iniziale INTEGER NOT NULL DEFAULT 0,
    finale INTEGER NOT NULL DEFAULT 0,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    UNIQUE (procedimento_id, atto_id),
    FOREIGN KEY (procedimento_id) REFERENCES procedimenti(id) ON DELETE CASCADE,
    FOREIGN KEY (atto_id) REFERENCES atti(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pa_procedimento_id
ON procedimento_atto(procedimento_id);
CREATE INDEX IF NOT EXISTS idx_pa_atto_id
ON procedimento_atto(atto_id);

CREATE TABLE IF NOT EXISTS atto_allegato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atto_id INTEGER NOT NULL,
    allegato_id INTEGER NOT NULL,
    obbligatorio INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    UNIQUE (atto_id, allegato_id),
    FOREIGN KEY (atto_id) REFERENCES atti(id) ON DELETE CASCADE,
    FOREIGN KEY (allegato_id) REFERENCES allegati_obbligatori(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aa_atto_id
ON atto_allegato(atto_id);
CREATE INDEX IF NOT EXISTS idx_aa_allegato_id
ON atto_allegato(allegato_id);

CREATE TABLE IF NOT EXISTS atto_controllo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atto_id INTEGER NOT NULL,
    controllo_id INTEGER NOT NULL,
    obbligatorio INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    UNIQUE (atto_id, controllo_id),
    FOREIGN KEY (atto_id) REFERENCES atti(id) ON DELETE CASCADE,
    FOREIGN KEY (controllo_id) REFERENCES controlli_conformita(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ac_atto_id
ON atto_controllo(atto_id);
CREATE INDEX IF NOT EXISTS idx_ac_controllo_id
ON atto_controllo(controllo_id);

CREATE TABLE IF NOT EXISTS fascicoli_strutturati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fascicolo_id TEXT UNIQUE REFERENCES fascicoli(id) ON DELETE CASCADE,
    numero TEXT,
    anno TEXT,
    oggetto TEXT,
    cliente_id TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    controparte TEXT,
    macro_area_id INTEGER REFERENCES macro_aree(id) ON DELETE SET NULL,
    sottobranca_id INTEGER REFERENCES sottobranche(id) ON DELETE SET NULL,
    procedimento_id INTEGER REFERENCES procedimenti(id) ON DELETE SET NULL,
    portale_rito_id INTEGER REFERENCES portali_riti(id) ON DELETE SET NULL,
    stato TEXT,
    ufficio_giudiziario TEXT,
    grado TEXT,
    data_apertura TEXT,
    data_chiusura TEXT,
    metadati_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_fascicoli_strutturati_fascicolo_id
ON fascicoli_strutturati(fascicolo_id);

CREATE TABLE IF NOT EXISTS template_atto_versioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atto_id INTEGER NOT NULL,
    versione TEXT NOT NULL,
    contenuto TEXT NOT NULL DEFAULT '{}',
    attivo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (atto_id, versione),
    FOREIGN KEY (atto_id) REFERENCES atti(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_template_atto_versioni_atto_id
ON template_atto_versioni(atto_id);

CREATE TABLE IF NOT EXISTS forense_versioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    titolo TEXT NOT NULL,
    fonte_normativa TEXT NOT NULL,
    data_vigore_da TEXT NOT NULL,
    data_vigore_a TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_forense_versioni_attiva
ON forense_versioni(attiva);

CREATE TABLE IF NOT EXISTS forense_tabelle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versione_id INTEGER NOT NULL,
    codice TEXT NOT NULL,
    nome TEXT NOT NULL,
    ambito TEXT NOT NULL,
    autorita TEXT,
    rito TEXT,
    macro_area_codice TEXT,
    descrizione TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (versione_id, codice),
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forense_tabelle_versione_id
ON forense_tabelle(versione_id);
CREATE INDEX IF NOT EXISTS idx_forense_tabelle_ambito
ON forense_tabelle(ambito);

CREATE TABLE IF NOT EXISTS forense_fasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    descrizione TEXT,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    attiva INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_forense_fasi_attiva
ON forense_fasi(attiva);

CREATE TABLE IF NOT EXISTS forense_scaglioni_valore (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versione_id INTEGER NOT NULL,
    tabella_id INTEGER NOT NULL,
    codice TEXT NOT NULL,
    label TEXT NOT NULL,
    valore_min REAL NOT NULL DEFAULT 0,
    valore_max REAL,
    indeterminabile INTEGER NOT NULL DEFAULT 0,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (tabella_id, codice),
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE CASCADE,
    FOREIGN KEY (tabella_id) REFERENCES forense_tabelle(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forense_scaglioni_tabella_id
ON forense_scaglioni_valore(tabella_id);
CREATE INDEX IF NOT EXISTS idx_forense_scaglioni_versione_id
ON forense_scaglioni_valore(versione_id);

CREATE TABLE IF NOT EXISTS forense_parametri_compenso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versione_id INTEGER NOT NULL,
    tabella_id INTEGER NOT NULL,
    fase_id INTEGER NOT NULL,
    scaglione_id INTEGER NOT NULL,
    unita_misura TEXT NOT NULL DEFAULT 'importo',
    compenso_min REAL,
    compenso_medio REAL,
    compenso_max REAL,
    note TEXT,
    attivo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (tabella_id, fase_id, scaglione_id),
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE CASCADE,
    FOREIGN KEY (tabella_id) REFERENCES forense_tabelle(id) ON DELETE CASCADE,
    FOREIGN KEY (fase_id) REFERENCES forense_fasi(id) ON DELETE RESTRICT,
    FOREIGN KEY (scaglione_id) REFERENCES forense_scaglioni_valore(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forense_parametri_tabella_id
ON forense_parametri_compenso(tabella_id);
CREATE INDEX IF NOT EXISTS idx_forense_parametri_fase_id
ON forense_parametri_compenso(fase_id);
CREATE INDEX IF NOT EXISTS idx_forense_parametri_scaglione_id
ON forense_parametri_compenso(scaglione_id);

CREATE TABLE IF NOT EXISTS forense_maggiorazioni_riduzioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versione_id INTEGER NOT NULL,
    codice TEXT NOT NULL,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL,
    modalita TEXT NOT NULL,
    valore_num REAL,
    applica_su TEXT NOT NULL DEFAULT 'compenso_fase',
    fase_id INTEGER,
    cumulabile INTEGER NOT NULL DEFAULT 1,
    priorita INTEGER NOT NULL DEFAULT 0,
    condizione_json TEXT,
    note TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (versione_id, codice),
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE CASCADE,
    FOREIGN KEY (fase_id) REFERENCES forense_fasi(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_forense_mr_versione_id
ON forense_maggiorazioni_riduzioni(versione_id);
CREATE INDEX IF NOT EXISTS idx_forense_mr_fase_id
ON forense_maggiorazioni_riduzioni(fase_id);

CREATE TABLE IF NOT EXISTS forense_spese_standard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versione_id INTEGER,
    codice TEXT NOT NULL,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    metodo_calcolo TEXT NOT NULL DEFAULT 'fisso',
    importo_default REAL,
    aliquota_default REAL,
    imponibile_tipo TEXT,
    formula_json TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (codice, versione_id),
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_forense_spese_categoria
ON forense_spese_standard(categoria);

CREATE TABLE IF NOT EXISTS forense_regole_applicative (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    versione_id INTEGER NOT NULL,
    codice TEXT NOT NULL,
    nome TEXT NOT NULL,
    descrizione TEXT,
    priorita INTEGER NOT NULL DEFAULT 0,
    condizione_json TEXT NOT NULL,
    azione_json TEXT NOT NULL,
    attiva INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (versione_id, codice),
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forense_regole_versione_id
ON forense_regole_applicative(versione_id);
CREATE INDEX IF NOT EXISTS idx_forense_regole_priorita
ON forense_regole_applicative(priorita);

CREATE TABLE IF NOT EXISTS procedimento_tariffario_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    procedimento_id INTEGER NOT NULL,
    versione_id INTEGER NOT NULL,
    tabella_id INTEGER NOT NULL,
    criterio_valore TEXT,
    valore_tipo_default TEXT,
    fase_default_json TEXT,
    accessori_default_json TEXT,
    regole_override_json TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (procedimento_id, versione_id, tabella_id),
    FOREIGN KEY (procedimento_id) REFERENCES procedimenti(id) ON DELETE CASCADE,
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE CASCADE,
    FOREIGN KEY (tabella_id) REFERENCES forense_tabelle(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_proc_tariffario_procedimento_id
ON procedimento_tariffario_map(procedimento_id);
CREATE INDEX IF NOT EXISTS idx_proc_tariffario_tabella_id
ON procedimento_tariffario_map(tabella_id);

CREATE TABLE IF NOT EXISTS atto_fase_tariffaria_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atto_id INTEGER NOT NULL,
    fase_id INTEGER NOT NULL,
    peso_percentuale REAL,
    obbligatoria INTEGER NOT NULL DEFAULT 0,
    attiva INTEGER NOT NULL DEFAULT 1,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (atto_id, fase_id),
    FOREIGN KEY (atto_id) REFERENCES atti(id) ON DELETE CASCADE,
    FOREIGN KEY (fase_id) REFERENCES forense_fasi(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_atto_fase_tariffaria_atto_id
ON atto_fase_tariffaria_map(atto_id);
CREATE INDEX IF NOT EXISTS idx_atto_fase_tariffaria_fase_id
ON atto_fase_tariffaria_map(fase_id);

CREATE TABLE IF NOT EXISTS pratiche_economiche (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fascicolo_id TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    procedimento_id INTEGER NOT NULL,
    versione_id INTEGER NOT NULL,
    tabella_id INTEGER,
    scaglione_id INTEGER,
    titolo TEXT,
    valore_tipo TEXT NOT NULL DEFAULT 'determinato',
    valore_pratica REAL,
    valore_stimato REAL,
    complessita INTEGER NOT NULL DEFAULT 2,
    urgenza INTEGER NOT NULL DEFAULT 0,
    numero_parti INTEGER NOT NULL DEFAULT 1,
    numero_questioni INTEGER NOT NULL DEFAULT 1,
    cliente_tipo TEXT,
    equo_compenso_applicabile INTEGER NOT NULL DEFAULT 0,
    note_interne TEXT,
    wizard_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (procedimento_id) REFERENCES procedimenti(id) ON DELETE RESTRICT,
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE RESTRICT,
    FOREIGN KEY (tabella_id) REFERENCES forense_tabelle(id) ON DELETE SET NULL,
    FOREIGN KEY (scaglione_id) REFERENCES forense_scaglioni_valore(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_pratiche_economiche_procedimento_id
ON pratiche_economiche(procedimento_id);
CREATE INDEX IF NOT EXISTS idx_pratiche_economiche_versione_id
ON pratiche_economiche(versione_id);
CREATE INDEX IF NOT EXISTS idx_pratiche_economiche_fascicolo_id
ON pratiche_economiche(fascicolo_id);

CREATE TABLE IF NOT EXISTS preventivi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pratica_economica_id INTEGER NOT NULL,
    numero_preventivo TEXT NOT NULL UNIQUE,
    stato TEXT NOT NULL DEFAULT 'bozza',
    data_emissione TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valido_fino TEXT,
    versione_id INTEGER NOT NULL,
    tabella_id INTEGER,
    scaglione_id INTEGER,
    totale_compensi_netto REAL NOT NULL DEFAULT 0,
    totale_spese_vive REAL NOT NULL DEFAULT 0,
    totale_spese_generali REAL NOT NULL DEFAULT 0,
    totale_cpa REAL NOT NULL DEFAULT 0,
    totale_iva REAL NOT NULL DEFAULT 0,
    totale_sconti REAL NOT NULL DEFAULT 0,
    totale_finale REAL NOT NULL DEFAULT 0,
    note_cliente TEXT,
    note_interne TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (pratica_economica_id) REFERENCES pratiche_economiche(id) ON DELETE CASCADE,
    FOREIGN KEY (versione_id) REFERENCES forense_versioni(id) ON DELETE RESTRICT,
    FOREIGN KEY (tabella_id) REFERENCES forense_tabelle(id) ON DELETE SET NULL,
    FOREIGN KEY (scaglione_id) REFERENCES forense_scaglioni_valore(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_preventivi_pratica_economica_id
ON preventivi(pratica_economica_id);
CREATE INDEX IF NOT EXISTS idx_preventivi_stato
ON preventivi(stato);

CREATE TABLE IF NOT EXISTS preventivo_voci (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preventivo_id INTEGER NOT NULL,
    fase_id INTEGER,
    origine TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    quantita REAL NOT NULL DEFAULT 1,
    coefficiente REAL NOT NULL DEFAULT 1,
    importo_base REAL,
    importo_unitario REAL,
    importo_totale REAL NOT NULL DEFAULT 0,
    parametro_min REAL,
    parametro_medio REAL,
    parametro_max REAL,
    maggiorazioni_json TEXT,
    riduzioni_json TEXT,
    visibile_al_cliente INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (preventivo_id) REFERENCES preventivi(id) ON DELETE CASCADE,
    FOREIGN KEY (fase_id) REFERENCES forense_fasi(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_preventivo_voci_preventivo_id
ON preventivo_voci(preventivo_id);
CREATE INDEX IF NOT EXISTS idx_preventivo_voci_fase_id
ON preventivo_voci(fase_id);

CREATE TABLE IF NOT EXISTS preventivo_accessori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preventivo_id INTEGER NOT NULL,
    spesa_standard_id INTEGER,
    categoria TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    metodo_calcolo TEXT NOT NULL DEFAULT 'fisso',
    base_calcolo REAL,
    aliquota REAL,
    quantita REAL NOT NULL DEFAULT 1,
    importo REAL NOT NULL DEFAULT 0,
    visibile_al_cliente INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (preventivo_id) REFERENCES preventivi(id) ON DELETE CASCADE,
    FOREIGN KEY (spesa_standard_id) REFERENCES forense_spese_standard(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_preventivo_accessori_preventivo_id
ON preventivo_accessori(preventivo_id);

CREATE TABLE IF NOT EXISTS accordi_compenso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preventivo_id INTEGER NOT NULL,
    tipo_accordo TEXT NOT NULL,
    compenso_concordato REAL,
    rateizzazione_json TEXT,
    esclusioni_json TEXT,
    clausole_json TEXT,
    testo_libero TEXT,
    data_accordo TEXT,
    attivo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (preventivo_id) REFERENCES preventivi(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_accordi_compenso_preventivo_id
ON accordi_compenso(preventivo_id);

CREATE TABLE IF NOT EXISTS preventivo_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preventivo_id INTEGER NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'full',
    snapshot_json TEXT NOT NULL,
    hash_sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (preventivo_id) REFERENCES preventivi(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_preventivo_snapshot_preventivo_id
ON preventivo_snapshot(preventivo_id);

CREATE TABLE IF NOT EXISTS preventivo_accettazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preventivo_id INTEGER NOT NULL,
    stato TEXT NOT NULL,
    data_evento TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modalita TEXT,
    documento_uri TEXT,
    firma_cliente_json TEXT,
    note TEXT,
    FOREIGN KEY (preventivo_id) REFERENCES preventivi(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_preventivo_accettazioni_preventivo_id
ON preventivo_accettazioni(preventivo_id);

CREATE TABLE IF NOT EXISTS controlli_forensi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    severita TEXT NOT NULL DEFAULT 'errore',
    descrizione TEXT,
    espressione_check TEXT,
    messaggio_errore TEXT,
    attiva INTEGER NOT NULL DEFAULT 1,
    ordinamento INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS preventivo_controllo_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preventivo_id INTEGER NOT NULL,
    controllo_id INTEGER NOT NULL,
    esito TEXT NOT NULL DEFAULT 'pending',
    dettaglio TEXT,
    creato_il TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (preventivo_id, controllo_id),
    FOREIGN KEY (preventivo_id) REFERENCES preventivi(id) ON DELETE CASCADE,
    FOREIGN KEY (controllo_id) REFERENCES controlli_forensi(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_preventivo_controllo_map_preventivo_id
ON preventivo_controllo_map(preventivo_id);
"""


MACRO_AREAS = [
    ("civile", "Civile", "Macro area generale del contenzioso e della consulenza civile."),
    ("penale", "Penale", "Procedimenti penali, indagini e difesa."),
    ("amministrativo", "Amministrativo", "Ricorsi e attività nel processo amministrativo."),
    ("costituzionale", "Costituzionale", "Questioni e giudizi costituzionali."),
    ("commerciale", "Commerciale", "Contrattualistica, impresa e operazioni commerciali."),
    ("lavoro", "Lavoro", "Lavoro, previdenza e assistenza."),
    ("tributario", "Tributario", "Contenzioso e adempimenti tributari."),
    ("processuale_civile", "Processuale civile", "Regole e flussi processuali civili."),
    ("processuale_penale", "Processuale penale", "Regole e flussi processuali penali."),
    ("unione_europea", "Unione europea", "Contenzioso e fonti dell'Unione europea."),
    ("internazionale", "Internazionale", "Profili internazionali, notifiche e competenza estera."),
    ("famiglia", "Famiglia", "Persone, minori, responsabilità genitoriale e volontaria."),
    ("societario", "Societario", "Società, Registro Imprese e pratiche camerali."),
    ("crisi_impresa", "Crisi d'impresa", "Concorsuale, composizione negoziata e crisi."),
    # ── Macro-aree aggiunte — allineamento con 02_macro_aree.sql ──
    ("penale_difensivo", "Diritto Penale difensivo", "Difesa dell'imputato, indagini difensive, udienza preliminare, dibattimento, impugnazioni, esecuzione penale e misure di prevenzione."),
    ("societario_commerciale", "Diritto Societario & Commerciale", "Società di capitali e persone, M&A, governance, impugnazione delibere, contratti commerciali, startup e joint venture."),
    ("immigrazione_cittadinanza", "Immigrazione & Cittadinanza", "Permessi di soggiorno, cittadinanza, protezione internazionale, ricongiungimento familiare ed espulsioni."),
    # ── Macro-aree procedurali — allineamento con NODE_CATALOG (tassonomia_preventivi.py) ──
    ("esecuzione_civile", "Esecuzione civile", "Precetti, pignoramenti mobiliari, immobiliari e presso terzi; opposizioni esecutive."),
    ("previdenza_assistenza", "Previdenza & Assistenza", "Ricorsi INPS, INAIL, assistenza sociale e previdenza complementare."),
    ("mediazione", "Mediazione civile e commerciale", "Mediazione obbligatoria e facoltativa ex D.Lgs. 28/2010; ADR civile e commerciale."),
    ("negoziazione_assistita", "Negoziazione assistita", "Convenzioni ex D.L. 132/2014; accordi negoziati in materia civile, famiglia e lavoro."),
    ("arbitrato", "Arbitrato", "Arbitrato rituale e irrituale; clausole compromissorie; lodi arbitrali."),
    ("volontaria_giurisdizione", "Volontaria giurisdizione", "Amministrazione di sostegno, tutela, curatela, autorizzazioni del giudice tutelare."),
    ("corte_dei_conti", "Giustizia contabile", "Giudizi di responsabilità erariale e pensionistici innanzi alla Corte dei Conti."),
    ("giurisdizioni_superiori", "Giurisdizioni superiori", "Corte Costituzionale, CEDU, CGUE e rinvii pregiudiziali europei."),
    ("consulenza_contrattualistica", "Consulenza e contrattualistica", "Pareri legali, redazione e revisione contratti, trattative, transazioni stragiudiziali."),
    ("servizi_professionali", "Servizi professionali", "Domiciliazioni, attività a tempo, procedure particolari e servizi vari."),
    ("immobiliare_tavolare", "Diritto immobiliare & Tavolare", "Compravendite, locazioni, iscrizioni ipotecarie, pubblicità tavolare e urbanistica."),
]


PORTALI_RITI_BASE = [
    ("PCT", "PCT", "canale", "Canale del processo civile telematico.", "PCT"),
    ("PST", "PST", "portale", "Portale dei Servizi Telematici del Ministero della Giustizia.", "PST"),
    ("PAT", "PAT", "portale", "Processo Amministrativo Telematico.", "PAT"),
    ("PTT", "PTT", "portale", "Processo Tributario Telematico.", "PTT"),
    ("SIGIT", "SIGIT", "registro", "Sistema informativo della giustizia tributaria.", "PTT"),
    ("REGISTRO_IMPRESE", "Registro Imprese", "portale", "Portale camerale e adempimenti societari.", "REGISTRO_IMPRESE"),
    ("TELEMACO", "Telemaco", "portale", "Servizi camerali Telemaco.", "TELEMACO"),
    ("DIRE", "DIRE", "portale", "Flussi camerali DIRE.", "DIRE"),
    ("STRAGIUDIZIALE", "Stragiudiziale", "rito", "Attività fuori giudizio e precontenziosa.", "OFFLINE"),
    ("CARTACEO", "Cartaceo", "canale", "Gestione cartacea o ibrida.", "OFFLINE"),
    ("PEC", "PEC", "canale", "Invio, notifica o scambio documentale via PEC.", "PEC"),
]


FORENSE_FASI = [
    ("FASE_STUDIO", "Studio", "Esame della posizione, dei documenti e della strategia.", 10),
    ("FASE_INTRODUTTIVA", "Introduttiva", "Redazione e deposito dell'atto introduttivo.", 20),
    ("FASE_ISTRUTTORIA", "Istruttoria", "Attività istruttoria, memorie, udienze e prove.", 30),
    ("FASE_DECISIONALE", "Decisionale", "Conclusionali, repliche, precisazione conclusioni e decisione.", 40),
    ("FASE_ESECUTIVA", "Esecutiva", "Precetto, pignoramento ed esecuzione.", 50),
    ("FASE_CAUTELARE", "Cautelare", "Ricorsi e attività cautelari.", 60),
    ("FASE_MONITORIA", "Monitoria", "Decreto ingiuntivo e attività collegate.", 70),
    ("FASE_IMPUGNAZIONE", "Impugnazione", "Appello, reclamo, cassazione e mezzi di impugnazione.", 80),
    ("FASE_STRAGIUDIZIALE", "Stragiudiziale", "Pareri, diffide, trattative e attività fuori giudizio.", 90),
]


CONTROLLI_FORENSI_BASE = [
    ("CHK_VALORE_PRATICA", "Valore pratica presente", "valore", "errore", "Controlla la presenza del valore pratica o della stima.", "valore_pratica != null OR valore_stimato != null", "Valore pratica mancante.", 10),
    ("CHK_SCAGLIONE", "Scaglione coerente", "scaglione", "bloccante", "Controlla la coerenza tra valore e scaglione scelto.", "scaglione_coerente == true", "Scaglione incoerente con il valore della pratica.", 20),
    ("CHK_TABELLA_FORENSE", "Tabella forense associata", "coerenza", "bloccante", "Controlla che la pratica abbia una tabella forense valida.", "tabella_forense_presente == true", "Tabella forense non associata alla pratica.", 30),
    ("CHK_EQUO_COMPENSO", "Verifica equo compenso", "equo_compenso", "warning", "Controlla i casi in cui attivare il presidio equo compenso.", "equo_compenso_ok == true", "Verificare la coerenza del preventivo con l'equo compenso.", 40),
    ("CHK_ACCESSORI", "Accessori coerenti", "accessori", "warning", "Controlla spese generali, CPA, IVA e spese vive.", "accessori_coerenti == true", "Accessori economici da verificare.", 50),
    ("CHK_SNAPSHOT", "Snapshot presente", "snapshot", "bloccante", "Controlla che il preventivo sia stato congelato prima dell'accettazione.", "snapshot_presente == true", "Snapshot del preventivo mancante.", 60),
    ("CHK_ACCORDO_COMPENSO", "Accordo compenso presente", "accordo", "warning", "Controlla la presenza della pattuizione o delle condizioni economiche.", "accordo_presente == true", "Accordo sul compenso assente o incompleto.", 70),
    ("CHK_PREVENTIVO_FIRMABILE", "Preventivo firmabile", "coerenza", "bloccante", "Controlla che il preventivo sia pronto per invio e accettazione.", "preventivo_firmabile == true", "Il preventivo non è ancora firmabile.", 80),
]


def ensure_catalogo_strutturale_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_STRUTTURALE_SQL)


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0] if row else 0)


def _seed_macro_aree(conn: sqlite3.Connection) -> dict[str, int]:
    now = datetime.now().isoformat()
    for ordine, (codice, nome, descrizione) in enumerate(MACRO_AREAS, start=1):
        conn.execute(
            """
            INSERT OR IGNORE INTO macro_aree(codice, nome, descrizione, ordinamento, updated_at)
            VALUES(?,?,?,?,?)
            """,
            (codice, nome, descrizione, ordine, now),
        )
    return {
        str(codice): int(pk)
        for pk, codice in conn.execute("SELECT id, codice FROM macro_aree").fetchall()
    }


def _seed_sottobranche(conn: sqlite3.Connection, macro_ids: dict[str, int]) -> dict[str, int]:
    now = datetime.now().isoformat()
    nomi = {codice: nome for codice, nome, _ in MACRO_AREAS}
    for ordine, (codice_macro, macro_id) in enumerate(sorted(macro_ids.items()), start=1):
        conn.execute(
            """
            INSERT OR IGNORE INTO sottobranche(macro_area_id, codice, nome, descrizione, ordinamento, updated_at)
            VALUES(?,?,?,?,?,?)
            """,
            (
                macro_id,
                f"{codice_macro}_generale",
                f"{nomi.get(codice_macro, codice_macro)} generale",
                "Sottobranca iniziale neutra da specializzare nella fase di mappatura guidata.",
                ordine,
                now,
            ),
        )
    return {
        str(codice): int(pk)
        for pk, codice in conn.execute("SELECT id, codice FROM sottobranche").fetchall()
    }


def _seed_portali_riti(conn: sqlite3.Connection) -> dict[str, int]:
    now = datetime.now().isoformat()
    for ordine, (codice, nome, tipo, descrizione, piattaforma) in enumerate(PORTALI_RITI_BASE, start=1):
        conn.execute(
            """
            INSERT OR IGNORE INTO portali_riti(codice, nome, tipo, descrizione, piattaforma, ordinamento, updated_at)
            VALUES(?,?,?,?,?,?,?)
            """,
            (codice, nome, tipo, descrizione, piattaforma, ordine, now),
        )
    return {
        str(codice): int(pk)
        for pk, codice in conn.execute("SELECT id, codice FROM portali_riti").fetchall()
    }


def _seed_forense_versioni(conn: sqlite3.Connection) -> dict[str, int]:
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO forense_versioni(
            codice, titolo, fonte_normativa, data_vigore_da, attiva, note, updated_at
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            "DM55_2014_DM147_2022",
            "Parametri forensi D.M. 55/2014 aggiornati dal D.M. 147/2022",
            "D.M. 55/2014 come modificato dal D.M. 147/2022, con presidio equo compenso ex L. 49/2023",
            "2022-10-23",
            1,
            "Versione iniziale del motore tariffario forense versionato.",
            now,
        ),
    )
    return {
        str(codice): int(pk)
        for pk, codice in conn.execute("SELECT id, codice FROM forense_versioni").fetchall()
    }


def _seed_forense_fasi(conn: sqlite3.Connection) -> dict[str, int]:
    now = datetime.now().isoformat()
    for codice, nome, descrizione, ordinamento in FORENSE_FASI:
        conn.execute(
            """
            INSERT OR IGNORE INTO forense_fasi(codice, nome, descrizione, ordinamento, attiva, updated_at)
            VALUES(?,?,?,?,?,?)
            """,
            (codice, nome, descrizione, ordinamento, 1, now),
        )
    return {
        str(codice): int(pk)
        for pk, codice in conn.execute("SELECT id, codice FROM forense_fasi").fetchall()
    }


def _seed_forense_spese_standard(conn: sqlite3.Connection, versioni: dict[str, int]) -> dict[str, int]:
    now = datetime.now().isoformat()
    versione_id = versioni.get("DM55_2014_DM147_2022")
    if versione_id is None:
        return {}

    rows = [
        (versione_id, "SPESE_GENERALI_15", "Spese generali", "spese_generali", "percentuale", None, 15.0, "compensi", None, 10, "Spese generali ex art. 2 D.M. 55/2014."),
        (versione_id, "CPA_4", "CPA", "CPA", "percentuale", None, 4.0, "compensi_piu_spese", None, 20, "Contributo previdenziale forense standard."),
        (versione_id, "IVA_22", "IVA", "IVA", "percentuale", None, 22.0, "totale_imponibile", None, 30, "IVA ordinaria applicata al preventivo."),
        (versione_id, "CU_DEFAULT", "Contributo unificato", "CU", "manuale", None, None, "spese_vive", None, 40, "Voce standard da valorizzare secondo rito e scaglione."),
    ]
    for row in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO forense_spese_standard(
                versione_id, codice, nome, categoria, metodo_calcolo,
                importo_default, aliquota_default, imponibile_tipo, formula_json,
                ordinamento, note, attiva, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (*row, 1, now),
        )
    return {
        str(codice): int(pk)
        for pk, codice in conn.execute("SELECT id, codice FROM forense_spese_standard").fetchall()
    }


def _seed_controlli_forensi(conn: sqlite3.Connection) -> dict[str, int]:
    now = datetime.now().isoformat()
    for codice, nome, categoria, severita, descrizione, check, messaggio, ordine in CONTROLLI_FORENSI_BASE:
        conn.execute(
            """
            INSERT OR IGNORE INTO controlli_forensi(
                codice, nome, categoria, severita, descrizione,
                espressione_check, messaggio_errore, ordinamento, attiva, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (codice, nome, categoria, severita, descrizione, check, messaggio, ordine, 1, now),
        )
    return {
        str(codice): int(pk)
        for pk, codice in conn.execute("SELECT id, codice FROM controlli_forensi").fetchall()
    }


def seed_catalogo_strutturale(conn: sqlite3.Connection) -> dict[str, int]:
    ensure_catalogo_strutturale_schema(conn)

    macro_ids = _seed_macro_aree(conn)
    _seed_sottobranche(conn, macro_ids)
    _seed_portali_riti(conn)
    versioni = _seed_forense_versioni(conn)
    _seed_forense_fasi(conn)
    _seed_forense_spese_standard(conn, versioni)
    _seed_controlli_forensi(conn)

    tables = [
        "macro_aree",
        "sottobranche",
        "portali_riti",
        "procedimenti",
        "atti",
        "allegati_obbligatori",
        "controlli_conformita",
        "procedimento_portale_rito",
        "procedimento_atto",
        "atto_allegato",
        "atto_controllo",
        "fascicoli_strutturati",
        "template_atto_versioni",
        "forense_versioni",
        "forense_tabelle",
        "forense_fasi",
        "forense_scaglioni_valore",
        "forense_parametri_compenso",
        "forense_maggiorazioni_riduzioni",
        "forense_spese_standard",
        "forense_regole_applicative",
        "procedimento_tariffario_map",
        "atto_fase_tariffaria_map",
        "pratiche_economiche",
        "preventivi",
        "preventivo_voci",
        "preventivo_accessori",
        "accordi_compenso",
        "preventivo_snapshot",
        "preventivo_accettazioni",
        "controlli_forensi",
        "preventivo_controllo_map",
    ]
    return {table: _table_count(conn, table) for table in tables}
