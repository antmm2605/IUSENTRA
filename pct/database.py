"""
Gestione database centralizzata per IUSENTRA.

Funzionalità:
  - Statistiche e analisi di tutti i moduli dati (JSON + SQLite)
  - Verifica integrità referenziale completa (cross-module)
  - Ottimizzazione: compattazione JSON, VACUUM/ANALYZE SQLite
  - Migrazione unificata verso SQLite con schema relazionale
  - Export ZIP completo con tutti i dati
  - Analisi pattern di utilizzo dal log di audit
  - Ricerca e riparazione automatica problemi comuni
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import time
import uuid
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pct.catalogo_strutturale import (
    ensure_catalogo_strutturale_schema,
    seed_catalogo_strutturale,
)
from pct.pdp_penale_workflow import SCHEMA_SQL_PDP_PENALE
from pct.path_security import resolve_sqlite_path
from pct.telematico_workflow import SCHEMA_SQL_TELEMATICO


# ================================================================ Dataclasses

@dataclass
class StatisticheModulo:
    nome: str
    percorso: str
    esiste: bool
    migrabile_sqlite: bool = False
    dimensione_bytes: int = 0
    record_totali: int = 0
    ultima_modifica: str = ""
    stato: str = "OK"       # OK | ERRORE | VUOTO | NON_TROVATO
    errore: str = ""

    @property
    def dimensione_leggibile(self) -> str:
        n = self.dimensione_bytes
        if n < 1024:
            return f"{n} B"
        elif n < 1024 ** 2:
            return f"{n / 1024:.1f} KB"
        elif n < 1024 ** 3:
            return f"{n / 1024 ** 2:.1f} MB"
        return f"{n / 1024 ** 3:.1f} GB"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dimensione_leggibile"] = self.dimensione_leggibile
        return d


@dataclass
class ProblemaIntegrita:
    modulo: str
    tipo: str           # RIFERIMENTO_MANCANTE | DUPLICATO | DATO_INVALIDO | DATO_MANCANTE
    severita: str       # CRITICO | AVVISO | INFO
    messaggio: str
    id_record: str = ""
    campo: str = ""
    suggerimento: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RisultatoOttimizzazione:
    modulo: str
    operazione: str
    riuscita: bool
    dettagli: str = ""
    ms: int = 0
    bytes_prima: int = 0
    bytes_dopo: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RiparazioneIntegrita:
    modulo: str
    tipo: str
    id_record: str
    campo: str
    azione: str
    dettagli: str = ""
    riuscita: bool = True
    valore_precedente: str = ""
    valore_nuovo: str = ""
    backup_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RisultatoMigrazione:
    riuscita: bool
    percorso_db: str
    record_migrati: Dict[str, int] = field(default_factory=dict)
    errori: List[str] = field(default_factory=list)
    avvisi: List[str] = field(default_factory=list)
    audit: Dict[str, Any] = field(default_factory=dict)
    ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ================================================================ Schema SQLite unificato

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- ---- Meta
CREATE TABLE IF NOT EXISTS _meta (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);

-- ---- Clienti
CREATE TABLE IF NOT EXISTS clienti (
    id              TEXT PRIMARY KEY,
    tipo            TEXT NOT NULL DEFAULT 'PERSONA_FISICA',
    stato           TEXT NOT NULL DEFAULT 'ATTIVO',
    cognome         TEXT,
    nome            TEXT,
    ragione_sociale TEXT,
    codice_fiscale  TEXT,
    partita_iva     TEXT,
    email           TEXT,
    telefono        TEXT,
    note            TEXT,
    creato_il       TEXT,
    modificato_il   TEXT,
    dati_json       TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_clienti_tipo     ON clienti(tipo);
CREATE INDEX IF NOT EXISTS idx_clienti_stato    ON clienti(stato);
CREATE INDEX IF NOT EXISTS idx_clienti_cf       ON clienti(codice_fiscale);
CREATE INDEX IF NOT EXISTS idx_clienti_email    ON clienti(email);
CREATE INDEX IF NOT EXISTS idx_clienti_cognome  ON clienti(cognome);

-- ---- Fascicoli
CREATE TABLE IF NOT EXISTS fascicoli (
    id                 TEXT PRIMARY KEY,
    numero             TEXT UNIQUE,
    titolo             TEXT,
    tipo               TEXT NOT NULL DEFAULT 'CIVILE',
    stato              TEXT NOT NULL DEFAULT 'APERTO',
    id_cliente         TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    nome_cliente       TEXT,
    tribunale          TEXT,
    sezione            TEXT,
    giudice            TEXT,
    numero_rg          TEXT,
    anno_rg            TEXT,
    controparte        TEXT,
    avvocato_referente TEXT,
    avvocato_dominus   TEXT,
    data_apertura      TEXT,
    data_chiusura      TEXT,
    oggetto            TEXT,
    note               TEXT,
    creato_il          TEXT,
    modificato_il      TEXT,
    attivita_json      TEXT DEFAULT '[]',
    documenti_json     TEXT DEFAULT '[]',
    scadenze_json      TEXT DEFAULT '[]',
    profilo_deposito_json TEXT DEFAULT '{}',
    dati_json          TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_fascicoli_tipo     ON fascicoli(tipo);
CREATE INDEX IF NOT EXISTS idx_fascicoli_stato    ON fascicoli(stato);
CREATE INDEX IF NOT EXISTS idx_fascicoli_cliente  ON fascicoli(id_cliente);
CREATE INDEX IF NOT EXISTS idx_fascicoli_numero   ON fascicoli(numero);
CREATE INDEX IF NOT EXISTS idx_fascicoli_avv      ON fascicoli(avvocato_referente);

-- ---- Soggetti e parti processuali
CREATE TABLE IF NOT EXISTS soggetti (
    id              TEXT PRIMARY KEY,
    tipo            TEXT NOT NULL DEFAULT 'PERSONA_FISICA',
    nome            TEXT,
    cognome         TEXT,
    ragione_sociale TEXT,
    codice_fiscale  TEXT,
    partita_iva     TEXT,
    qualifica       TEXT,
    id_cliente      TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    email           TEXT,
    telefono        TEXT,
    creato_il       TEXT,
    modificato_il   TEXT,
    dati_json       TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_soggetti_tipo     ON soggetti(tipo);
CREATE INDEX IF NOT EXISTS idx_soggetti_cliente  ON soggetti(id_cliente);
CREATE INDEX IF NOT EXISTS idx_soggetti_cf       ON soggetti(codice_fiscale);
CREATE INDEX IF NOT EXISTS idx_soggetti_nome     ON soggetti(cognome, nome, ragione_sociale);

CREATE TABLE IF NOT EXISTS soggetti_parti (
    id             TEXT PRIMARY KEY,
    id_fascicolo   TEXT REFERENCES fascicoli(id) ON DELETE CASCADE,
    id_soggetto    TEXT REFERENCES soggetti(id) ON DELETE CASCADE,
    ruolo          TEXT NOT NULL DEFAULT 'ALTRO',
    note           TEXT,
    data_aggiunta  TEXT,
    dati_json      TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_soggetti_parti_fascicolo ON soggetti_parti(id_fascicolo);
CREATE INDEX IF NOT EXISTS idx_soggetti_parti_soggetto  ON soggetti_parti(id_soggetto);
CREATE INDEX IF NOT EXISTS idx_soggetti_parti_ruolo     ON soggetti_parti(ruolo);

-- ---- Appuntamenti
CREATE TABLE IF NOT EXISTS appuntamenti (
    id              TEXT PRIMARY KEY,
    tipo            TEXT NOT NULL DEFAULT 'CONSULTAZIONE',
    stato           TEXT NOT NULL DEFAULT 'PROGRAMMATO',
    titolo          TEXT NOT NULL,
    data_ora        TEXT NOT NULL,
    durata_minuti   INTEGER DEFAULT 60,
    luogo           TEXT,
    descrizione     TEXT,
    cliente         TEXT,
    cf_cliente      TEXT,
    procedimento    TEXT,
    tribunale       TEXT,
    note            TEXT,
    creato_il       TEXT,
    modificato_il   TEXT,
    dati_json       TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_app_tipo     ON appuntamenti(tipo);
CREATE INDEX IF NOT EXISTS idx_app_stato    ON appuntamenti(stato);
CREATE INDEX IF NOT EXISTS idx_app_data     ON appuntamenti(data_ora);
CREATE INDEX IF NOT EXISTS idx_app_cliente  ON appuntamenti(cf_cliente);

-- ---- Scadenze
CREATE TABLE IF NOT EXISTS scadenze (
    id               TEXT PRIMARY KEY,
    tipo             TEXT NOT NULL,
    stato            TEXT NOT NULL DEFAULT 'APERTO',
    titolo           TEXT NOT NULL,
    data_scadenza    TEXT NOT NULL,
    priorita         TEXT DEFAULT 'MEDIA',
    perentorio       INTEGER DEFAULT 0,
    note             TEXT,
    id_fascicolo     TEXT REFERENCES fascicoli(id) ON DELETE CASCADE,
    id_appuntamento  TEXT REFERENCES appuntamenti(id) ON DELETE SET NULL,
    id_utente        TEXT,
    giorni_preavviso TEXT DEFAULT '[]',
    avvisi_inviati   TEXT DEFAULT '[]',
    completata_il    TEXT,
    creato_il        TEXT,
    dati_json        TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_scad_stato      ON scadenze(stato);
CREATE INDEX IF NOT EXISTS idx_scad_data       ON scadenze(data_scadenza);
CREATE INDEX IF NOT EXISTS idx_scad_priorita   ON scadenze(priorita);
CREATE INDEX IF NOT EXISTS idx_scad_fascicolo  ON scadenze(id_fascicolo);

-- ---- Timesheet
CREATE TABLE IF NOT EXISTS timesheet_entries (
    id              TEXT PRIMARY KEY,
    id_fascicolo    TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    id_cliente      TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    id_utente       TEXT,
    username        TEXT,
    data_attivita   TEXT NOT NULL,
    descrizione     TEXT NOT NULL,
    minuti          INTEGER NOT NULL DEFAULT 0,
    valore_unitario REAL NOT NULL DEFAULT 0,
    fatturabile     INTEGER DEFAULT 1,
    stato           TEXT NOT NULL DEFAULT 'APERTO',
    origine         TEXT DEFAULT '',
    creato_il       TEXT,
    modificato_il   TEXT,
    dati_json       TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_timesheet_fascicolo ON timesheet_entries(id_fascicolo);
CREATE INDEX IF NOT EXISTS idx_timesheet_cliente   ON timesheet_entries(id_cliente);
CREATE INDEX IF NOT EXISTS idx_timesheet_utente    ON timesheet_entries(id_utente);
CREATE INDEX IF NOT EXISTS idx_timesheet_data      ON timesheet_entries(data_attivita);

CREATE TABLE IF NOT EXISTS time_tracking_timers (
    id                 TEXT PRIMARY KEY,
    user_id            TEXT,
    username           TEXT,
    id_fascicolo       TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    id_cliente         TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    activity_type      TEXT NOT NULL DEFAULT 'other',
    description        TEXT,
    started_at         TEXT NOT NULL,
    paused_at          TEXT,
    ended_at           TEXT,
    elapsed_seconds    INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'running',
    timesheet_entry_id TEXT REFERENCES timesheet_entries(id) ON DELETE SET NULL,
    created_at         TEXT,
    updated_at         TEXT,
    dati_json          TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_time_tracking_user_status ON time_tracking_timers(user_id, status);
CREATE INDEX IF NOT EXISTS idx_time_tracking_fascicolo   ON time_tracking_timers(id_fascicolo);
CREATE INDEX IF NOT EXISTS idx_time_tracking_cliente     ON time_tracking_timers(id_cliente);
CREATE INDEX IF NOT EXISTS idx_time_tracking_started     ON time_tracking_timers(started_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_time_tracking_one_active_user
    ON time_tracking_timers(user_id)
    WHERE status IN ('running', 'paused');

-- ---- Preventivi e conferimenti
CREATE TABLE IF NOT EXISTS preventivi_records (
    preventivo_id                 TEXT PRIMARY KEY,
    numero                        TEXT NOT NULL,
    id_cliente                    TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    id_fascicolo                  TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    data_emissione                TEXT NOT NULL,
    data_scadenza                 TEXT,
    oggetto                       TEXT NOT NULL DEFAULT '',
    stato                         TEXT NOT NULL DEFAULT 'BOZZA',
    workflow_channel              TEXT NOT NULL DEFAULT 'STUDIO',
    tipo_compenso                 TEXT NOT NULL DEFAULT '',
    tipo_procedimento             TEXT NOT NULL DEFAULT '',
    area_pratica                  TEXT NOT NULL DEFAULT '',
    id_pratica                    TEXT NOT NULL DEFAULT '',
    procedura_operativa_codice    TEXT NOT NULL DEFAULT '',
    procedura_operativa_nome      TEXT NOT NULL DEFAULT '',
    canale_operativo              TEXT NOT NULL DEFAULT '',
    registro_operativo            TEXT NOT NULL DEFAULT '',
    classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]',
    criterio_arrotondamento_orario TEXT NOT NULL DEFAULT '',
    minuti_stimati                INTEGER NOT NULL DEFAULT 0,
    ore_fatturabili_calcolate     REAL NOT NULL DEFAULT 0,
    compenso_orario_base          REAL NOT NULL DEFAULT 0,
    massimale_ore                 REAL NOT NULL DEFAULT 0,
    soglia_preapprovazione_ore    REAL NOT NULL DEFAULT 0,
    warning_compenso_orario_json  TEXT NOT NULL DEFAULT '[]',
    totale                        REAL NOT NULL DEFAULT 0,
    accettato_il                  TEXT,
    id_preventivo_precedente      TEXT NOT NULL DEFAULT '',
    token_portale                 TEXT NOT NULL DEFAULT '',
    creato_il                     TEXT,
    profilo_deposito_json         TEXT NOT NULL DEFAULT '{}',
    dati_json                     TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_preventivi_records_cliente ON preventivi_records(id_cliente);
CREATE INDEX IF NOT EXISTS idx_preventivi_records_stato   ON preventivi_records(stato, data_emissione);
CREATE INDEX IF NOT EXISTS idx_preventivi_records_pratica ON preventivi_records(id_pratica, area_pratica);

CREATE TABLE IF NOT EXISTS conferimenti_records (
    conferimento_id               TEXT PRIMARY KEY,
    numero                        TEXT NOT NULL,
    id_preventivo                 TEXT NOT NULL DEFAULT '',
    id_cliente                    TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    id_fascicolo                  TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    data_incarico                 TEXT NOT NULL,
    oggetto                       TEXT NOT NULL DEFAULT '',
    stato                         TEXT NOT NULL DEFAULT 'ATTIVO',
    workflow_channel              TEXT NOT NULL DEFAULT 'STUDIO',
    tipo_compenso                 TEXT NOT NULL DEFAULT '',
    tipo_procedimento             TEXT NOT NULL DEFAULT '',
    area_pratica                  TEXT NOT NULL DEFAULT '',
    id_pratica                    TEXT NOT NULL DEFAULT '',
    procedura_operativa_codice    TEXT NOT NULL DEFAULT '',
    procedura_operativa_nome      TEXT NOT NULL DEFAULT '',
    canale_operativo              TEXT NOT NULL DEFAULT '',
    registro_operativo            TEXT NOT NULL DEFAULT '',
    classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]',
    criterio_arrotondamento_orario TEXT NOT NULL DEFAULT '',
    massimale_ore                 REAL NOT NULL DEFAULT 0,
    soglia_preapprovazione_ore    REAL NOT NULL DEFAULT 0,
    warning_compenso_orario_json  TEXT NOT NULL DEFAULT '[]',
    compenso_pattuito             REAL NOT NULL DEFAULT 0,
    firma_cliente_eseguita        INTEGER NOT NULL DEFAULT 0,
    fascicolo_aperto_il           TEXT,
    profilo_deposito_json         TEXT NOT NULL DEFAULT '{}',
    dati_json                     TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_conferimenti_records_cliente ON conferimenti_records(id_cliente);
CREATE INDEX IF NOT EXISTS idx_conferimenti_records_stato   ON conferimenti_records(stato, data_incarico);

-- ---- Parcelle e pagamenti
CREATE TABLE IF NOT EXISTS parcelle (
    id                            TEXT PRIMARY KEY,
    numero                        TEXT NOT NULL,
    id_cliente                    TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    id_fascicolo                  TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    data_emissione                TEXT NOT NULL,
    data_scadenza                 TEXT,
    stato                         TEXT NOT NULL DEFAULT 'BOZZA',
    totale                        REAL NOT NULL DEFAULT 0,
    imponibile                    REAL NOT NULL DEFAULT 0,
    origine                       TEXT NOT NULL DEFAULT '',
    id_preventivo                 TEXT NOT NULL DEFAULT '',
    id_pratica                    TEXT NOT NULL DEFAULT '',
    area_pratica                  TEXT NOT NULL DEFAULT '',
    procedura_operativa_codice    TEXT NOT NULL DEFAULT '',
    procedura_operativa_nome      TEXT NOT NULL DEFAULT '',
    canale_operativo              TEXT NOT NULL DEFAULT '',
    registro_operativo            TEXT NOT NULL DEFAULT '',
    tipo_compenso                 TEXT NOT NULL DEFAULT '',
    tipo_procedimento             TEXT NOT NULL DEFAULT '',
    valore_controversia           REAL NOT NULL DEFAULT 0,
    complessita                   TEXT NOT NULL DEFAULT '',
    data_pagamento                TEXT,
    metodo_pagamento              TEXT,
    creato_da                     TEXT NOT NULL DEFAULT '',
    creato_il                     TEXT,
    dati_json                     TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_parcelle_cliente ON parcelle(id_cliente);
CREATE INDEX IF NOT EXISTS idx_parcelle_fascicolo ON parcelle(id_fascicolo);
CREATE INDEX IF NOT EXISTS idx_parcelle_stato ON parcelle(stato, data_emissione);

CREATE TABLE IF NOT EXISTS payment_links (
    id                            TEXT PRIMARY KEY,
    token                         TEXT NOT NULL UNIQUE,
    id_parcella                   TEXT NOT NULL DEFAULT '',
    id_cliente                    TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    importo                       REAL NOT NULL DEFAULT 0,
    valuta                        TEXT NOT NULL DEFAULT 'EUR',
    stato                         TEXT NOT NULL DEFAULT 'ATTESO',
    provider_usato                TEXT NOT NULL DEFAULT '',
    provider_tx_id                TEXT NOT NULL DEFAULT '',
    creato_il                     TEXT,
    scade_il                      TEXT,
    pagato_il                     TEXT,
    dati_json                     TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_payment_links_cliente ON payment_links(id_cliente);
CREATE INDEX IF NOT EXISTS idx_payment_links_parcella ON payment_links(id_parcella);
CREATE INDEX IF NOT EXISTS idx_payment_links_stato ON payment_links(stato, creato_il);

CREATE TABLE IF NOT EXISTS payment_config (
    config_id                     TEXT PRIMARY KEY,
    provider_count                INTEGER NOT NULL DEFAULT 0,
    updated_at                    TEXT,
    dati_json                     TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS settings_config (
    section                       TEXT PRIMARY KEY,
    updated_at                    TEXT NOT NULL,
    source                        TEXT NOT NULL DEFAULT 'config_studio',
    secret_fields_json            TEXT NOT NULL DEFAULT '[]',
    dati_json                     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_settings_config_updated ON settings_config(updated_at);

-- ---- Messaggi
CREATE TABLE IF NOT EXISTS messaggi (
    id                    TEXT PRIMARY KEY,
    canale                TEXT NOT NULL DEFAULT 'EMAIL',
    stato                 TEXT NOT NULL DEFAULT 'BOZZA',
    oggetto               TEXT,
    corpo                 TEXT,
    email_destinatario    TEXT,
    telefono_destinatario TEXT,
    id_cliente            TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    id_fascicolo          TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    tipo_automazione      TEXT,
    inviato_il            TEXT,
    errore_invio          TEXT,
    creato_il             TEXT,
    dati_json             TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_msg_stato    ON messaggi(stato);
CREATE INDEX IF NOT EXISTS idx_msg_canale   ON messaggi(canale);
CREATE INDEX IF NOT EXISTS idx_msg_cliente  ON messaggi(id_cliente);

-- ---- Utenti
CREATE TABLE IF NOT EXISTS utenti (
    id                  TEXT PRIMARY KEY,
    username            TEXT UNIQUE NOT NULL,
    email               TEXT,
    nome_completo       TEXT,
    ruolo               TEXT NOT NULL DEFAULT 'SEGRETERIA',
    password_hash       TEXT NOT NULL,
    attivo              INTEGER DEFAULT 1,
    must_change_password INTEGER DEFAULT 0,
    permessi_extra      TEXT DEFAULT '[]',
    permessi_negati     TEXT DEFAULT '[]',
    creato_il           TEXT,
    ultimo_accesso      TEXT,
    dati_json           TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_utenti_ruolo     ON utenti(ruolo);
CREATE INDEX IF NOT EXISTS idx_utenti_attivo    ON utenti(attivo);

-- ---- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id           TEXT PRIMARY KEY,
    timestamp    TEXT NOT NULL,
    id_utente    TEXT,
    username     TEXT,
    azione       TEXT NOT NULL,
    risorsa_tipo TEXT,
    risorsa_id   TEXT,
    dettagli     TEXT,
    ip           TEXT,
    esito        TEXT DEFAULT 'OK'
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp  ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_utente     ON audit_log(id_utente);
CREATE INDEX IF NOT EXISTS idx_audit_azione     ON audit_log(azione);
CREATE INDEX IF NOT EXISTS idx_audit_esito      ON audit_log(esito);

-- ---- Registro moduli dati
CREATE TABLE IF NOT EXISTS moduli_dati (
    nome              TEXT PRIMARY KEY,
    percorso          TEXT NOT NULL,
    storage_kind      TEXT NOT NULL DEFAULT 'json',
    inizializzato_il  TEXT,
    payload_json      TEXT DEFAULT '{}'
);

-- ---- Mirror SQL governato dei moduli JSON estesi
CREATE TABLE IF NOT EXISTS moduli_json_records (
    modulo        TEXT NOT NULL,
    record_key    TEXT NOT NULL,
    record_index  INTEGER NOT NULL DEFAULT 0,
    record_kind   TEXT NOT NULL DEFAULT 'dict',
    payload_json  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (modulo, record_key),
    FOREIGN KEY (modulo) REFERENCES moduli_dati(nome) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_moduli_json_records_modulo ON moduli_json_records(modulo);

-- ---- Privacy (registro trattamenti GDPR)
CREATE TABLE IF NOT EXISTS privacy_trattamenti (
    id                        TEXT PRIMARY KEY,
    nome                      TEXT NOT NULL,
    finalita                  TEXT,
    categoria_dati            TEXT,
    base_giuridica            TEXT,
    soggetti_interessati      TEXT,
    destinatari               TEXT,
    trasferimento_extra_ue    INTEGER DEFAULT 0,
    paese_destinazione        TEXT,
    termine_conservazione     TEXT,
    misure_sicurezza          TEXT,
    responsabile              TEXT,
    attivo                    INTEGER DEFAULT 1,
    note                      TEXT,
    creato_il                 TEXT,
    modificato_il             TEXT,
    dati_json                 TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_privacy_attivo   ON privacy_trattamenti(attivo);
CREATE INDEX IF NOT EXISTS idx_privacy_nome     ON privacy_trattamenti(nome);

-- ---- Notifiche
CREATE TABLE IF NOT EXISTS notifiche_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT,
    tipo           TEXT,
    cliente        TEXT,
    numero         TEXT,
    utente         TEXT,
    esito_json     TEXT DEFAULT '{}',
    payload_json   TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_notifiche_ts     ON notifiche_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_notifiche_tipo   ON notifiche_log(tipo);

-- ---- Backup
CREATE TABLE IF NOT EXISTS backup_config (
    chiave         TEXT PRIMARY KEY,
    valore         TEXT,
    payload_json   TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS backup_records (
    id               TEXT PRIMARY KEY,
    timestamp        TEXT NOT NULL,
    tipo             TEXT NOT NULL,
    stato            TEXT NOT NULL,
    percorso_file    TEXT,
    hash_file        TEXT,
    dimensione_bytes INTEGER DEFAULT 0,
    num_file         INTEGER DEFAULT 0,
    componenti_json  TEXT DEFAULT '[]',
    cifrato          INTEGER DEFAULT 0,
    nota             TEXT,
    errore           TEXT,
    backup_base_id   TEXT,
    dati_json        TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_backup_timestamp ON backup_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_backup_stato     ON backup_records(stato);
CREATE INDEX IF NOT EXISTS idx_backup_tipo      ON backup_records(tipo);

-- ---- Search index unificato
CREATE VIRTUAL TABLE IF NOT EXISTS search_documenti USING fts5(
    tipo UNINDEXED,
    entity_id UNINDEXED,
    titolo,
    corpo,
    meta UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 1'
);

CREATE TABLE IF NOT EXISTS search_meta_indice (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);

CREATE TABLE IF NOT EXISTS search_ocr_cache (
    hash_sha256  TEXT PRIMARY KEY,
    testo        TEXT,
    elaborato_il TEXT
);
""" + "\n" + SCHEMA_SQL_PDP_PENALE + "\n" + SCHEMA_SQL_TELEMATICO


# ================================================================ GestioneDatabase

class GestioneDatabase:
    """
    Gestore centralizzato del database per lo studio legale.

    Fornisce strumenti di analisi, verifica integrità, ottimizzazione
    e migrazione per tutti i moduli dati del sistema.

    Esempio::

        gdb = GestioneDatabase({
            "clienti": "./clienti/anagrafica.json",
            "fascicoli": "./fascicoli/fascicoli.json",
            ...
        })
        stats = gdb.statistiche()
        problemi = gdb.verifica_integrita()
    """

    MODULI_SQLITE = [
        "clienti", "condivisioni", "note_faldone", "fascicoli",
        "appuntamenti", "calendar_sync", "scadenze", "timesheet", "time_tracking",
        "preventivi", "conferimenti", "fatturazione",
        "pagamenti_links", "pagamenti_config", "impostazioni", "messaggi",
        "email_casella", "email_ordinaria", "utenti", "audit",
        "privacy", "notifiche", "backup", "portale", "soggetti",
        "soggetti_parti", "wizard_pro", "legal_intelligence",
        "normative_tables", "giurisprudenza", "workspace_intelligence",
        "local_ai", "validation_runs", "template_atti",
        "template_atti_prefs", "redaction_assistant", "telematico",
    ]

    MODULI_SQLITE_STRUTTURATI = {
        "clienti", "fascicoli", "appuntamenti", "scadenze",
        "timesheet", "time_tracking", "preventivi", "conferimenti", "fatturazione",
        "pagamenti_links", "pagamenti_config", "impostazioni", "messaggi", "utenti",
        "soggetti", "soggetti_parti",
        "audit", "privacy", "notifiche", "backup",
    }

    MODULI_SQLITE_TABELLE = {
        "clienti": ("clienti", "id"),
        "fascicoli": ("fascicoli", "id"),
        "appuntamenti": ("appuntamenti", "id"),
        "scadenze": ("scadenze", "id"),
        "timesheet": ("timesheet_entries", "id"),
        "time_tracking": ("time_tracking_timers", "id"),
        "preventivi": ("preventivi_records", "preventivo_id"),
        "conferimenti": ("conferimenti_records", "conferimento_id"),
        "fatturazione": ("parcelle", "id"),
        "pagamenti_links": ("payment_links", "id"),
        "pagamenti_config": ("payment_config", "config_id"),
        "impostazioni": ("settings_config", "section"),
        "messaggi": ("messaggi", "id"),
        "utenti": ("utenti", "id"),
        "soggetti": ("soggetti", "id"),
        "soggetti_parti": ("soggetti_parti", "id"),
        "audit": ("audit_log", "id"),
        "privacy": ("privacy_trattamenti", "id"),
        "notifiche": ("notifiche_log", "id"),
        "backup": ("backup_records", "id"),
    }

    # Domini che non devono mai diminuire in un DB operativo esistente durante
    # l'attivazione SQL. Audit/notifiche possono crescere durante la stessa
    # operazione e vengono validati nel report, ma non bloccano il cutover.
    MODULI_SQLITE_ANTI_PERDITA = {
        "clienti", "fascicoli", "appuntamenti", "scadenze",
        "timesheet", "time_tracking", "preventivi", "conferimenti",
        "fatturazione", "pagamenti_links", "impostazioni", "messaggi", "utenti",
        "soggetti", "soggetti_parti",
        "privacy", "backup",
    }

    def __init__(self, percorsi: Dict[str, str]):
        """
        Parameters
        ----------
        percorsi:
            Dizionario {nome_modulo: percorso_file_json}.
            Chiavi riconosciute: clienti, fascicoli, appuntamenti,
            scadenze, timesheet, messaggi, utenti, audit, privacy, notifiche,
            backup, search_index.
        """
        self.percorsi = {k: Path(v) for k, v in percorsi.items() if v}

    @staticmethod
    def _search_index_documenti_table(conn: sqlite3.Connection) -> Optional[str]:
        """Rileva il nome tabella documenti dell'indice di ricerca."""
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "documenti" in tables:
            return "documenti"
        if "search_documenti" in tables:
            return "search_documenti"
        return None

    def _moduli_monitorati(self) -> List[str]:
        """Ritorna i moduli JSON monitorati nel pannello admin."""
        chiavi = [
            chiave
            for chiave, percorso in self.percorsi.items()
            if chiave != "search_index" and percorso.suffix.lower() == ".json"
        ]
        core = [chiave for chiave in self.MODULI_SQLITE if chiave in chiavi]
        extra = sorted(chiave for chiave in chiavi if chiave not in self.MODULI_SQLITE)
        return core + extra

    # ---------------------------------------------------------------- I/O

    def _leggi_json(self, chiave: str) -> Tuple[List[dict], Optional[str]]:
        """Legge un file JSON. Ritorna (lista_record, errore_o_None)."""
        p = self.percorsi.get(chiave)
        if not p or not p.exists():
            return [], None
        try:
            raw = json.loads(p.read_text("utf-8"))
            if isinstance(raw, dict):
                # JSON salvato come {id: record} (format dei moduli)
                return list(raw.values()), None
            elif isinstance(raw, list):
                return raw, None
            else:
                return [], f"Formato sconosciuto: {type(raw).__name__}"
        except json.JSONDecodeError as e:
            return [], f"JSON non valido: {e}"
        except Exception as e:
            return [], str(e)

    def _leggi_json_grezzo(self, chiave: str) -> Tuple[Any, Optional[str]]:
        """Legge un file JSON restituendo la struttura originale."""
        p = self.percorsi.get(chiave)
        if not p or not p.exists():
            return None, None
        try:
            return json.loads(p.read_text("utf-8")), None
        except json.JSONDecodeError as e:
            return None, f"JSON non valido: {e}"
        except Exception as e:
            return None, str(e)

    def _scrivi_json_grezzo(self, chiave: str, payload: Any) -> None:
        """Scrive un file JSON preservando la struttura lista/dizionario."""
        p = self.percorsi.get(chiave)
        if not p:
            raise ValueError(f"Percorso non configurato per {chiave}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")

    @staticmethod
    def _records_from_raw(raw: Any) -> List[dict]:
        if isinstance(raw, dict):
            return [item for item in raw.values() if isinstance(item, dict)]
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        return []

    @staticmethod
    def _payload_json(payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def _json_record_entries(cls, raw: Any) -> List[Tuple[str, int, str, Any]]:
        """Normalizza qualunque JSON monitorato in record SQL ordinati."""
        if raw is None:
            return []
        if isinstance(raw, dict):
            return [
                (str(key), index, type(value).__name__, value)
                for index, (key, value) in enumerate(raw.items())
            ]
        if isinstance(raw, list):
            entries: List[Tuple[str, int, str, Any]] = []
            for index, value in enumerate(raw):
                candidate = ""
                if isinstance(value, dict):
                    for field_name in ("id", "uuid", "slug", "codice", "numero", "msg_id", "message_id"):
                        if value.get(field_name):
                            candidate = str(value.get(field_name))
                            break
                record_key = f"{index:06d}:{candidate}" if candidate else f"idx_{index:06d}"
                entries.append((record_key, index, type(value).__name__, value))
            return entries
        return [("__root__", 0, type(raw).__name__, raw)]

    @classmethod
    def _soggetti_parti_entries(cls, raw: Any) -> List[Tuple[str, int, str, dict]]:
        """Flatten del formato storico {id_fascicolo: [parti]} in righe SQL."""
        rows: List[Tuple[str, int, str, dict]] = []
        if raw is None:
            return rows
        candidates: list[tuple[str, Any]] = []
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, list):
                    candidates.extend((str(key) if key != "parti" else "", item) for item in value)
                elif isinstance(value, dict):
                    candidates.append((str(key), value))
        elif isinstance(raw, list):
            candidates.extend(("", item) for item in raw)
        for index, (id_fascicolo, value) in enumerate(candidates):
            if not isinstance(value, dict):
                continue
            payload = dict(value)
            if id_fascicolo and not payload.get("id_fascicolo"):
                payload["id_fascicolo"] = id_fascicolo
            payload.setdefault("id_fascicolo", "")
            record_id = str(payload.get("id") or "").strip()
            if not record_id:
                stable = "|".join(
                    str(payload.get(field) or "")
                    for field in ("id_fascicolo", "id_soggetto", "ruolo", "data_aggiunta")
                )
                record_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"iusentra:soggetti_parti:{stable}:{index}"))[:12]
                payload["id"] = record_id
            rows.append((record_id, index, "dict", payload))
        return rows

    @classmethod
    def _json_record_payload(cls, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return cls._payload_json(value)
        return cls._payload_json({"value": value})

    @staticmethod
    def _canonical_payload(value: Any) -> str:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                value = {"value": value}
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _source_record_identity(
        cls,
        chiave: str,
        record_key: str,
        payload: Any,
    ) -> str:
        if chiave == "pagamenti_config":
            return "default" if payload else ""
        if chiave not in cls.MODULI_SQLITE_STRUTTURATI:
            return record_key
        if isinstance(payload, dict):
            candidates = (
                "id",
                "preventivo_id",
                "conferimento_id",
                "uuid",
                "slug",
                "codice",
                "numero",
                "msg_id",
                "message_id",
            )
            for field_name in candidates:
                value = payload.get(field_name)
                if value not in (None, ""):
                    return str(value)
        return ""

    @classmethod
    def _source_payloads_for_module(cls, chiave: str, raw: Any) -> Dict[str, str]:
        if chiave == "impostazioni":
            return cls._settings_config_source_payloads(raw)
        if chiave == "pagamenti_config":
            return {"default": cls._canonical_payload(raw)} if raw else {}
        if chiave == "soggetti_parti":
            return {
                record_key: cls._canonical_payload(payload)
                for record_key, _record_index, _record_kind, payload in cls._soggetti_parti_entries(raw)
            }
        payloads: Dict[str, str] = {}
        for record_key, _record_index, _record_kind, payload in cls._json_record_entries(raw):
            identity = cls._source_record_identity(chiave, record_key, payload)
            if not identity:
                continue
            stored_payload = cls._json_record_payload(payload) if chiave not in cls.MODULI_SQLITE_STRUTTURATI else payload
            payloads[identity] = cls._canonical_payload(stored_payload)
        return payloads

    @classmethod
    def _source_summary_for_module(cls, chiave: str, raw: Any) -> Dict[str, Any]:
        if chiave == "impostazioni":
            payloads = cls._settings_config_source_payloads(raw)
            return {
                "count": len(payloads),
                "ids": set(payloads),
                "payloads": payloads,
            }
        if chiave == "pagamenti_config":
            count = 1 if raw else 0
        elif chiave == "soggetti_parti":
            count = len(cls._soggetti_parti_entries(raw))
        else:
            count = len(cls._json_record_entries(raw))
        payloads = cls._source_payloads_for_module(chiave, raw)
        return {
            "count": count,
            "ids": set(payloads),
            "payloads": payloads,
        }

    @classmethod
    def _settings_config_source_payloads(cls, raw: Any) -> Dict[str, str]:
        if not isinstance(raw, dict) or not raw:
            return {}
        try:
            from pct.config_studio import ConfigStudio
            from pct.impostazioni_config_repository import settings_config_rows_from_config

            cfg = ConfigStudio.from_dict(raw)
            rows = settings_config_rows_from_config(cfg)
            return {
                str(row.get("section") or ""): cls._canonical_payload(row.get("dati") or {})
                for row in rows
                if row.get("section")
            }
        except Exception:
            return {
                str(section): cls._canonical_payload(payload)
                for section, payload in raw.items()
                if str(section or "").strip()
            }

    def _source_migration_snapshot(self) -> Dict[str, Dict[str, Any]]:
        snapshot: Dict[str, Dict[str, Any]] = {}
        for chiave in self._moduli_monitorati():
            if chiave not in self.MODULI_SQLITE:
                continue
            raw, err = self._leggi_json_grezzo(chiave)
            if err:
                snapshot[chiave] = {"count": 0, "ids": set(), "payloads": {}, "errore": err}
                continue
            snapshot[chiave] = self._source_summary_for_module(chiave, raw)
        return snapshot

    @staticmethod
    def _sqlite_has_table(conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        return bool(row)

    @staticmethod
    def _sqlite_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
        try:
            return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table_name}")')}
        except sqlite3.Error:
            return set()

    @classmethod
    def _sqlite_structured_snapshot(
        cls,
        conn: sqlite3.Connection,
        chiave: str,
    ) -> Dict[str, Any]:
        table_info = cls.MODULI_SQLITE_TABELLE.get(chiave)
        if not table_info:
            return {"count": 0, "ids": set(), "payloads": {}}
        table_name, id_column = table_info
        if not cls._sqlite_has_table(conn, table_name):
            return {"count": 0, "ids": set(), "payloads": {}}
        columns = cls._sqlite_table_columns(conn, table_name)
        count_row = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
        count = int((count_row or [0])[0] or 0)
        ids: set[str] = set()
        payloads: Dict[str, str] = {}
        if id_column in columns:
            select_columns = f'"{id_column}"'
            if "dati_json" in columns:
                select_columns += ', dati_json'
            for row in conn.execute(f'SELECT {select_columns} FROM "{table_name}"').fetchall():
                identity = str(row[0] or "")
                if not identity:
                    continue
                ids.add(identity)
                if "dati_json" in columns and len(row) > 1 and row[1]:
                    payloads[identity] = cls._canonical_payload(row[1])
        return {"count": count, "ids": ids, "payloads": payloads}

    @classmethod
    def _sqlite_extended_snapshot(
        cls,
        conn: sqlite3.Connection,
        chiave: str,
    ) -> Dict[str, Any]:
        if not cls._sqlite_has_table(conn, "moduli_json_records"):
            return {"count": 0, "ids": set(), "payloads": {}}
        rows = conn.execute(
            """
            SELECT record_key, payload_json
            FROM moduli_json_records
            WHERE modulo = ?
            """,
            (chiave,),
        ).fetchall()
        payloads = {
            str(row[0]): cls._canonical_payload(row[1])
            for row in rows
            if row and row[0] not in (None, "")
        }
        return {"count": len(rows), "ids": set(payloads), "payloads": payloads}

    @classmethod
    def _sqlite_snapshot_for_module(
        cls,
        conn: sqlite3.Connection,
        chiave: str,
    ) -> Dict[str, Any]:
        if chiave in cls.MODULI_SQLITE_STRUTTURATI:
            return cls._sqlite_structured_snapshot(conn, chiave)
        if chiave in cls.MODULI_SQLITE:
            return cls._sqlite_extended_snapshot(conn, chiave)
        return {"count": 0, "ids": set(), "payloads": {}}

    def _sqlite_migration_snapshot(self, db_path: Path) -> Dict[str, Dict[str, Any]]:
        if not db_path.exists():
            return {}
        snapshot: Dict[str, Dict[str, Any]] = {}
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                for chiave in self._moduli_monitorati():
                    if chiave not in self.MODULI_SQLITE:
                        continue
                    snapshot[chiave] = self._sqlite_snapshot_for_module(conn, chiave)
            finally:
                conn.close()
        except sqlite3.Error:
            return {}
        return snapshot

    def _anti_loss_precheck(self, target_db_path: Path) -> Dict[str, Any]:
        source = self._source_migration_snapshot()
        existing = self._sqlite_migration_snapshot(target_db_path)
        blockers: List[str] = []
        modules: Dict[str, Dict[str, Any]] = {}
        for chiave, existing_info in existing.items():
            if chiave not in self.MODULI_SQLITE:
                continue
            source_info = source.get(chiave, {"count": 0, "ids": set(), "payloads": {}})
            existing_count = int(existing_info.get("count") or 0)
            source_count = int(source_info.get("count") or 0)
            existing_ids = set(existing_info.get("ids") or set())
            source_ids = set(source_info.get("ids") or set())
            missing_existing = sorted(existing_ids - source_ids) if source_ids else []
            only_source = sorted(source_ids - existing_ids) if existing_ids else sorted(source_ids)
            source_payloads = dict(source_info.get("payloads") or {})
            existing_payloads = dict(existing_info.get("payloads") or {})
            payload_mismatches = [
                identity
                for identity, payload in source_payloads.items()
                if identity in existing_payloads and existing_payloads[identity] != payload
            ]
            is_guarded = (
                chiave in self.MODULI_SQLITE_ANTI_PERDITA
                or (chiave not in self.MODULI_SQLITE_STRUTTURATI and chiave in self.MODULI_SQLITE)
            )
            status = "ok"
            reason = ""
            if is_guarded and existing_count > source_count:
                status = "blocked"
                reason = (
                    f"il database operativo contiene {existing_count} record, "
                    f"la sorgente JSON ne contiene {source_count}"
                )
                blockers.append(
                    f"Blocco anti-perdita su {chiave}: {reason}."
                )
            elif is_guarded and missing_existing:
                status = "blocked"
                sample = ", ".join(missing_existing[:5])
                reason = f"record gia' presenti nel database assenti dalla sorgente JSON: {sample}"
                blockers.append(f"Blocco anti-perdita su {chiave}: {reason}.")
            modules[chiave] = {
                "json_count": source_count,
                "existing_sqlite_count": existing_count,
                "missing_existing_ids": missing_existing[:20],
                "only_source_ids": only_source[:20],
                "payload_mismatches": payload_mismatches[:20],
                "only_database_count": len(missing_existing),
                "only_source_count": len(only_source),
                "conflict_count": len(payload_mismatches),
                "status": status,
                "reason": reason,
            }
        return {
            "ok": not blockers,
            "target_exists": target_db_path.exists(),
            "target_db": str(target_db_path),
            "modules": modules,
            "blockers": blockers,
        }

    @staticmethod
    def _sqlite_writable_probe(db_path: Path) -> str:
        if db_path.exists() and not db_path.is_file():
            return "Il percorso SQLite esiste ma non e' un file."
        parent = db_path.parent
        if not parent.exists():
            return "La cartella del database SQLite non esiste."
        probe = parent / f".iusentra-write-probe-{int(time.time() * 1000)}.tmp"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except Exception as exc:
            return f"La cartella del database non e' scrivibile: {exc}"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path), timeout=1)
                try:
                    conn.execute("PRAGMA quick_check").fetchone()
                finally:
                    conn.close()
            except sqlite3.OperationalError as exc:
                return f"Database SQLite non leggibile o bloccato: {exc}"
            except sqlite3.Error as exc:
                return f"Database SQLite non valido: {exc}"
        return ""

    @staticmethod
    def _sqlite_disk_free_label(db_path: Path) -> str:
        try:
            usage = shutil.disk_usage(str(db_path.parent if db_path.parent.exists() else db_path.parent.parent))
        except Exception:
            return "n.d."
        free = usage.free
        if free < 1024:
            return f"{free} B"
        if free < 1024 ** 2:
            return f"{free / 1024:.1f} KB"
        if free < 1024 ** 3:
            return f"{free / 1024 ** 2:.1f} MB"
        return f"{free / 1024 ** 3:.1f} GB"

    def preverifica_attivazione_sqlite(self, percorso_db: str) -> Dict[str, Any]:
        """Analisi non distruttiva prima dell'attivazione SQLite operativa."""
        db_path = resolve_sqlite_path(percorso_db)
        precheck = self._anti_loss_precheck(db_path)
        writable_error = self._sqlite_writable_probe(db_path)
        if writable_error:
            precheck.setdefault("blockers", []).append(writable_error)
            precheck["ok"] = False
        modules = precheck.get("modules") or {}
        blocked = not bool(precheck.get("ok", True))
        has_existing = bool(precheck.get("target_exists"))
        has_only_database = any(int(row.get("only_database_count") or 0) > 0 for row in modules.values())
        has_conflicts = any(int(row.get("conflict_count") or 0) > 0 for row in modules.values())
        if blocked:
            stato = "Bloccata per protezione dati"
            messaggio = (
                "Pre-verifica SQLite completata: il database esistente contiene dati da preservare "
                "prima dell'attivazione."
            )
            azione = (
                "Usare la riconciliazione sicura: il database esistente resta la base, i record "
                "presenti solo nella sorgente vengono aggiunti e i conflitti restano da revisione."
            )
        elif has_existing and (has_only_database or has_conflicts):
            stato = "Completata con avvisi non bloccanti"
            messaggio = "Pre-verifica SQLite completata con differenze da presidiare."
            azione = "Eseguire riconciliazione sicura prima dell'attivazione definitiva."
        else:
            stato = "Completata"
            messaggio = "Pre-verifica SQLite completata: non sono emersi blocchi anti-perdita."
            azione = "Puoi procedere con migrazione o attivazione SQLite."
        return {
            "ok": not blocked,
            "stato": stato,
            "messaggio": messaggio,
            "percorso_db": str(db_path),
            "record_migrati": 0,
            "per_modulo": {},
            "errori": list(precheck.get("blockers") or []),
            "avvisi": [
                f"Spazio libero rilevato: {self._sqlite_disk_free_label(db_path)}.",
                "La pre-verifica non modifica i dati dello studio.",
            ],
            "azione_consigliata": azione,
            "audit_migrazione": {"precheck": precheck, "validation": {}, "staging": False},
        }

    def _validate_sqlite_migration(self, db_path: Path) -> Dict[str, Any]:
        source = self._source_migration_snapshot()
        migrated = self._sqlite_migration_snapshot(db_path)
        modules: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []
        warnings: List[str] = []
        for chiave, source_info in source.items():
            migrated_info = migrated.get(chiave, {"count": 0, "ids": set(), "payloads": {}})
            source_count = int(source_info.get("count") or 0)
            migrated_count = int(migrated_info.get("count") or 0)
            source_ids = set(source_info.get("ids") or set())
            migrated_ids = set(migrated_info.get("ids") or set())
            missing_source = sorted(source_ids - migrated_ids) if source_ids else []
            source_payloads = dict(source_info.get("payloads") or {})
            migrated_payloads = dict(migrated_info.get("payloads") or {})
            payload_mismatches = [
                identity
                for identity, payload in source_payloads.items()
                if identity in migrated_payloads and migrated_payloads[identity] != payload
            ]
            status = "ok"
            if migrated_count < source_count:
                status = "error"
                errors.append(
                    f"{chiave}: record SQLite {migrated_count} inferiori alla sorgente JSON {source_count}"
                )
            if missing_source:
                status = "error"
                errors.append(
                    f"{chiave}: record sorgente non presenti in SQLite ({', '.join(missing_source[:5])})"
                )
            if payload_mismatches:
                status = "error"
                errors.append(
                    f"{chiave}: dati_json/payload_json non conserva tutti i campi per {len(payload_mismatches)} record"
                )
            if source_count == 0 and migrated_count > 0:
                warnings.append(
                    f"{chiave}: SQLite contiene {migrated_count} record non presenti nella sorgente JSON corrente"
                )
            modules[chiave] = {
                "json_count": source_count,
                "sqlite_count": migrated_count,
                "missing_source_ids": missing_source[:20],
                "payload_mismatches": payload_mismatches[:20],
                "status": status,
            }
        return {
            "ok": not errors,
            "db_path": str(db_path),
            "modules": modules,
            "errors": errors,
            "warnings": warnings,
        }

    def verifica_migrazione_sqlite(self, percorso_db: str) -> Dict[str, Any]:
        """Verifica pubblica conteggi, identificativi e payload JSON preservati nel DB SQLite."""
        db_path = resolve_sqlite_path(percorso_db)
        return self._validate_sqlite_migration(db_path)

    @staticmethod
    def _install_sqlite_database(source_db_path: Path, target_db_path: Path) -> None:
        target_db_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(source_db_path))
        target = sqlite3.connect(str(target_db_path))
        try:
            source.backup(target)
            target.commit()
        finally:
            source.close()
            target.close()

    @staticmethod
    def _sqlite_identifier(name: str) -> str:
        return '"' + str(name).replace('"', '""') + '"'

    @classmethod
    def _sqlite_table_names_for_merge(cls, conn: sqlite3.Connection) -> List[str]:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    @classmethod
    def _sqlite_table_info_for_merge(cls, conn: sqlite3.Connection, table_name: str) -> Dict[str, Any]:
        rows = conn.execute(f"PRAGMA table_info({cls._sqlite_identifier(table_name)})").fetchall()
        columns = [str(row[1]) for row in rows]
        pk_rows = sorted((int(row[5] or 0), str(row[1])) for row in rows if int(row[5] or 0) > 0)
        pk_columns = [name for _, name in pk_rows]
        return {"columns": columns, "pk_columns": pk_columns}

    @staticmethod
    def _sqlite_row_canonical(row: sqlite3.Row, columns: List[str]) -> str:
        payload = {column: row[column] for column in columns}
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)

    @classmethod
    def _sqlite_copy_table_schema(cls, source: sqlite3.Connection, target: sqlite3.Connection, table_name: str) -> None:
        row = source.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        ).fetchone()
        if row and row[0]:
            target.execute(str(row[0]))

    @classmethod
    def _merge_sqlite_source_into_existing(
        cls,
        source_db_path: Path,
        target_db_path: Path,
    ) -> Dict[str, Any]:
        source = sqlite3.connect(str(source_db_path))
        target = sqlite3.connect(str(target_db_path))
        source.row_factory = sqlite3.Row
        target.row_factory = sqlite3.Row
        report: Dict[str, Any] = {
            "records_imported": 0,
            "already_present": 0,
            "conflicts": [],
            "tables": {},
        }
        try:
            target.execute("PRAGMA foreign_keys = OFF")
            for table_name in cls._sqlite_table_names_for_merge(source):
                if not cls._sqlite_has_table(target, table_name):
                    cls._sqlite_copy_table_schema(source, target, table_name)
                source_info = cls._sqlite_table_info_for_merge(source, table_name)
                target_info = cls._sqlite_table_info_for_merge(target, table_name)
                columns = [column for column in source_info["columns"] if column in target_info["columns"]]
                if not columns:
                    continue
                pk_columns = [
                    column for column in (target_info["pk_columns"] or source_info["pk_columns"])
                    if column in columns
                ]
                table_report = {
                    "imported": 0,
                    "already_present": 0,
                    "conflicts": 0,
                    "preserved_existing": 0,
                    "target_count": 0,
                }
                target_before = int(
                    (target.execute(
                        f"SELECT COUNT(*) FROM {cls._sqlite_identifier(table_name)}"
                    ).fetchone() or [0])[0] or 0
                )
                select_sql = (
                    "SELECT "
                    + ", ".join(cls._sqlite_identifier(column) for column in columns)
                    + f" FROM {cls._sqlite_identifier(table_name)}"
                )
                insert_sql = (
                    f"INSERT INTO {cls._sqlite_identifier(table_name)} "
                    f"({', '.join(cls._sqlite_identifier(column) for column in columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)})"
                )
                for row in source.execute(select_sql).fetchall():
                    existing = None
                    if pk_columns:
                        where = " AND ".join(f"{cls._sqlite_identifier(column)} = ?" for column in pk_columns)
                        existing = target.execute(
                            f"SELECT {', '.join(cls._sqlite_identifier(column) for column in columns)} "
                            f"FROM {cls._sqlite_identifier(table_name)} WHERE {where}",
                            tuple(row[column] for column in pk_columns),
                        ).fetchone()
                    if existing is None and not pk_columns:
                        where = " AND ".join(f"{cls._sqlite_identifier(column)} IS ?" for column in columns)
                        existing = target.execute(
                            f"SELECT {', '.join(cls._sqlite_identifier(column) for column in columns)} "
                            f"FROM {cls._sqlite_identifier(table_name)} WHERE {where}",
                            tuple(row[column] for column in columns),
                        ).fetchone()
                    if existing is None:
                        target.execute(insert_sql, tuple(row[column] for column in columns))
                        table_report["imported"] += 1
                        report["records_imported"] += 1
                        continue
                    if cls._sqlite_row_canonical(existing, columns) == cls._sqlite_row_canonical(row, columns):
                        table_report["already_present"] += 1
                        report["already_present"] += 1
                        continue
                    table_report["conflicts"] += 1
                    report["conflicts"].append(
                        {
                            "table": table_name,
                            "key": {column: row[column] for column in pk_columns} if pk_columns else {},
                            "reason": (
                                "Record gia' presente con contenuto diverso: conservata la versione "
                                "nel database operativo."
                            ),
                        }
                    )
                target_after = int(
                    (target.execute(
                        f"SELECT COUNT(*) FROM {cls._sqlite_identifier(table_name)}"
                    ).fetchone() or [0])[0] or 0
                )
                table_report["preserved_existing"] = max(
                    target_before - table_report["already_present"],
                    0,
                )
                table_report["target_count"] = target_after
                if (
                    table_report["imported"]
                    or table_report["already_present"]
                    or table_report["conflicts"]
                    or table_report["preserved_existing"]
                ):
                    report["tables"][table_name] = table_report
            target.commit()
        finally:
            try:
                target.execute("PRAGMA foreign_keys = ON")
            except sqlite3.Error:
                pass
            source.close()
            target.close()
        return report

    def riconcilia_verso_sqlite(self, percorso_db: str) -> RisultatoMigrazione:
        """Riconcilia SQLite preservando il database operativo come base."""
        t0 = time.monotonic()
        target_db_path = resolve_sqlite_path(percorso_db)
        target_db_path.parent.mkdir(parents=True, exist_ok=True)
        precheck = self._anti_loss_precheck(target_db_path)
        if not target_db_path.exists() or precheck.get("ok", True):
            risultato = self.migra_verso_sqlite(str(target_db_path))
            risultato.audit.setdefault("reconciliation", {"mode": "non necessaria"})
            return risultato

        writable_error = self._sqlite_writable_probe(target_db_path)
        if writable_error:
            ms = int((time.monotonic() - t0) * 1000)
            return RisultatoMigrazione(
                riuscita=False,
                percorso_db=str(target_db_path),
                record_migrati={},
                errori=[writable_error],
                avvisi=["Riconciliazione non eseguita: database operativo non modificato."],
                audit={"precheck": precheck, "validation": {}, "reconciliation": {"executed": False}},
                ms=ms,
            )

        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        backup_db_path = target_db_path.with_name(
            f"{target_db_path.stem}.backup-riconciliazione-{stamp}{target_db_path.suffix}"
        )
        source_db_path = target_db_path.with_name(
            f".{target_db_path.stem}.sorgente-riconciliazione-{stamp}{target_db_path.suffix}"
        )
        staging_db_path = target_db_path.with_name(
            f".{target_db_path.stem}.riconciliazione-{stamp}{target_db_path.suffix}"
        )
        errori: List[str] = []
        avvisi: List[str] = []
        record_migrati: Dict[str, int] = {}
        reconciliation: Dict[str, Any] = {
            "executed": False,
            "mode": "database_esistente_come_base",
            "backup_db": str(backup_db_path),
            "source_db": str(source_db_path),
            "staging_db": str(staging_db_path),
        }

        try:
            self._install_sqlite_database(target_db_path, backup_db_path)
            self._install_sqlite_database(target_db_path, staging_db_path)
            source_result = self.migra_verso_sqlite(str(source_db_path))
            if not source_result.riuscita:
                errori.extend(source_result.errori or ["Migrazione sorgente per riconciliazione non riuscita."])
            else:
                merge_report = self._merge_sqlite_source_into_existing(source_db_path, staging_db_path)
                reconciliation.update(merge_report)
                reconciliation["executed"] = True
                record_migrati = {
                    table: int(row.get("imported") or 0)
                    for table, row in dict(merge_report.get("tables") or {}).items()
                    if int(row.get("imported") or 0) > 0
                }
                conflicts = list(merge_report.get("conflicts") or [])
                if conflicts:
                    avvisi.append(
                        f"Riconciliazione eseguita con {len(conflicts)} conflitti conservati per revisione."
                    )
                validation = self._validate_sqlite_migration(staging_db_path)
                blocking_validation_errors = [
                    str(item)
                    for item in validation.get("errors") or []
                    if "record sorgente non presenti" in str(item)
                ]
                if blocking_validation_errors:
                    errori.extend(blocking_validation_errors)
                reconciliation["validation"] = validation
            if not errori:
                self._install_sqlite_database(staging_db_path, target_db_path)
                try:
                    from pct.storage import StudioDB

                    try:
                        StudioDB.invalidate(str(target_db_path))
                    except AttributeError:
                        pass
                    StudioDB.get(str(target_db_path)).ensure_schema()
                except Exception as exc:
                    errori.append(f"Riallineamento schema SQLite post-riconciliazione non riuscito: {exc}")
        except Exception as exc:
            errori.append(f"Riconciliazione SQLite non riuscita: {exc}")
        finally:
            for cleanup_path in (source_db_path, staging_db_path):
                try:
                    from pct.storage import StudioDB

                    try:
                        StudioDB.invalidate(str(cleanup_path))
                    except AttributeError:
                        pass
                except Exception:
                    pass
                for suffix in ("", "-wal", "-shm"):
                    try:
                        cleanup_path.with_name(cleanup_path.name + suffix).unlink()
                    except (FileNotFoundError, PermissionError):
                        pass

        ms = int((time.monotonic() - t0) * 1000)
        if not errori:
            avvisi.append(
                "Riconciliazione conservativa completata: i record presenti solo nel database operativo sono stati preservati."
            )
        return RisultatoMigrazione(
            riuscita=len(errori) == 0,
            percorso_db=str(target_db_path),
            record_migrati=record_migrati,
            errori=errori,
            avvisi=avvisi,
            audit={
                "precheck": precheck,
                "validation": reconciliation.get("validation", {}),
                "reconciliation": reconciliation,
                "staging": True,
            },
            ms=ms,
        )

    @classmethod
    def _modulo_payload_metadata(cls, path: Path, raw: Any, errore: Optional[str]) -> str:
        payload = {
            "root_type": type(raw).__name__ if raw is not None else "missing",
            "record_entries": len(cls._json_record_entries(raw)),
            "dimensione_bytes": int(path.stat().st_size) if path.exists() else 0,
        }
        if errore:
            payload["errore"] = errore
        return cls._payload_json(payload)

    def _migra_moduli_json_estesi(
        self,
        conn: sqlite3.Connection,
        migrati: Dict[str, int],
        errori: List[str],
    ) -> None:
        """Migra i moduli JSON senza tabella verticale dedicata in un mirror SQL governato."""
        totale = 0
        for chiave in self._moduli_monitorati():
            if chiave in self.MODULI_SQLITE_STRUTTURATI:
                continue
            raw, err = self._leggi_json_grezzo(chiave)
            if err:
                errori.append(f"{chiave}: {err}")
                continue
            if raw is None:
                continue
            count = 0
            conn.execute("DELETE FROM moduli_json_records WHERE modulo = ?", (chiave,))
            for record_key, record_index, record_kind, payload in self._json_record_entries(raw):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO moduli_json_records
                    (modulo, record_key, record_index, record_kind, payload_json)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        chiave,
                        record_key,
                        record_index,
                        record_kind,
                        self._json_record_payload(payload),
                    ),
                )
                count += 1
            migrati[chiave] = count
            totale += count
        migrati["moduli_json_records"] = totale

    def sincronizza_moduli_json_sqlite(
        self,
        percorso_db: str,
        *,
        include_structured: bool = False,
    ) -> Dict[str, Any]:
        """Allinea nel DB tenant il catalogo SQL di tutti i JSON monitorati.

        Il metodo e' idempotente e non sostituisce le tabelle verticali dei
        domini core: aggiorna sempre `moduli_dati` e, quando richiesto, anche
        `moduli_json_records` per ogni JSON tenant-aware.
        """
        t0 = time.monotonic()
        target_db_path = resolve_sqlite_path(percorso_db)
        target_db_path.parent.mkdir(parents=True, exist_ok=True)
        modules: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []
        moduli_count = 0
        records_total = 0
        now = datetime.now().isoformat()

        with sqlite3.connect(str(target_db_path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(SCHEMA_SQL)
            for chiave in self._moduli_monitorati():
                path = self.percorsi.get(chiave)
                if not path:
                    continue
                raw, err = self._leggi_json_grezzo(chiave)
                payload_json = self._modulo_payload_metadata(path, raw, err)
                storage_kind = "json"
                conn.execute(
                    """
                    INSERT INTO moduli_dati
                    (nome, percorso, storage_kind, inizializzato_il, payload_json)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(nome) DO UPDATE SET
                        percorso=excluded.percorso,
                        storage_kind=excluded.storage_kind,
                        payload_json=excluded.payload_json
                    """,
                    (chiave, str(path), storage_kind, now, payload_json),
                )
                moduli_count += 1
                record_count = 0
                if err:
                    errors.append(f"{chiave}: {err}")
                elif raw is None:
                    if include_structured or chiave not in self.MODULI_SQLITE_STRUTTURATI:
                        conn.execute("DELETE FROM moduli_json_records WHERE modulo = ?", (chiave,))
                elif include_structured or chiave not in self.MODULI_SQLITE_STRUTTURATI:
                    conn.execute("DELETE FROM moduli_json_records WHERE modulo = ?", (chiave,))
                    for record_key, record_index, record_kind, payload in self._json_record_entries(raw):
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO moduli_json_records
                            (modulo, record_key, record_index, record_kind, payload_json)
                            VALUES (?,?,?,?,?)
                            """,
                            (
                                chiave,
                                record_key,
                                record_index,
                                record_kind,
                                self._json_record_payload(payload),
                            ),
                        )
                        record_count += 1
                    records_total += record_count
                modules[chiave] = {
                    "path": str(path),
                    "exists": bool(path.exists()),
                    "records": record_count,
                    "error": err or "",
                    "structured": chiave in self.MODULI_SQLITE_STRUTTURATI,
                }
            conn.commit()

        return {
            "ok": not errors,
            "percorso_db": str(target_db_path),
            "moduli_dati": moduli_count,
            "moduli_json_records": records_total,
            "modules": modules,
            "errors": errors,
            "ms": int((time.monotonic() - t0) * 1000),
        }

    def _backup_json_prima_riparazione(self, chiave: str, ts: str) -> str:
        p = self.percorsi.get(chiave)
        if not p or not p.exists():
            return ""
        backup = p.with_name(f"{p.stem}.pre-riparazione-{ts}{p.suffix}.bak")
        shutil.copy2(p, backup)
        return str(backup)

    @staticmethod
    def _append_repair_note(record: dict, message: str) -> None:
        note = str(record.get("note") or "").strip()
        if message in note:
            return
        record["note"] = f"{note}\n{message}".strip() if note else message

    def _stat_file(self, p: Path) -> Tuple[int, str]:
        """(dimensione_bytes, ultima_modifica_iso)"""
        if not p.exists():
            return 0, ""
        st = p.stat()
        return int(st.st_size), datetime.fromtimestamp(st.st_mtime).isoformat()

    # ---------------------------------------------------------------- Statistiche

    def statistiche(self) -> Dict[str, Any]:
        """
        Restituisce le statistiche complete di tutti i moduli.

        Returns
        -------
        dict con chiavi: moduli (lista StatisticheModulo), totale_record,
        totale_dimensione_bytes, generato_il.
        """
        moduli: List[StatisticheModulo] = []
        totale_record = 0
        totale_bytes = 0

        for chiave in self._moduli_monitorati():
            p = self.percorsi.get(chiave)
            sm = StatisticheModulo(
                nome=chiave,
                percorso=str(p) if p else "",
                esiste=bool(p and p.exists()),
                migrabile_sqlite=chiave in self.MODULI_SQLITE,
            )
            if not p:
                sm.stato = "NON_CONFIGURATO"
            elif not p.exists():
                sm.stato = "NON_TROVATO"
            else:
                sm.dimensione_bytes, sm.ultima_modifica = self._stat_file(p)
                records, errore = self._leggi_json(chiave)
                if errore:
                    sm.stato = "ERRORE"
                    sm.errore = errore
                elif not records:
                    sm.stato = "VUOTO"
                    sm.record_totali = 0
                else:
                    sm.stato = "OK"
                    sm.record_totali = len(records)
                    totale_record += len(records)
                    totale_bytes += sm.dimensione_bytes
            moduli.append(sm)

        # Aggiungi indice di ricerca SQLite
        search_p = self.percorsi.get("search_index")
        if search_p:
            sm_s = StatisticheModulo(
                nome="search_index",
                percorso=str(search_p),
                esiste=search_p.exists(),
                migrabile_sqlite=True,
            )
            if search_p.exists():
                sm_s.dimensione_bytes, sm_s.ultima_modifica = self._stat_file(search_p)
                try:
                    conn = sqlite3.connect(str(search_p))
                    table_name = self._search_index_documenti_table(conn)
                    if not table_name:
                        raise RuntimeError("Tabella documenti non trovata nell'indice di ricerca")
                    row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                    sm_s.record_totali = row[0] if row else 0
                    sm_s.stato = "OK"
                    conn.close()
                    totale_bytes += sm_s.dimensione_bytes
                except Exception as e:
                    sm_s.stato = "ERRORE"
                    sm_s.errore = str(e)
            else:
                sm_s.stato = "NON_TROVATO"
            moduli.append(sm_s)

        return {
            "moduli": [m.to_dict() for m in moduli],
            "moduli_monitorati": len(moduli),
            "moduli_migrabili_sqlite": len([m for m in moduli if m.migrabile_sqlite]),
            "totale_record": totale_record,
            "totale_dimensione_bytes": totale_bytes,
            "totale_dimensione": _fmt_bytes(totale_bytes),
            "generato_il": datetime.now().isoformat(),
        }

    # ---------------------------------------------------------------- Integrità

    def verifica_integrita(self) -> List[ProblemaIntegrita]:
        """
        Esegue la verifica di integrità referenziale e validazione dati
        su tutti i moduli.

        Returns
        -------
        Lista di ProblemaIntegrita ordinata per severità (CRITICO → INFO).
        """
        problemi: List[ProblemaIntegrita] = []

        clienti_raw, _ = self._leggi_json("clienti")
        fascicoli_raw, _ = self._leggi_json("fascicoli")
        app_raw, _ = self._leggi_json("appuntamenti")
        scadenze_raw, _ = self._leggi_json("scadenze")
        messaggi_raw, _ = self._leggi_json("messaggi")
        utenti_raw, _ = self._leggi_json("utenti")

        # Set di ID per riferimenti
        id_clienti = {c.get("id") for c in clienti_raw if c.get("id")}
        id_fascicoli = {f.get("id") for f in fascicoli_raw if f.get("id")}
        id_app = {a.get("id") for a in app_raw if a.get("id")}

        # ---- Clienti
        cf_visti: Dict[str, str] = {}
        email_viste: Dict[str, str] = {}
        for c in clienti_raw:
            cid = c.get("id", "?")
            # CF duplicato
            cf = (c.get("codice_fiscale") or "").strip().upper()
            if cf and cf in cf_visti:
                problemi.append(ProblemaIntegrita(
                    modulo="clienti", tipo="DUPLICATO", severita="AVVISO",
                    messaggio=f"Codice fiscale '{cf}' duplicato",
                    id_record=cid, campo="codice_fiscale",
                    suggerimento="Verificare i due clienti e rimuovere il duplicato",
                ))
            elif cf:
                cf_visti[cf] = cid
            # Email duplicata
            email = (c.get("email") or "").strip().lower()
            if email and email in email_viste:
                problemi.append(ProblemaIntegrita(
                    modulo="clienti", tipo="DUPLICATO", severita="AVVISO",
                    messaggio=f"Email '{email}' duplicata",
                    id_record=cid, campo="email",
                    suggerimento="Verificare i due clienti",
                ))
            elif email:
                email_viste[email] = cid
            # Nome mancante
            nome = (c.get("nome") or "") + (c.get("cognome") or "") + (c.get("ragione_sociale") or "")
            if not nome.strip():
                problemi.append(ProblemaIntegrita(
                    modulo="clienti", tipo="DATO_MANCANTE", severita="AVVISO",
                    messaggio="Cliente senza nome, cognome o ragione sociale",
                    id_record=cid, campo="nome",
                    suggerimento="Completare i dati anagrafici",
                ))

        # ---- Fascicoli
        numeri_visti: Dict[str, str] = {}
        for f in fascicoli_raw:
            fid = f.get("id", "?")
            # id_cliente non esistente
            ic = f.get("id_cliente")
            if ic and ic not in id_clienti:
                problemi.append(ProblemaIntegrita(
                    modulo="fascicoli", tipo="RIFERIMENTO_MANCANTE", severita="CRITICO",
                    messaggio=f"Fascicolo riferisce cliente inesistente: {ic!r}",
                    id_record=fid, campo="id_cliente",
                    suggerimento="Correggere l'id_cliente o ricollegare il fascicolo",
                ))
            # Numero duplicato
            numero = f.get("numero", "")
            if numero and numero in numeri_visti:
                problemi.append(ProblemaIntegrita(
                    modulo="fascicoli", tipo="DUPLICATO", severita="CRITICO",
                    messaggio=f"Numero fascicolo '{numero}' duplicato",
                    id_record=fid, campo="numero",
                    suggerimento="Rinumerare uno dei fascicoli",
                ))
            elif numero:
                numeri_visti[numero] = fid
            # Titolo mancante
            if not f.get("titolo", "").strip():
                problemi.append(ProblemaIntegrita(
                    modulo="fascicoli", tipo="DATO_MANCANTE", severita="AVVISO",
                    messaggio="Fascicolo senza titolo",
                    id_record=fid, campo="titolo",
                    suggerimento="Aggiungere un titolo descrittivo",
                ))
            # Data apertura invalida
            da = f.get("data_apertura", "")
            if da:
                try:
                    date.fromisoformat(da)
                except ValueError:
                    problemi.append(ProblemaIntegrita(
                        modulo="fascicoli", tipo="DATO_INVALIDO", severita="AVVISO",
                        messaggio=f"Data apertura non valida: {da!r}",
                        id_record=fid, campo="data_apertura",
                        suggerimento="Correggere il formato data (YYYY-MM-DD)",
                    ))

        # ---- Appuntamenti
        for a in app_raw:
            aid = a.get("id", "?")
            # Data non valida
            data_ora = a.get("data_ora", "")
            if data_ora:
                try:
                    datetime.fromisoformat(data_ora)
                except ValueError:
                    problemi.append(ProblemaIntegrita(
                        modulo="appuntamenti", tipo="DATO_INVALIDO", severita="CRITICO",
                        messaggio=f"Data/ora non valida: {data_ora!r}",
                        id_record=aid, campo="data_ora",
                        suggerimento="Correggere il formato data/ora",
                    ))
            # Titolo mancante
            if not a.get("titolo", "").strip():
                problemi.append(ProblemaIntegrita(
                    modulo="appuntamenti", tipo="DATO_MANCANTE", severita="AVVISO",
                    messaggio="Appuntamento senza titolo",
                    id_record=aid, campo="titolo",
                ))

        # ---- Scadenze
        for s in scadenze_raw:
            sid = s.get("id", "?")
            # id_fascicolo non esistente
            if_id = s.get("id_fascicolo", "")
            if if_id and if_id not in id_fascicoli:
                problemi.append(ProblemaIntegrita(
                    modulo="scadenze", tipo="RIFERIMENTO_MANCANTE", severita="CRITICO",
                    messaggio=f"Scadenza riferisce fascicolo inesistente: {if_id!r}",
                    id_record=sid, campo="id_fascicolo",
                    suggerimento="Ricollegare la scadenza al fascicolo corretto",
                ))
            # id_appuntamento non esistente
            ia_id = s.get("id_appuntamento", "")
            if ia_id and ia_id not in id_app:
                problemi.append(ProblemaIntegrita(
                    modulo="scadenze", tipo="RIFERIMENTO_MANCANTE", severita="AVVISO",
                    messaggio=f"Scadenza riferisce appuntamento inesistente: {ia_id!r}",
                    id_record=sid, campo="id_appuntamento",
                    suggerimento="Aggiornare o cancellare il riferimento all'appuntamento",
                ))
            # Data scadenza invalida
            ds = s.get("data_scadenza", "")
            if ds:
                try:
                    date.fromisoformat(ds)
                except ValueError:
                    problemi.append(ProblemaIntegrita(
                        modulo="scadenze", tipo="DATO_INVALIDO", severita="CRITICO",
                        messaggio=f"Data scadenza non valida: {ds!r}",
                        id_record=sid, campo="data_scadenza",
                        suggerimento="Correggere il formato data (YYYY-MM-DD)",
                    ))

        # ---- Messaggi
        for m in messaggi_raw:
            mid = m.get("id", "?")
            ic = m.get("id_cliente", "")
            if ic and ic not in id_clienti:
                problemi.append(ProblemaIntegrita(
                    modulo="messaggi", tipo="RIFERIMENTO_MANCANTE", severita="AVVISO",
                    messaggio=f"Messaggio riferisce cliente inesistente: {ic!r}",
                    id_record=mid, campo="id_cliente",
                ))
            if_id = m.get("id_fascicolo", "")
            if if_id and if_id not in id_fascicoli:
                problemi.append(ProblemaIntegrita(
                    modulo="messaggi", tipo="RIFERIMENTO_MANCANTE", severita="AVVISO",
                    messaggio=f"Messaggio riferisce fascicolo inesistente: {if_id!r}",
                    id_record=mid, campo="id_fascicolo",
                ))

        # ---- Utenti
        usernames_visti: Dict[str, str] = {}
        for u in utenti_raw:
            uid = u.get("id", "?")
            uname = (u.get("username") or "").strip().lower()
            if uname in usernames_visti:
                problemi.append(ProblemaIntegrita(
                    modulo="utenti", tipo="DUPLICATO", severita="CRITICO",
                    messaggio=f"Username duplicato: {uname!r}",
                    id_record=uid, campo="username",
                    suggerimento="Eliminare l'utente duplicato o rinominarlo",
                ))
            elif uname:
                usernames_visti[uname] = uid
            if not u.get("password_hash", ""):
                problemi.append(ProblemaIntegrita(
                    modulo="utenti", tipo="DATO_MANCANTE", severita="CRITICO",
                    messaggio="Utente senza password hash",
                    id_record=uid, campo="password_hash",
                    suggerimento="Reimpostare la password dell'utente",
                ))

        # Ordina: CRITICO → AVVISO → INFO
        ordine = {"CRITICO": 0, "AVVISO": 1, "INFO": 2}
        problemi.sort(key=lambda p: ordine.get(p.severita, 9))
        return problemi

    def ripara_integrita(self) -> Dict[str, Any]:
        """
        Ripara automaticamente anomalie referenziali risolvibili senza inventare dati.

        Quando il riferimento mancante non puo' essere ricollegato a un record
        reale e univoco, il campo viene scollegato e l'identificativo originale
        resta annotato sul record. Prima di ogni scrittura viene creata una copia
        ``*.pre-riparazione-*.bak`` del file JSON coinvolto.
        """
        t0 = time.monotonic()
        riparazioni: List[RiparazioneIntegrita] = []
        errori: List[str] = []
        backup_files: Dict[str, str] = {}
        touched: set[str] = set()
        ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        ts_label = datetime.now().isoformat(timespec="seconds")

        raw_by_key: Dict[str, Any] = {}
        records_by_key: Dict[str, List[dict]] = {}
        for chiave in ("clienti", "fascicoli", "appuntamenti", "scadenze", "messaggi"):
            raw, err = self._leggi_json_grezzo(chiave)
            if err:
                errori.append(f"{chiave}: {err}")
                continue
            raw_by_key[chiave] = raw
            records_by_key[chiave] = self._records_from_raw(raw)

        def _norm(value: Any) -> str:
            return " ".join(str(value or "").strip().lower().split())

        def _record_id(record: dict) -> str:
            return str(record.get("id") or record.get("uuid") or "?")

        def _unique_by(records: List[dict], *fields: str) -> Dict[str, dict]:
            values: Dict[str, dict] = {}
            duplicates: set[str] = set()
            for record in records:
                for key_field in fields:
                    key = _norm(record.get(key_field))
                    if not key:
                        continue
                    if key in values and values[key] is not record:
                        duplicates.add(key)
                    else:
                        values[key] = record
            return {key: record for key, record in values.items() if key not in duplicates}

        def _cliente_label(record: dict) -> str:
            nome_cognome = f"{record.get('nome', '')} {record.get('cognome', '')}".strip()
            return _norm(record.get("nome_completo") or nome_cognome or record.get("ragione_sociale"))

        def _mark_touched(chiave: str) -> str:
            if chiave not in backup_files:
                backup_files[chiave] = self._backup_json_prima_riparazione(chiave, ts_file)
            touched.add(chiave)
            return backup_files.get(chiave, "")

        def _repair_metadata(record: dict, details: str) -> None:
            history = record.setdefault("riparazioni_integrita", [])
            if isinstance(history, list):
                history.append({"timestamp": ts_label, "dettagli": details})

        def _append_repair(
            *,
            chiave: str,
            record: dict,
            campo: str,
            tipo: str,
            azione: str,
            dettagli: str,
            old: Any,
            new: Any = "",
            backup_file: str = "",
        ) -> None:
            riparazioni.append(
                RiparazioneIntegrita(
                    modulo=chiave,
                    tipo=tipo,
                    id_record=_record_id(record),
                    campo=campo,
                    azione=azione,
                    dettagli=dettagli,
                    valore_precedente=str(old or ""),
                    valore_nuovo=str(new or ""),
                    backup_file=backup_file or backup_files.get(chiave, ""),
                )
            )

        clienti = records_by_key.get("clienti", [])
        fascicoli = records_by_key.get("fascicoli", [])
        appuntamenti = records_by_key.get("appuntamenti", [])
        scadenze = records_by_key.get("scadenze", [])
        messaggi = records_by_key.get("messaggi", [])

        id_clienti = {str(c.get("id")) for c in clienti if c.get("id")}
        id_fascicoli = {str(f.get("id")) for f in fascicoli if f.get("id")}
        id_appuntamenti = {str(a.get("id")) for a in appuntamenti if a.get("id")}
        clienti_by_name: Dict[str, dict] = {}
        duplicate_client_names: set[str] = set()
        for cliente in clienti:
            key = _cliente_label(cliente)
            if not key:
                continue
            if key in clienti_by_name:
                duplicate_client_names.add(key)
            else:
                clienti_by_name[key] = cliente
        clienti_by_name = {k: v for k, v in clienti_by_name.items() if k not in duplicate_client_names}
        clienti_by_email = _unique_by(clienti, "email")
        fascicoli_by_alias = _unique_by(fascicoli, "numero", "id_pratica")

        def _find_fascicolo(record: dict, missing_id: str) -> Optional[dict]:
            direct = fascicoli_by_alias.get(_norm(missing_id))
            if direct:
                return direct
            for candidate_field in ("numero_fascicolo", "fascicolo_numero", "numero", "id_pratica"):
                candidate = fascicoli_by_alias.get(_norm(record.get(candidate_field)))
                if candidate:
                    return candidate
            return None

        # Fascicoli con cliente mancante: ricollega per nome cliente reale o scollega.
        for fascicolo in fascicoli:
            old = str(fascicolo.get("id_cliente") or "").strip()
            if not old or old in id_clienti:
                continue
            backup = _mark_touched("fascicoli")
            candidate = clienti_by_name.get(_norm(fascicolo.get("nome_cliente")))
            if candidate and candidate.get("id"):
                fascicolo["id_cliente"] = candidate["id"]
                details = f"Ricollegato cliente reale da nome_cliente: {fascicolo.get('nome_cliente')!r}."
                _repair_metadata(fascicolo, details)
                _append_repair(
                    chiave="fascicoli",
                    record=fascicolo,
                    campo="id_cliente",
                    tipo="RIFERIMENTO_MANCANTE",
                    azione="ricollegato_cliente",
                    dettagli=details,
                    old=old,
                    new=candidate.get("id"),
                )
            else:
                fascicolo["id_cliente"] = ""
                details = f"Scollegato id_cliente inesistente {old!r}; nome_cliente conservato."
                self._append_repair_note(fascicolo, f"Riparazione integrita {ts_label}: {details}")
                _repair_metadata(fascicolo, details)
                _append_repair(
                    chiave="fascicoli",
                    record=fascicolo,
                    campo="id_cliente",
                    tipo="RIFERIMENTO_MANCANTE",
                    azione="scollegato_cliente_inesistente",
                    dettagli=details,
                    old=old,
                    backup_file=backup,
                )

        # Scadenze: riferimenti orfani a fascicoli/appuntamenti non devono bloccare l'utente.
        for scadenza in scadenze:
            old_fascicolo = str(scadenza.get("id_fascicolo") or "").strip()
            if old_fascicolo and old_fascicolo not in id_fascicoli:
                backup = _mark_touched("scadenze")
                candidate = _find_fascicolo(scadenza, old_fascicolo)
                if candidate and candidate.get("id"):
                    scadenza["id_fascicolo"] = candidate["id"]
                    details = f"Ricollegato al fascicolo reale {candidate.get('numero') or candidate.get('id')}."
                    _repair_metadata(scadenza, details)
                    _append_repair(
                        chiave="scadenze",
                        record=scadenza,
                        campo="id_fascicolo",
                        tipo="RIFERIMENTO_MANCANTE",
                        azione="ricollegato_fascicolo",
                        dettagli=details,
                        old=old_fascicolo,
                        new=candidate.get("id"),
                        backup_file=backup,
                    )
                else:
                    scadenza["id_fascicolo"] = ""
                    details = (
                        f"Scollegato riferimento a fascicolo inesistente {old_fascicolo!r}; "
                        "nessun fascicolo reale univoco trovato."
                    )
                    self._append_repair_note(scadenza, f"Riparazione integrita {ts_label}: {details}")
                    _repair_metadata(scadenza, details)
                    _append_repair(
                        chiave="scadenze",
                        record=scadenza,
                        campo="id_fascicolo",
                        tipo="RIFERIMENTO_MANCANTE",
                        azione="scollegato_fascicolo_inesistente",
                        dettagli=details,
                        old=old_fascicolo,
                        backup_file=backup,
                    )

            old_app = str(scadenza.get("id_appuntamento") or "").strip()
            if old_app and old_app not in id_appuntamenti:
                backup = _mark_touched("scadenze")
                scadenza["id_appuntamento"] = ""
                details = f"Scollegato riferimento ad appuntamento inesistente {old_app!r}."
                self._append_repair_note(scadenza, f"Riparazione integrita {ts_label}: {details}")
                _repair_metadata(scadenza, details)
                _append_repair(
                    chiave="scadenze",
                    record=scadenza,
                    campo="id_appuntamento",
                    tipo="RIFERIMENTO_MANCANTE",
                    azione="scollegato_appuntamento_inesistente",
                    dettagli=details,
                    old=old_app,
                    backup_file=backup,
                )

        # Messaggi: se cliente/fascicolo non sono piu' presenti, conservare il messaggio.
        for messaggio in messaggi:
            old_cliente = str(messaggio.get("id_cliente") or "").strip()
            if old_cliente and old_cliente not in id_clienti:
                backup = _mark_touched("messaggi")
                candidate = clienti_by_email.get(_norm(messaggio.get("email_destinatario")))
                if candidate and candidate.get("id"):
                    messaggio["id_cliente"] = candidate["id"]
                    details = "Ricollegato cliente reale tramite email destinatario."
                    _repair_metadata(messaggio, details)
                    _append_repair(
                        chiave="messaggi",
                        record=messaggio,
                        campo="id_cliente",
                        tipo="RIFERIMENTO_MANCANTE",
                        azione="ricollegato_cliente",
                        dettagli=details,
                        old=old_cliente,
                        new=candidate.get("id"),
                        backup_file=backup,
                    )
                else:
                    messaggio["id_cliente"] = ""
                    details = f"Scollegato riferimento a cliente inesistente {old_cliente!r}."
                    _repair_metadata(messaggio, details)
                    _append_repair(
                        chiave="messaggi",
                        record=messaggio,
                        campo="id_cliente",
                        tipo="RIFERIMENTO_MANCANTE",
                        azione="scollegato_cliente_inesistente",
                        dettagli=details,
                        old=old_cliente,
                        backup_file=backup,
                    )

            old_fascicolo = str(messaggio.get("id_fascicolo") or "").strip()
            if old_fascicolo and old_fascicolo not in id_fascicoli:
                backup = _mark_touched("messaggi")
                candidate = _find_fascicolo(messaggio, old_fascicolo)
                if candidate and candidate.get("id"):
                    messaggio["id_fascicolo"] = candidate["id"]
                    details = f"Ricollegato al fascicolo reale {candidate.get('numero') or candidate.get('id')}."
                    _repair_metadata(messaggio, details)
                    _append_repair(
                        chiave="messaggi",
                        record=messaggio,
                        campo="id_fascicolo",
                        tipo="RIFERIMENTO_MANCANTE",
                        azione="ricollegato_fascicolo",
                        dettagli=details,
                        old=old_fascicolo,
                        new=candidate.get("id"),
                        backup_file=backup,
                    )
                else:
                    messaggio["id_fascicolo"] = ""
                    details = f"Scollegato riferimento a fascicolo inesistente {old_fascicolo!r}."
                    _repair_metadata(messaggio, details)
                    _append_repair(
                        chiave="messaggi",
                        record=messaggio,
                        campo="id_fascicolo",
                        tipo="RIFERIMENTO_MANCANTE",
                        azione="scollegato_fascicolo_inesistente",
                        dettagli=details,
                        old=old_fascicolo,
                        backup_file=backup,
                    )

        for chiave in sorted(touched):
            try:
                self._scrivi_json_grezzo(chiave, raw_by_key[chiave])
            except Exception as exc:
                errori.append(f"{chiave}: salvataggio riparazione non riuscito: {exc}")

        problemi_residui = self.verifica_integrita()
        return {
            "ok": not errori,
            "riparazioni": [riparazione.to_dict() for riparazione in riparazioni],
            "n_riparazioni": len(riparazioni),
            "backup_files": [path for path in backup_files.values() if path],
            "problemi_residui": [problema.to_dict() for problema in problemi_residui],
            "n_problemi_residui": len(problemi_residui),
            "errori": errori,
            "ms": int((time.monotonic() - t0) * 1000),
        }

    # ---------------------------------------------------------------- Ottimizzazione

    def ottimizza(self) -> List[RisultatoOttimizzazione]:
        """
        Esegue ottimizzazioni su tutti i moduli:
        - Compatta i file JSON (rimuove spazi extra, ordina chiavi)
        - VACUUM e ANALYZE sul database SQLite dell'indice di ricerca
        - Aggiorna l'ultima data di ottimizzazione
        """
        risultati: List[RisultatoOttimizzazione] = []

        # Compatta file JSON
        for chiave in self._moduli_monitorati():
            p = self.percorsi.get(chiave)
            if not p or not p.exists():
                continue
            t0 = time.monotonic()
            dim_pre = p.stat().st_size
            try:
                raw = json.loads(p.read_text("utf-8"))
                compatto = json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=False)
                p.write_text(compatto, "utf-8")
                dim_post = p.stat().st_size
                risparmio = dim_pre - dim_post
                ms = int((time.monotonic() - t0) * 1000)
                risultati.append(RisultatoOttimizzazione(
                    modulo=chiave,
                    operazione="compattazione JSON",
                    riuscita=True,
                    dettagli=f"{_fmt_bytes(dim_pre)} → {_fmt_bytes(dim_post)} "
                             f"({'+' if risparmio < 0 else '-'}{abs(risparmio)} B)",
                    ms=ms,
                    bytes_prima=dim_pre,
                    bytes_dopo=dim_post,
                ))
            except Exception as e:
                risultati.append(RisultatoOttimizzazione(
                    modulo=chiave, operazione="compattazione JSON",
                    riuscita=False, dettagli=str(e),
                ))

        # VACUUM + ANALYZE sull'indice di ricerca SQLite
        search_p = self.percorsi.get("search_index")
        if search_p and search_p.exists():
            t0 = time.monotonic()
            dim_pre = search_p.stat().st_size
            try:
                conn = sqlite3.connect(str(search_p))
                try:
                    table_name = self._search_index_documenti_table(conn)
                    if not table_name:
                        raise RuntimeError("Tabella documenti non trovata nell'indice di ricerca")
                    conn.execute(f"INSERT INTO {table_name}({table_name}) VALUES('optimize')")
                    conn.commit()
                finally:
                    conn.close()

                # VACUUM richiede autocommit e non puo' essere eseguito nella
                # transazione aperta dall'ottimizzazione FTS.
                conn = sqlite3.connect(str(search_p), isolation_level=None)
                try:
                    conn.execute("VACUUM")
                    conn.execute("ANALYZE")
                finally:
                    conn.close()
                dim_post = search_p.stat().st_size
                ms = int((time.monotonic() - t0) * 1000)
                risultati.append(RisultatoOttimizzazione(
                    modulo="search_index", operazione="VACUUM + ANALYZE + FTS optimize",
                    riuscita=True,
                    ms=ms,
                    bytes_prima=dim_pre,
                    bytes_dopo=dim_post,
                    dettagli=f"{_fmt_bytes(dim_pre)} → {_fmt_bytes(dim_post)}",
                ))
            except Exception as e:
                risultati.append(RisultatoOttimizzazione(
                    modulo="search_index", operazione="VACUUM",
                    riuscita=False, dettagli=str(e), bytes_prima=dim_pre, bytes_dopo=dim_pre,
                ))

        return risultati

    # ---------------------------------------------------------------- Migrazione SQLite

    def _reset_sqlite_target(self, conn: sqlite3.Connection) -> None:
        """Svuota in modo sicuro il DB target senza richiedere unlink del file."""
        rows = conn.execute(
            """
            SELECT type, name
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
              AND name NOT LIKE 'fts_%'
            ORDER BY
                CASE type
                    WHEN 'trigger' THEN 0
                    WHEN 'index' THEN 1
                    WHEN 'view' THEN 2
                    ELSE 3
                END,
                name DESC
            """
        ).fetchall()
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            for row in rows:
                object_type = str(row["type"] if isinstance(row, sqlite3.Row) else row[0]).lower()
                object_name = str(row["name"] if isinstance(row, sqlite3.Row) else row[1])
                if object_name == "sqlite_sequence":
                    continue
                if object_type == "index":
                    sql = f'DROP INDEX IF EXISTS "{object_name}"'
                elif object_type == "trigger":
                    sql = f'DROP TRIGGER IF EXISTS "{object_name}"'
                elif object_type == "view":
                    sql = f'DROP VIEW IF EXISTS "{object_name}"'
                else:
                    sql = f'DROP TABLE IF EXISTS "{object_name}"'
                try:
                    conn.execute(sql)
                except sqlite3.Error:
                    continue
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    def migra_verso_sqlite(self, percorso_db: str) -> RisultatoMigrazione:
        """
        Migra tutti i dati dai file JSON verso un database SQLite unificato.

        Il database di destinazione viene creato (o ricreato) al percorso
        indicato. I file JSON originali non vengono modificati.

        Parameters
        ----------
        percorso_db:
            Percorso del file SQLite da creare.

        Returns
        -------
        RisultatoMigrazione con conteggio record migrati e lista errori.
        """
        t0 = time.monotonic()
        target_db_path = resolve_sqlite_path(percorso_db)
        target_db = str(target_db_path)
        target_db_path.parent.mkdir(parents=True, exist_ok=True)

        precheck = self._anti_loss_precheck(target_db_path)
        if not precheck.get("ok", True):
            ms = int((time.monotonic() - t0) * 1000)
            return RisultatoMigrazione(
                riuscita=False,
                percorso_db=target_db,
                record_migrati={},
                errori=list(precheck.get("blockers") or []),
                avvisi=[
                    "Attivazione SQLite bloccata: il database esistente contiene record non presenti nei JSON correnti."
                ],
                audit={"precheck": precheck, "validation": {}, "staging": False},
                ms=ms,
            )

        work_db_path = target_db_path
        staging = target_db_path.exists()
        if staging:
            stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            work_db_path = target_db_path.with_name(
                f".{target_db_path.stem}.migrazione-{stamp}{target_db_path.suffix}"
            )
            for suffix in ("", "-wal", "-shm"):
                try:
                    work_db_path.with_name(work_db_path.name + suffix).unlink()
                except FileNotFoundError:
                    pass

        conn = sqlite3.connect(str(work_db_path))
        conn.row_factory = sqlite3.Row
        errori: List[str] = []
        avvisi: List[str] = []
        migrati: Dict[str, int] = {}
        id_clienti_migrati = set()
        id_fascicoli_migrati = set()
        id_appuntamenti_migrati = set()

        try:
            self._reset_sqlite_target(conn)
            conn.executescript(SCHEMA_SQL)
            for ddl in (
                "ALTER TABLE fascicoli ADD COLUMN profilo_deposito_json TEXT DEFAULT '{}'",
                "ALTER TABLE preventivi_records ADD COLUMN profilo_deposito_json TEXT NOT NULL DEFAULT '{}'",
                "ALTER TABLE conferimenti_records ADD COLUMN profilo_deposito_json TEXT NOT NULL DEFAULT '{}'",
                "ALTER TABLE preventivi_records ADD COLUMN classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]'",
                "ALTER TABLE conferimenti_records ADD COLUMN classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]'",
                "ALTER TABLE preventivi_records ADD COLUMN criterio_arrotondamento_orario TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE preventivi_records ADD COLUMN minuti_stimati INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE preventivi_records ADD COLUMN ore_fatturabili_calcolate REAL NOT NULL DEFAULT 0",
                "ALTER TABLE preventivi_records ADD COLUMN compenso_orario_base REAL NOT NULL DEFAULT 0",
                "ALTER TABLE preventivi_records ADD COLUMN massimale_ore REAL NOT NULL DEFAULT 0",
                "ALTER TABLE preventivi_records ADD COLUMN soglia_preapprovazione_ore REAL NOT NULL DEFAULT 0",
                "ALTER TABLE preventivi_records ADD COLUMN warning_compenso_orario_json TEXT NOT NULL DEFAULT '[]'",
                "ALTER TABLE conferimenti_records ADD COLUMN criterio_arrotondamento_orario TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE conferimenti_records ADD COLUMN massimale_ore REAL NOT NULL DEFAULT 0",
                "ALTER TABLE conferimenti_records ADD COLUMN soglia_preapprovazione_ore REAL NOT NULL DEFAULT 0",
                "ALTER TABLE conferimenti_records ADD COLUMN warning_compenso_orario_json TEXT NOT NULL DEFAULT '[]'",
            ):
                try:
                    conn.execute(ddl)
                except Exception:
                    pass

            # Meta
            conn.execute(
                "INSERT OR REPLACE INTO _meta VALUES(?,?)",
                ("migrazione_il", datetime.now().isoformat()),
            )
            for chiave, percorso in sorted(self.percorsi.items()):
                storage_kind = "sqlite" if chiave == "search_index" else "json"
                payload_json = "{}"
                if percorso.suffix.lower() == ".json":
                    raw_payload, payload_error = self._leggi_json_grezzo(chiave)
                    payload_json = self._modulo_payload_metadata(percorso, raw_payload, payload_error)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO moduli_dati
                    (nome, percorso, storage_kind, inizializzato_il, payload_json)
                    VALUES (?,?,?,?,?)
                    """,
                    (chiave, str(percorso), storage_kind, datetime.now().isoformat(), payload_json),
                )
            migrati["moduli_dati"] = len(self.percorsi)

            # ---- Clienti
            clienti_raw, err = self._leggi_json("clienti")
            if err:
                errori.append(f"clienti: {err}")
            else:
                c_count = 0
                for c in clienti_raw:
                    try:
                        rec = c.get("recapiti") or {}
                        conn.execute("""
                            INSERT OR REPLACE INTO clienti
                            (id, tipo, stato, cognome, nome, ragione_sociale,
                             codice_fiscale, partita_iva, email, telefono, note,
                             creato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            c.get("id"), c.get("tipo", "PERSONA_FISICA"),
                            c.get("stato", "ATTIVO"), c.get("cognome", ""),
                            c.get("nome", ""), c.get("ragione_sociale", ""),
                            c.get("codice_fiscale", ""), c.get("partita_iva", ""),
                            c.get("email", ""),
                            rec.get("telefono_principale") if isinstance(rec, dict) else c.get("telefono", ""),
                            c.get("note", ""), c.get("creato_il", ""),
                            json.dumps(c, ensure_ascii=False),
                        ))
                        c_count += 1
                        if c.get("id"):
                            id_clienti_migrati.add(c.get("id"))
                    except Exception as e:
                        errori.append(f"clienti/{c.get('id','?')}: {e}")
                migrati["clienti"] = c_count

            # ---- Fascicoli
            fasc_raw, err = self._leggi_json("fascicoli")
            if err:
                errori.append(f"fascicoli: {err}")
            else:
                f_count = 0
                for f in fasc_raw:
                    try:
                        id_cliente = f.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"fascicoli/{f.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        conn.execute("""
                            INSERT OR REPLACE INTO fascicoli
                            (id, numero, titolo, tipo, stato, id_cliente, nome_cliente,
                             tribunale, sezione, giudice, numero_rg, anno_rg,
                             controparte, avvocato_referente, avvocato_dominus,
                             data_apertura, data_chiusura, oggetto, note, creato_il,
                             attivita_json, documenti_json, scadenze_json,
                             profilo_deposito_json, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            f.get("id"), f.get("numero"), f.get("titolo"),
                            f.get("tipo", "CIVILE"), f.get("stato", "APERTO"),
                            id_cliente, f.get("nome_cliente", ""),
                            f.get("tribunale", ""), f.get("sezione", ""),
                            f.get("giudice", ""), f.get("numero_rg", ""),
                            f.get("anno_rg", ""), f.get("controparte", ""),
                            f.get("avvocato_referente", ""), f.get("avvocato_dominus", ""),
                            f.get("data_apertura", ""), f.get("data_chiusura", ""),
                            f.get("oggetto", ""), f.get("note", ""),
                            f.get("creato_il", ""),
                            json.dumps(f.get("attivita", []), ensure_ascii=False),
                            json.dumps(f.get("documenti", []), ensure_ascii=False),
                            json.dumps(f.get("scadenze", []), ensure_ascii=False),
                            json.dumps(f.get("profilo_deposito", {}), ensure_ascii=False),
                            json.dumps(f, ensure_ascii=False),
                        ))
                        f_count += 1
                        if f.get("id"):
                            id_fascicoli_migrati.add(f.get("id"))
                    except Exception as e:
                        errori.append(f"fascicoli/{f.get('id','?')}: {e}")
                migrati["fascicoli"] = f_count

            # ---- Soggetti
            soggetti_raw, err = self._leggi_json("soggetti")
            if err:
                errori.append(f"soggetti: {err}")
            else:
                sg_count = 0
                for soggetto in soggetti_raw:
                    try:
                        rec = soggetto.get("recapiti") if isinstance(soggetto.get("recapiti"), dict) else {}
                        id_cliente = soggetto.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"soggetti/{soggetto.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO soggetti
                            (id, tipo, nome, cognome, ragione_sociale, codice_fiscale,
                             partita_iva, qualifica, id_cliente, email, telefono,
                             creato_il, modificato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                soggetto.get("id"),
                                soggetto.get("tipo", "PERSONA_FISICA"),
                                soggetto.get("nome", ""),
                                soggetto.get("cognome", ""),
                                soggetto.get("ragione_sociale", ""),
                                soggetto.get("codice_fiscale", ""),
                                soggetto.get("partita_iva", ""),
                                soggetto.get("qualifica", ""),
                                id_cliente,
                                rec.get("email", "") if isinstance(rec, dict) else "",
                                (
                                    rec.get("telefono", "") or rec.get("cellulare", "")
                                    if isinstance(rec, dict)
                                    else ""
                                ),
                                soggetto.get("creato_il", ""),
                                soggetto.get("modificato_il", ""),
                                json.dumps(soggetto, ensure_ascii=False),
                            ),
                        )
                        sg_count += 1
                    except Exception as ex:
                        errori.append(f"soggetti/{soggetto.get('id','?')}: {ex}")
                migrati["soggetti"] = sg_count

            soggetti_parti_raw, err = self._leggi_json_grezzo("soggetti_parti")
            if err:
                errori.append(f"soggetti_parti: {err}")
            else:
                sp_count = 0
                for record_key, _index, _kind, parte in self._soggetti_parti_entries(soggetti_parti_raw):
                    try:
                        id_fascicolo = parte.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"soggetti_parti/{record_key}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO soggetti_parti
                            (id, id_fascicolo, id_soggetto, ruolo, note, data_aggiunta, dati_json)
                            VALUES (?,?,?,?,?,?,?)
                            """,
                            (
                                parte.get("id") or record_key,
                                id_fascicolo,
                                parte.get("id_soggetto") or None,
                                parte.get("ruolo", "ALTRO"),
                                parte.get("note", ""),
                                parte.get("data_aggiunta", ""),
                                json.dumps({**parte, "id_fascicolo": id_fascicolo or parte.get("id_fascicolo", "")}, ensure_ascii=False),
                            ),
                        )
                        sp_count += 1
                    except Exception as ex:
                        errori.append(f"soggetti_parti/{record_key}: {ex}")
                migrati["soggetti_parti"] = sp_count

            # ---- Appuntamenti
            app_raw, err = self._leggi_json("appuntamenti")
            if err:
                errori.append(f"appuntamenti: {err}")
            else:
                a_count = 0
                for a in app_raw:
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO appuntamenti
                            (id, tipo, stato, titolo, data_ora, durata_minuti, luogo,
                             descrizione, cliente, cf_cliente, procedimento, tribunale,
                             note, creato_il, modificato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            a.get("id"), a.get("tipo", "CONSULTAZIONE"),
                            a.get("stato", "PROGRAMMATO"), a.get("titolo", ""),
                            a.get("data_ora", ""), a.get("durata_minuti", 60),
                            a.get("luogo", ""), a.get("descrizione", ""),
                            a.get("cliente", ""), a.get("cf_cliente", ""),
                            a.get("procedimento", ""), a.get("tribunale", ""),
                            a.get("note", ""), a.get("creato_il", ""),
                            a.get("modificato_il", ""),
                            json.dumps(a, ensure_ascii=False),
                        ))
                        a_count += 1
                        if a.get("id"):
                            id_appuntamenti_migrati.add(a.get("id"))
                    except Exception as e:
                        errori.append(f"appuntamenti/{a.get('id','?')}: {e}")
                migrati["appuntamenti"] = a_count

            # ---- Scadenze
            scad_raw, err = self._leggi_json("scadenze")
            if err:
                errori.append(f"scadenze: {err}")
            else:
                s_count = 0
                for s in scad_raw:
                    try:
                        id_fascicolo = s.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"scadenze/{s.get('id','?')}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        id_appuntamento = s.get("id_appuntamento") or None
                        if id_appuntamento and id_appuntamento not in id_appuntamenti_migrati:
                            avvisi.append(
                                f"scadenze/{s.get('id','?')}: appuntamento {id_appuntamento!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_appuntamento = None
                        conn.execute("""
                            INSERT OR REPLACE INTO scadenze
                            (id, tipo, stato, titolo, data_scadenza, priorita,
                             perentorio, note, id_fascicolo, id_appuntamento, id_utente,
                             giorni_preavviso, avvisi_inviati, completata_il, creato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            s.get("id"), s.get("tipo", "ALTRO"),
                            s.get("stato", "APERTO"), s.get("titolo", ""),
                            s.get("data_scadenza", ""), s.get("priorita", "MEDIA"),
                            1 if s.get("perentorio") else 0,
                            s.get("note", ""), id_fascicolo,
                            id_appuntamento,
                            s.get("id_utente_responsabile", ""),
                            json.dumps(s.get("giorni_preavviso", []), ensure_ascii=False),
                            json.dumps(s.get("avvisi_inviati", []), ensure_ascii=False),
                            s.get("completata_il", ""), s.get("creato_il", ""),
                            json.dumps(s, ensure_ascii=False),
                        ))
                        s_count += 1
                    except Exception as e:
                        errori.append(f"scadenze/{s.get('id','?')}: {e}")
                migrati["scadenze"] = s_count

            # ---- Timesheet
            timesheet_raw, err = self._leggi_json("timesheet")
            if err:
                errori.append(f"timesheet: {err}")
            else:
                t_count = 0
                for voce in timesheet_raw:
                    try:
                        id_cliente = voce.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"timesheet/{voce.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        id_fascicolo = voce.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"timesheet/{voce.get('id','?')}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO timesheet_entries
                            (id, id_fascicolo, id_cliente, id_utente, username, data_attivita,
                             descrizione, minuti, valore_unitario, fatturabile, stato, origine,
                             creato_il, modificato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                voce.get("id"),
                                id_fascicolo,
                                id_cliente,
                                voce.get("id_utente") or None,
                                voce.get("username", ""),
                                voce.get("data_attivita", ""),
                                voce.get("descrizione", ""),
                                int(voce.get("minuti", 0) or 0),
                                float(voce.get("valore_unitario", 0.0) or 0.0),
                                1 if voce.get("fatturabile", True) else 0,
                                voce.get("stato", "APERTO"),
                                voce.get("origine", ""),
                                voce.get("creato_il", ""),
                                voce.get("modificato_il", ""),
                                json.dumps(voce, ensure_ascii=False),
                            ),
                        )
                        t_count += 1
                    except Exception as ex:
                        errori.append(f"timesheet/{voce.get('id','?')}: {ex}")
                migrati["timesheet"] = t_count

            # ---- Timer attivita top bar
            time_tracking_raw, err = self._leggi_json("time_tracking")
            if err:
                errori.append(f"time_tracking: {err}")
            else:
                tt_count = 0
                for timer in time_tracking_raw:
                    try:
                        id_cliente = timer.get("client_id") or timer.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"time_tracking/{timer.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        id_fascicolo = timer.get("case_id") or timer.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"time_tracking/{timer.get('id','?')}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO time_tracking_timers
                            (id, user_id, username, id_fascicolo, id_cliente, activity_type,
                             description, started_at, paused_at, ended_at, elapsed_seconds,
                             status, timesheet_entry_id, created_at, updated_at, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                timer.get("id"),
                                timer.get("user_id") or None,
                                timer.get("username", ""),
                                id_fascicolo,
                                id_cliente,
                                timer.get("activity_type", "other"),
                                timer.get("description", ""),
                                timer.get("started_at", ""),
                                timer.get("paused_at") or None,
                                timer.get("ended_at") or None,
                                int(timer.get("elapsed_seconds", 0) or 0),
                                timer.get("status", "running"),
                                timer.get("timesheet_entry_id") or None,
                                timer.get("created_at", ""),
                                timer.get("updated_at", ""),
                                json.dumps(timer, ensure_ascii=False),
                            ),
                        )
                        tt_count += 1
                    except Exception as ex:
                        errori.append(f"time_tracking/{timer.get('id','?')}: {ex}")
                migrati["time_tracking"] = tt_count

            # ---- Preventivi
            preventivi_raw, err = self._leggi_json("preventivi")
            if err:
                errori.append(f"preventivi: {err}")
            else:
                pr_count = 0
                for preventivo in preventivi_raw:
                    try:
                        id_cliente = preventivo.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"preventivi/{preventivo.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        id_fascicolo = preventivo.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"preventivi/{preventivo.get('id','?')}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        totale = float(preventivo.get("totale", 0.0) or 0.0)
                        if not totale:
                            totale = round(float(preventivo.get("base_iva", 0.0) or 0.0) + float(preventivo.get("iva", 0.0) or 0.0) + float(preventivo.get("anticipazioni_art15", 0.0) or 0.0), 2)
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO preventivi_records
                            (preventivo_id, numero, id_cliente, id_fascicolo, data_emissione, data_scadenza,
                             oggetto, stato, workflow_channel, tipo_compenso, tipo_procedimento,
                             area_pratica, id_pratica, procedura_operativa_codice, procedura_operativa_nome,
                             canale_operativo, registro_operativo, classificazioni_tassonomiche_json,
                             criterio_arrotondamento_orario, minuti_stimati, ore_fatturabili_calcolate,
                             compenso_orario_base, massimale_ore, soglia_preapprovazione_ore,
                             warning_compenso_orario_json, totale, accettato_il,
                             id_preventivo_precedente, token_portale, creato_il,
                             profilo_deposito_json, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                preventivo.get("id"),
                                preventivo.get("numero", ""),
                                id_cliente,
                                id_fascicolo,
                                preventivo.get("data_emissione", ""),
                                preventivo.get("data_scadenza", ""),
                                preventivo.get("oggetto", ""),
                                preventivo.get("stato", "BOZZA"),
                                preventivo.get("workflow_channel", "STUDIO"),
                                preventivo.get("tipo_compenso", ""),
                                preventivo.get("tipo_procedimento", ""),
                                preventivo.get("area_pratica", ""),
                                preventivo.get("id_pratica", ""),
                                preventivo.get("procedura_operativa_codice", ""),
                                preventivo.get("procedura_operativa_nome", ""),
                                preventivo.get("canale_operativo", ""),
                                preventivo.get("registro_operativo", ""),
                                json.dumps(
                                    preventivo.get("classificazioni_tassonomiche") or [],
                                    ensure_ascii=False,
                                ),
                                preventivo.get("criterio_arrotondamento_orario", ""),
                                int(preventivo.get("minuti_stimati", 0) or 0),
                                float(preventivo.get("ore_fatturabili_calcolate", 0.0) or 0.0),
                                float(preventivo.get("compenso_orario_base", 0.0) or 0.0),
                                float(preventivo.get("massimale_ore", 0.0) or 0.0),
                                float(preventivo.get("soglia_preapprovazione_ore", 0.0) or 0.0),
                                json.dumps(preventivo.get("warning_compenso_orario") or [], ensure_ascii=False),
                                totale,
                                preventivo.get("accettato_il", ""),
                                preventivo.get("id_preventivo_precedente", ""),
                                preventivo.get("token_portale", ""),
                                preventivo.get("creato_il", ""),
                                json.dumps(preventivo.get("profilo_deposito", {}), ensure_ascii=False),
                                json.dumps(preventivo, ensure_ascii=False),
                            ),
                        )
                        pr_count += 1
                    except Exception as ex:
                        errori.append(f"preventivi/{preventivo.get('id','?')}: {ex}")
                migrati["preventivi"] = pr_count

            conferimenti_raw, err = self._leggi_json("conferimenti")
            if err:
                errori.append(f"conferimenti: {err}")
            else:
                conf_count = 0
                for conferimento in conferimenti_raw:
                    try:
                        id_cliente = conferimento.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"conferimenti/{conferimento.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        id_fascicolo = conferimento.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"conferimenti/{conferimento.get('id','?')}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO conferimenti_records
                            (conferimento_id, numero, id_preventivo, id_cliente, id_fascicolo,
                             data_incarico, oggetto, stato, workflow_channel, tipo_compenso,
                             tipo_procedimento, area_pratica, id_pratica, procedura_operativa_codice,
                             procedura_operativa_nome, canale_operativo, registro_operativo,
                             classificazioni_tassonomiche_json,
                             criterio_arrotondamento_orario, massimale_ore, soglia_preapprovazione_ore,
                             warning_compenso_orario_json,
                             compenso_pattuito, firma_cliente_eseguita, fascicolo_aperto_il,
                             profilo_deposito_json, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                conferimento.get("id"),
                                conferimento.get("numero", ""),
                                conferimento.get("id_preventivo", ""),
                                id_cliente,
                                id_fascicolo,
                                conferimento.get("data_incarico", ""),
                                conferimento.get("oggetto", ""),
                                conferimento.get("stato", "ATTIVO"),
                                conferimento.get("workflow_channel", "STUDIO"),
                                conferimento.get("tipo_compenso", ""),
                                conferimento.get("tipo_procedimento", ""),
                                conferimento.get("area_pratica", ""),
                                conferimento.get("id_pratica", ""),
                                conferimento.get("procedura_operativa_codice", ""),
                                conferimento.get("procedura_operativa_nome", ""),
                                conferimento.get("canale_operativo", ""),
                                conferimento.get("registro_operativo", ""),
                                json.dumps(
                                    conferimento.get("classificazioni_tassonomiche") or [],
                                    ensure_ascii=False,
                                ),
                                conferimento.get("criterio_arrotondamento_orario", ""),
                                float(conferimento.get("massimale_ore", 0.0) or 0.0),
                                float(conferimento.get("soglia_preapprovazione_ore", 0.0) or 0.0),
                                json.dumps(conferimento.get("warning_compenso_orario") or [], ensure_ascii=False),
                                float(conferimento.get("compenso_pattuito", 0.0) or 0.0),
                                1 if conferimento.get("firma_cliente_eseguita") else 0,
                                conferimento.get("fascicolo_aperto_il", ""),
                                json.dumps(conferimento.get("profilo_deposito", {}), ensure_ascii=False),
                                json.dumps(conferimento, ensure_ascii=False),
                            ),
                        )
                        conf_count += 1
                    except Exception as ex:
                        errori.append(f"conferimenti/{conferimento.get('id','?')}: {ex}")
                migrati["conferimenti"] = conf_count

            # ---- Parcelle
            parcelle_raw, err = self._leggi_json("fatturazione")
            if err:
                errori.append(f"fatturazione: {err}")
            else:
                parcelle_count = 0
                for parcella in parcelle_raw:
                    try:
                        id_cliente = parcella.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"fatturazione/{parcella.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        id_fascicolo = parcella.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"fatturazione/{parcella.get('id','?')}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO parcelle
                            (id, numero, id_cliente, id_fascicolo, data_emissione, data_scadenza,
                             stato, totale, imponibile, origine, id_preventivo, id_pratica,
                             area_pratica, procedura_operativa_codice, procedura_operativa_nome,
                             canale_operativo, registro_operativo, tipo_compenso, tipo_procedimento,
                             valore_controversia, complessita, data_pagamento, metodo_pagamento,
                             creato_da, creato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                parcella.get("id"),
                                parcella.get("numero", ""),
                                id_cliente,
                                id_fascicolo,
                                parcella.get("data_emissione", ""),
                                parcella.get("data_scadenza", ""),
                                parcella.get("stato", "BOZZA"),
                                float(parcella.get("totale", 0.0) or 0.0),
                                float(parcella.get("imponibile", 0.0) or 0.0),
                                parcella.get("origine", ""),
                                parcella.get("id_preventivo", ""),
                                parcella.get("id_pratica", ""),
                                parcella.get("area_pratica", ""),
                                parcella.get("procedura_operativa_codice", ""),
                                parcella.get("procedura_operativa_nome", ""),
                                parcella.get("canale_operativo", ""),
                                parcella.get("registro_operativo", ""),
                                parcella.get("tipo_compenso", ""),
                                parcella.get("tipo_procedimento", ""),
                                float(parcella.get("valore_controversia", 0.0) or 0.0),
                                parcella.get("complessita", ""),
                                parcella.get("data_pagamento", ""),
                                parcella.get("metodo_pagamento", ""),
                                parcella.get("creato_da", ""),
                                parcella.get("creato_il", ""),
                                json.dumps(parcella, ensure_ascii=False),
                            ),
                        )
                        parcelle_count += 1
                    except Exception as ex:
                        errori.append(f"fatturazione/{parcella.get('id','?')}: {ex}")
                migrati["fatturazione"] = parcelle_count

            # ---- Pagamenti
            pagamenti_cfg_raw, err = self._leggi_json_grezzo("pagamenti_config")
            if err:
                errori.append(f"pagamenti_config: {err}")
            elif pagamenti_cfg_raw:
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO payment_config
                        (config_id, provider_count, updated_at, dati_json)
                        VALUES (?,?,?,?)
                        """,
                        (
                            "default",
                            len(
                                [
                                    key for key, value in (pagamenti_cfg_raw or {}).items()
                                    if isinstance(value, dict) and value.get("abilitato")
                                ]
                            ),
                            datetime.now().isoformat(),
                            json.dumps(pagamenti_cfg_raw, ensure_ascii=False),
                        ),
                    )
                    migrati["pagamenti_config"] = 1
                except Exception as ex:
                    errori.append(f"pagamenti_config/default: {ex}")

            impostazioni_path = self.percorsi.get("impostazioni")
            if impostazioni_path and impostazioni_path.exists():
                try:
                    from pct.config_studio import GestioneConfigStudio
                    from pct.impostazioni_config_repository import settings_config_rows_from_config

                    cfg_studio = GestioneConfigStudio(config_path=str(impostazioni_path)).config
                    rows = settings_config_rows_from_config(cfg_studio)
                    for row in rows:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO settings_config
                            (section, updated_at, source, secret_fields_json, dati_json)
                            VALUES (?,?,?,?,?)
                            """,
                            (
                                row["section"],
                                row["updated_at"],
                                row["source"],
                                json.dumps(row.get("secret_fields") or [], ensure_ascii=False),
                                json.dumps(row.get("dati") or {}, ensure_ascii=False),
                            ),
                        )
                    migrati["impostazioni"] = len(rows)
                except Exception as ex:
                    errori.append(f"impostazioni/settings_config: {ex}")

            pagamenti_link_raw, err = self._leggi_json("pagamenti_links")
            if err:
                errori.append(f"pagamenti_links: {err}")
            else:
                pay_count = 0
                for link in pagamenti_link_raw:
                    try:
                        id_cliente = link.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"pagamenti_links/{link.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO payment_links
                            (id, token, id_parcella, id_cliente, importo, valuta, stato,
                             provider_usato, provider_tx_id, creato_il, scade_il, pagato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                link.get("id"),
                                link.get("token", ""),
                                link.get("id_parcella", ""),
                                id_cliente,
                                float(link.get("importo", 0.0) or 0.0),
                                link.get("valuta", "EUR"),
                                link.get("stato", "ATTESO"),
                                link.get("provider_usato", ""),
                                link.get("provider_tx_id", ""),
                                link.get("creato_il", ""),
                                link.get("scade_il", ""),
                                link.get("pagato_il", ""),
                                json.dumps(link, ensure_ascii=False),
                            ),
                        )
                        pay_count += 1
                    except Exception as ex:
                        errori.append(f"pagamenti_links/{link.get('id','?')}: {ex}")
                migrati["pagamenti_links"] = pay_count

            # ---- Messaggi
            msg_raw, err = self._leggi_json("messaggi")
            if err:
                errori.append(f"messaggi: {err}")
            else:
                m_count = 0
                for m in msg_raw:
                    try:
                        id_cliente = m.get("id_cliente") or None
                        if id_cliente and id_cliente not in id_clienti_migrati:
                            avvisi.append(
                                f"messaggi/{m.get('id','?')}: cliente {id_cliente!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_cliente = None
                        id_fascicolo = m.get("id_fascicolo") or None
                        if id_fascicolo and id_fascicolo not in id_fascicoli_migrati:
                            avvisi.append(
                                f"messaggi/{m.get('id','?')}: fascicolo {id_fascicolo!r} non trovato, riferimento scollegato in migrazione"
                            )
                            id_fascicolo = None
                        conn.execute("""
                            INSERT OR REPLACE INTO messaggi
                            (id, canale, stato, oggetto, corpo,
                             email_destinatario, telefono_destinatario,
                             id_cliente, id_fascicolo, tipo_automazione,
                             inviato_il, errore_invio, creato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            m.get("id"), m.get("canale", "EMAIL"),
                            m.get("stato", "BOZZA"), m.get("oggetto", ""),
                            m.get("corpo", ""), m.get("email_destinatario", ""),
                            m.get("telefono_destinatario", ""),
                            id_cliente, id_fascicolo,
                            m.get("tipo_automazione", ""), m.get("inviato_il", ""),
                            m.get("errore_invio", ""), m.get("creato_il", ""),
                            json.dumps(m, ensure_ascii=False),
                        ))
                        m_count += 1
                    except Exception as e:
                        errori.append(f"messaggi/{m.get('id','?')}: {e}")
                migrati["messaggi"] = m_count

            # ---- Utenti
            ut_raw, err = self._leggi_json("utenti")
            if err:
                errori.append(f"utenti: {err}")
            else:
                u_count = 0
                for u in ut_raw:
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO utenti
                            (id, username, email, nome_completo, ruolo,
                             password_hash, attivo, must_change_password,
                             permessi_extra, permessi_negati, creato_il, ultimo_accesso, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            u.get("id"), u.get("username", ""),
                            u.get("email", ""), u.get("nome_completo", ""),
                            u.get("ruolo", "SEGRETERIA"), u.get("password_hash", ""),
                            1 if u.get("attivo", True) else 0,
                            1 if u.get("must_change_password", False) else 0,
                            json.dumps(u.get("permessi_extra", []), ensure_ascii=False),
                            json.dumps(u.get("permessi_negati", []), ensure_ascii=False),
                            u.get("creato_il", ""), u.get("ultimo_accesso", ""),
                            json.dumps(u, ensure_ascii=False),
                        ))
                        u_count += 1
                    except Exception as e:
                        errori.append(f"utenti/{u.get('id','?')}: {e}")
                migrati["utenti"] = u_count

            # ---- Audit log
            audit_raw, err = self._leggi_json("audit")
            if err:
                errori.append(f"audit: {err}")
            else:
                al_count = 0
                for e in audit_raw:
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO audit_log
                            (id, timestamp, id_utente, username, azione,
                             risorsa_tipo, risorsa_id, dettagli, ip, esito)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (
                            e.get("id"), e.get("timestamp", ""),
                            e.get("id_utente", ""), e.get("username", ""),
                            e.get("azione", ""), e.get("risorsa_tipo", ""),
                            e.get("risorsa_id", ""), e.get("dettagli", ""),
                            e.get("ip", ""), e.get("esito", "OK"),
                        ))
                        al_count += 1
                    except Exception as ex:
                        errori.append(f"audit/{e.get('id','?')}: {ex}")
                migrati["audit"] = al_count

            # ---- Privacy
            privacy_raw, err = self._leggi_json("privacy")
            if err:
                errori.append(f"privacy: {err}")
            else:
                p_count = 0
                for trattamento in privacy_raw:
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO privacy_trattamenti
                            (id, nome, finalita, categoria_dati, base_giuridica,
                             soggetti_interessati, destinatari, trasferimento_extra_ue,
                             paese_destinazione, termine_conservazione,
                             misure_sicurezza, responsabile, attivo, note,
                             creato_il, modificato_il, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                trattamento.get("id"),
                                trattamento.get("nome", ""),
                                trattamento.get("finalita", ""),
                                trattamento.get("categoria_dati", ""),
                                trattamento.get("base_giuridica", ""),
                                trattamento.get("soggetti_interessati", trattamento.get("soggetti", "")),
                                trattamento.get("destinatari", ""),
                                1 if trattamento.get("trasferimento_extra_ue") else 0,
                                trattamento.get("paese_destinazione", ""),
                                trattamento.get("termine_conservazione", ""),
                                trattamento.get("misure_sicurezza", ""),
                                trattamento.get("responsabile", ""),
                                1 if trattamento.get("attivo", True) else 0,
                                trattamento.get("note", ""),
                                trattamento.get("creato_il", ""),
                                trattamento.get("modificato_il", ""),
                                json.dumps(trattamento, ensure_ascii=False),
                            ),
                        )
                        p_count += 1
                    except Exception as ex:
                        errori.append(f"privacy/{trattamento.get('id','?')}: {ex}")
                migrati["privacy"] = p_count

            # ---- Notifiche
            notifiche_raw, err = self._leggi_json("notifiche")
            if err:
                errori.append(f"notifiche: {err}")
            else:
                n_count = 0
                for entry in notifiche_raw:
                    try:
                        esito = entry.get("esito")
                        payload = {k: v for k, v in entry.items() if k != "esito"}
                        conn.execute(
                            """
                            INSERT INTO notifiche_log
                            (timestamp, tipo, cliente, numero, utente, esito_json, payload_json)
                            VALUES (?,?,?,?,?,?,?)
                            """,
                            (
                                entry.get("ts", entry.get("timestamp", "")),
                                entry.get("tipo", ""),
                                entry.get("cliente", ""),
                                entry.get("numero", ""),
                                entry.get("utente", ""),
                                json.dumps(esito or {}, ensure_ascii=False),
                                json.dumps(payload, ensure_ascii=False),
                            ),
                        )
                        n_count += 1
                    except Exception as ex:
                        errori.append(f"notifiche/{entry.get('ts','?')}: {ex}")
                migrati["notifiche"] = n_count

            # ---- Backup
            backup_raw, err = self._leggi_json("backup")
            if err:
                errori.append(f"backup: {err}")
            else:
                b_count = 0
                for record in backup_raw:
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO backup_records
                            (id, timestamp, tipo, stato, percorso_file, hash_file,
                             dimensione_bytes, num_file, componenti_json, cifrato,
                             nota, errore, backup_base_id, dati_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                record.get("id"),
                                record.get("timestamp", ""),
                                record.get("tipo", "COMPLETO"),
                                record.get("stato", "OK"),
                                record.get("percorso_file", ""),
                                record.get("hash_file", ""),
                                int(record.get("dimensione_bytes", 0) or 0),
                                int(record.get("num_file", 0) or 0),
                                json.dumps(record.get("componenti", []), ensure_ascii=False),
                                1 if record.get("cifrato") else 0,
                                record.get("nota", ""),
                                record.get("errore", ""),
                                record.get("backup_base_id", ""),
                                json.dumps(record, ensure_ascii=False),
                            ),
                        )
                        b_count += 1
                    except Exception as ex:
                        errori.append(f"backup/{record.get('id','?')}: {ex}")
                migrati["backup"] = b_count

            backup_path = self.percorsi.get("backup")
            if backup_path:
                backup_cfg = backup_path.with_name("config.json")
                if backup_cfg.exists():
                    try:
                        cfg_raw = json.loads(backup_cfg.read_text("utf-8"))
                        cfg_count = 0
                        for chiave, valore in cfg_raw.items():
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO backup_config
                                (chiave, valore, payload_json)
                                VALUES (?,?,?)
                                """,
                                (
                                    str(chiave),
                                    json.dumps(valore, ensure_ascii=False)
                                    if isinstance(valore, (dict, list, bool))
                                    else "" if valore is None else str(valore),
                                    json.dumps({"chiave": chiave, "valore": valore}, ensure_ascii=False),
                                ),
                            )
                            cfg_count += 1
                        migrati["backup_config"] = cfg_count
                    except Exception as ex:
                        errori.append(f"backup_config: {ex}")

            # ---- Moduli JSON estesi
            self._migra_moduli_json_estesi(conn, migrati, errori)

            # ---- Search index
            search_path = self.percorsi.get("search_index")
            if search_path and search_path.exists():
                try:
                    src = sqlite3.connect(str(search_path))
                    src.row_factory = sqlite3.Row

                    doc_count = 0
                    for row in src.execute(
                        "SELECT tipo, entity_id, titolo, corpo, meta FROM documenti"
                    ).fetchall():
                        conn.execute(
                            """
                            INSERT INTO search_documenti(tipo, entity_id, titolo, corpo, meta)
                            VALUES (?,?,?,?,?)
                            """,
                            (
                                row["tipo"],
                                row["entity_id"],
                                row["titolo"],
                                row["corpo"],
                                row["meta"],
                            ),
                        )
                        doc_count += 1
                    migrati["search_index"] = doc_count

                    meta_count = 0
                    for row in src.execute(
                        "SELECT chiave, valore FROM meta_indice"
                    ).fetchall():
                        conn.execute(
                            "INSERT OR REPLACE INTO search_meta_indice(chiave, valore) VALUES (?,?)",
                            (row["chiave"], row["valore"]),
                        )
                        meta_count += 1
                    migrati["search_meta_indice"] = meta_count

                    ocr_count = 0
                    for row in src.execute(
                        "SELECT hash_sha256, testo, elaborato_il FROM ocr_cache"
                    ).fetchall():
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO search_ocr_cache(hash_sha256, testo, elaborato_il)
                            VALUES (?,?,?)
                            """,
                            (row["hash_sha256"], row["testo"], row["elaborato_il"]),
                        )
                        ocr_count += 1
                    migrati["search_ocr_cache"] = ocr_count
                    src.close()
                except Exception as ex:
                    errori.append(f"search_index: {ex}")

            conn.execute("INSERT OR REPLACE INTO _meta VALUES(?,?)",
                         ("totale_record", str(sum(migrati.values()))))

            ensure_catalogo_strutturale_schema(conn)
            catalogo_counts = seed_catalogo_strutturale(conn)
            conn.execute(
                "INSERT OR REPLACE INTO _meta VALUES(?,?)",
                ("catalogo_strutturale_json", json.dumps(catalogo_counts, ensure_ascii=False)),
            )
            avvisi.append(
                "Base strutturale seedata automaticamente con moduli procedurali e forensi versionati, senza associazioni automatiche ai cataloghi legacy."
            )
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            conn.commit()

        except Exception as e:
            errori.append(f"Errore critico migrazione: {e}")
            conn.rollback()
        finally:
            conn.close()

        validation: Dict[str, Any] = {}
        if not errori:
            validation = self._validate_sqlite_migration(work_db_path)
            if not validation.get("ok", False):
                errori.extend(str(item) for item in validation.get("errors") or [])
            avvisi.extend(str(item) for item in validation.get("warnings") or [])

        if not errori and work_db_path != target_db_path:
            try:
                self._install_sqlite_database(work_db_path, target_db_path)
            except Exception as exc:
                errori.append(f"Installazione SQLite sicura non riuscita: {exc}")

        if not errori:
            try:
                from pct.storage import StudioDB

                try:
                    StudioDB.invalidate(target_db)
                except AttributeError:
                    pass
                StudioDB.get(target_db).ensure_schema()
            except Exception as exc:
                errori.append(f"Riallineamento schema SQLite post-migrazione non riuscito: {exc}")

        if work_db_path != target_db_path:
            for suffix in ("", "-wal", "-shm"):
                try:
                    work_db_path.with_name(work_db_path.name + suffix).unlink()
                except FileNotFoundError:
                    pass

        ms = int((time.monotonic() - t0) * 1000)
        return RisultatoMigrazione(
            riuscita=len(errori) == 0,
            percorso_db=target_db,
            record_migrati=migrati,
            errori=errori,
            avvisi=avvisi,
            audit={"precheck": precheck, "validation": validation, "staging": staging},
            ms=ms,
        )

    # ---------------------------------------------------------------- Export ZIP

    def esporta_tutto(self, output_dir: str) -> str:
        """
        Esporta tutti i file dati in uno ZIP con timestamp.

        Returns
        -------
        Percorso del file ZIP creato.
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        zip_path = str(Path(output_dir) / f"export_completo_{ts}.zip")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for chiave, p in self.percorsi.items():
                if p.exists():
                    arcname = f"dati/{chiave}/{p.name}"
                    zf.write(str(p), arcname)

            # Aggiungi manifest
            stats = self.statistiche()
            manifest = json.dumps(stats, indent=2, ensure_ascii=False)
            zf.writestr("manifest.json", manifest)

        return zip_path

    # ---------------------------------------------------------------- Analisi accessi

    def analisi_uso(self) -> Dict[str, Any]:
        """
        Analizza il log di audit per estrarre statistiche di utilizzo:
        azioni più frequenti, utenti più attivi, ore di punta, errori.
        """
        audit_raw, err = self._leggi_json("audit")
        if err or not audit_raw:
            return {"disponibile": False, "errore": err or "Audit log vuoto"}

        from collections import Counter

        azioni = Counter(e.get("azione", "") for e in audit_raw)
        utenti = Counter(e.get("username", "anonimo") for e in audit_raw if e.get("username"))
        esiti = Counter(e.get("esito", "OK") for e in audit_raw)
        ore = Counter()
        giorni = Counter()
        errori = []

        for e in audit_raw:
            ts = e.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    ore[dt.hour] += 1
                    giorni[dt.strftime("%Y-%m-%d")] += 1
                except (ValueError, TypeError):
                    pass
            if e.get("esito") == "ERRORE":
                errori.append({
                    "timestamp": e.get("timestamp", ""),
                    "azione": e.get("azione", ""),
                    "username": e.get("username", ""),
                    "dettagli": e.get("dettagli", ""),
                })

        ora_punta = max(ore, key=ore.get) if ore else None
        giorno_piu_attivo = max(giorni, key=giorni.get) if giorni else None

        return {
            "disponibile": True,
            "totale_eventi": len(audit_raw),
            "azioni_frequenti": azioni.most_common(10),
            "utenti_attivi": utenti.most_common(10),
            "esiti": dict(esiti),
            "ora_punta": ora_punta,
            "accessi_per_ora": dict(sorted(ore.items())),
            "giorno_piu_attivo": giorno_piu_attivo,
            "errori_recenti": errori[-10:],
            "tasso_errori": round(
                esiti.get("ERRORE", 0) / len(audit_raw) * 100, 1
            ) if audit_raw else 0,
        }

    # ---------------------------------------------------------------- Statistiche SQL

    def statistiche_sqlite(self, percorso_db: str) -> Optional[Dict[str, Any]]:
        """Statistiche dettagliate su un database SQLite migrato."""
        p = Path(percorso_db)
        if not p.exists():
            return None
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(str(p))
            tables = [r[0] for r in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE '\\_%' ESCAPE '\\'
                  AND name NOT LIKE 'sqlite_%'
                  AND name NOT LIKE 'search_documenti_%'
                """
            ).fetchall()]
            stats = {}
            table_errors: Dict[str, str] = {}
            for t in tables:
                quoted = '"' + str(t).replace('"', '""') + '"'
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()
                    stats[t] = row[0] if row else 0
                except Exception as exc:
                    stats[t] = 0
                    table_errors[str(t)] = str(exc)

            # Page info
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            free_pages = conn.execute("PRAGMA freelist_count").fetchone()[0]

            size = p.stat().st_size
            payload = {
                "tabelle": stats,
                "dimensione": _fmt_bytes(size),
                "dimensione_bytes": size,
                "pagine_totali": page_count,
                "pagine_libere": free_pages,
                "frammentazione_pct": round(free_pages / page_count * 100, 1) if page_count else 0,
                "page_size": page_size,
                "esiste": True,
            }
            if table_errors:
                payload["errore"] = (
                    "Snapshot presente con avvisi: alcune tabelle tecniche non sono "
                    "conteggiabili e sono state escluse dal totale visibile."
                )
                payload["errori_tabelle"] = table_errors
            return payload
        except Exception as e:
            return {"esiste": False, "errore": str(e)}
        finally:
            if conn is not None:
                conn.close()


# ================================================================ Utility

def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.1f} GB"


def _bootstrap_json_file(path: str, payload: Any) -> bool:
    target = Path(path)
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return True


def bootstrap_moduli_monitorati(moduli: Dict[str, Optional[str]]) -> Dict[str, str]:
    """
    Inizializza automaticamente i file JSON mancanti dei moduli monitorati.

    Non sovrascrive mai file esistenti e usa, quando utile, la struttura minima
    corretta per evitare stati "Non trovato" dovuti solo a bootstrap non ancora
    eseguiti. Per backup e search crea anche le strutture tecniche minime
    richieste in modalità operativa o SQL.
    """
    normalized = {
        str(nome or "").strip().lower(): str(path).strip()
        for nome, path in (moduli or {}).items()
        if path
    }
    created: Dict[str, str] = {}

    def _mark(nome: str, path: str, changed: bool) -> None:
        if changed:
            created[nome] = path

    simple_payloads: Dict[str, Any] = {
        "appuntamenti": {},
        "audit": [],
        "calendar_sync": {"profiles": []},
        "clienti": {},          # anagrafica.json — mancava dal bootstrap
        "condivisioni": {"cartelle": {}, "fascicoli": {}, "link": {}},
        "fascicoli": {},
        "conferimenti": {},
        "messaggi": {},
        "note_faldone": {},
        "notifiche": [],
        "email_casella": {},
        "email_ordinaria": [],
        "fatturazione": {},
        "pagamenti_config": {},
        "pagamenti_links": {},
        "portale": {},
        "preventivi": {},
        "scadenze": {},          # scadenze.json — mancava dal bootstrap
        "soggetti": [],
        "soggetti_parti": {},
        "template_atti": {},
        "timesheet": {},
        "time_tracking": {},
        "utenti": {},
        "validation_runs": {"runs": []},
        "redaction_assistant": [],
        "workspace_intelligence": {},
        "giurisprudenza": {"storage_version": 2, "judgments": [], "ingestion_runs": []},
        "wizard_pro": [],
    }

    for nome, payload in simple_payloads.items():
        path = normalized.get(nome)
        if not path:
            continue
        if Path(path).suffix.lower() != ".json":
            continue
        _mark(nome, path, _bootstrap_json_file(path, payload))

    preventivi_path = normalized.get("preventivi")
    if preventivi_path:
        conf_path = str(Path(preventivi_path).with_name("conferimenti.json"))
        _bootstrap_json_file(conf_path, {})

    template_prefs_path = normalized.get("template_atti_prefs")
    if template_prefs_path and not Path(template_prefs_path).exists():
        from pct.template_atti import GestionePreferenzeTemplateAtti

        GestionePreferenzeTemplateAtti(template_prefs_path).salva()
        created["template_atti_prefs"] = template_prefs_path

    privacy_path = normalized.get("privacy")
    if privacy_path and not Path(privacy_path).exists():
        from pct.privacy import GestioneTrattamenti

        GestioneTrattamenti(privacy_path)
        created["privacy"] = privacy_path

    backup_path = normalized.get("backup")
    if backup_path:
        backup_target = Path(backup_path)
        changed = _bootstrap_json_file(str(backup_target), [])
        if changed:
            created["backup"] = str(backup_target)

        backup_cfg = backup_target.with_name("config.json")
        if not backup_cfg.exists():
            from pct.backup import ConfigBackup

            cfg = ConfigBackup(directory_backup=str(backup_target.parent))
            backup_cfg.write_text(
                json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            created["backup_config"] = str(backup_cfg)

    search_path = normalized.get("search_index")
    if search_path and not Path(search_path).exists():
        from pct.search_index import IndiceRicerca

        indice = IndiceRicerca(search_path)
        indice._conn.close()
        created["search_index"] = search_path

    normative_path = normalized.get("normative_tables")
    if normative_path and not Path(normative_path).exists():
        from pct.normative_tables import GestioneTabelleNormative

        GestioneTabelleNormative(normative_path)
        created["normative_tables"] = normative_path

    legal_path = normalized.get("legal_intelligence")
    if legal_path and not Path(legal_path).exists():
        from pct.legal_intelligence import GestioneLegalIntelligence

        gestore = GestioneLegalIntelligence(
            db_path=legal_path,
            normative_db_path=normalized.get("normative_tables"),
        )
        gestore._save()
        created["legal_intelligence"] = legal_path

    return created
