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

import csv
import io
import json
import os
import shutil
import sqlite3
import time
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
class RisultatoMigrazione:
    riuscita: bool
    percorso_db: str
    record_migrati: Dict[str, int] = field(default_factory=dict)
    errori: List[str] = field(default_factory=list)
    avvisi: List[str] = field(default_factory=list)
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
    scadenze_json      TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_fascicoli_tipo     ON fascicoli(tipo);
CREATE INDEX IF NOT EXISTS idx_fascicoli_stato    ON fascicoli(stato);
CREATE INDEX IF NOT EXISTS idx_fascicoli_cliente  ON fascicoli(id_cliente);
CREATE INDEX IF NOT EXISTS idx_fascicoli_numero   ON fascicoli(numero);
CREATE INDEX IF NOT EXISTS idx_fascicoli_avv      ON fascicoli(avvocato_referente);

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
    modificato_il   TEXT
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
    creato_il        TEXT
);
CREATE INDEX IF NOT EXISTS idx_scad_stato      ON scadenze(stato);
CREATE INDEX IF NOT EXISTS idx_scad_data       ON scadenze(data_scadenza);
CREATE INDEX IF NOT EXISTS idx_scad_priorita   ON scadenze(priorita);
CREATE INDEX IF NOT EXISTS idx_scad_fascicolo  ON scadenze(id_fascicolo);

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
    creato_il             TEXT
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
    ultimo_accesso      TEXT
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
        "clienti", "fascicoli", "appuntamenti",
        "scadenze", "messaggi", "utenti", "audit",
        "privacy", "notifiche", "backup",
    ]

    def __init__(self, percorsi: Dict[str, str]):
        """
        Parameters
        ----------
        percorsi:
            Dizionario {nome_modulo: percorso_file_json}.
            Chiavi riconosciute: clienti, fascicoli, appuntamenti,
            scadenze, messaggi, utenti, audit, privacy, notifiche,
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
                    messaggio=f"Utente senza password hash",
                    id_record=uid, campo="password_hash",
                    suggerimento="Reimpostare la password dell'utente",
                ))

        # Ordina: CRITICO → AVVISO → INFO
        ordine = {"CRITICO": 0, "AVVISO": 1, "INFO": 2}
        problemi.sort(key=lambda p: ordine.get(p.severita, 9))
        return problemi

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
                table_name = self._search_index_documenti_table(conn)
                if not table_name:
                    raise RuntimeError("Tabella documenti non trovata nell'indice di ricerca")
                conn.execute(f"INSERT INTO {table_name}({table_name}) VALUES('optimize')")
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                conn.commit()
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
        percorso_db = str(Path(percorso_db).resolve())
        Path(percorso_db).parent.mkdir(parents=True, exist_ok=True)

        # Rimuovi DB esistente per ricrearlo pulito
        if Path(percorso_db).exists():
            Path(percorso_db).unlink()

        conn = sqlite3.connect(percorso_db)
        conn.row_factory = sqlite3.Row
        errori: List[str] = []
        avvisi: List[str] = []
        migrati: Dict[str, int] = {}
        id_clienti_migrati = set()
        id_fascicoli_migrati = set()
        id_appuntamenti_migrati = set()

        try:
            conn.executescript(SCHEMA_SQL)

            # Meta
            conn.execute(
                "INSERT OR REPLACE INTO _meta VALUES(?,?)",
                ("migrazione_il", datetime.now().isoformat()),
            )
            for chiave, percorso in sorted(self.percorsi.items()):
                storage_kind = "sqlite" if chiave == "search_index" else "json"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO moduli_dati
                    (nome, percorso, storage_kind, inizializzato_il)
                    VALUES (?,?,?,?)
                    """,
                    (chiave, str(percorso), storage_kind, datetime.now().isoformat()),
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
                             attivita_json, documenti_json, scadenze_json)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                        ))
                        f_count += 1
                        if f.get("id"):
                            id_fascicoli_migrati.add(f.get("id"))
                    except Exception as e:
                        errori.append(f"fascicoli/{f.get('id','?')}: {e}")
                migrati["fascicoli"] = f_count

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
                             note, creato_il)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            a.get("id"), a.get("tipo", "CONSULTAZIONE"),
                            a.get("stato", "PROGRAMMATO"), a.get("titolo", ""),
                            a.get("data_ora", ""), a.get("durata_minuti", 60),
                            a.get("luogo", ""), a.get("descrizione", ""),
                            a.get("cliente", ""), a.get("cf_cliente", ""),
                            a.get("procedimento", ""), a.get("tribunale", ""),
                            a.get("note", ""), a.get("creato_il", ""),
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
                             giorni_preavviso, avvisi_inviati, completata_il, creato_il)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                        ))
                        s_count += 1
                    except Exception as e:
                        errori.append(f"scadenze/{s.get('id','?')}: {e}")
                migrati["scadenze"] = s_count

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
                             inviato_il, errore_invio, creato_il)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            m.get("id"), m.get("canale", "EMAIL"),
                            m.get("stato", "BOZZA"), m.get("oggetto", ""),
                            m.get("corpo", ""), m.get("email_destinatario", ""),
                            m.get("telefono_destinatario", ""),
                            id_cliente, id_fascicolo,
                            m.get("tipo_automazione", ""), m.get("inviato_il", ""),
                            m.get("errore_invio", ""), m.get("creato_il", ""),
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
                             permessi_extra, permessi_negati, creato_il, ultimo_accesso)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            u.get("id"), u.get("username", ""),
                            u.get("email", ""), u.get("nome_completo", ""),
                            u.get("ruolo", "SEGRETERIA"), u.get("password_hash", ""),
                            1 if u.get("attivo", True) else 0,
                            1 if u.get("must_change_password", False) else 0,
                            json.dumps(u.get("permessi_extra", []), ensure_ascii=False),
                            json.dumps(u.get("permessi_negati", []), ensure_ascii=False),
                            u.get("creato_il", ""), u.get("ultimo_accesso", ""),
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
            conn.commit()

        except Exception as e:
            errori.append(f"Errore critico migrazione: {e}")
            conn.rollback()
        finally:
            conn.close()

        ms = int((time.monotonic() - t0) * 1000)
        return RisultatoMigrazione(
            riuscita=len(errori) == 0,
            percorso_db=percorso_db,
            record_migrati=migrati,
            errori=errori,
            avvisi=avvisi,
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
            for t in tables:
                row = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
                stats[t] = row[0] if row else 0

            # Page info
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            free_pages = conn.execute("PRAGMA freelist_count").fetchone()[0]

            conn.close()
            size = p.stat().st_size
            return {
                "tabelle": stats,
                "dimensione": _fmt_bytes(size),
                "dimensione_bytes": size,
                "pagine_totali": page_count,
                "pagine_libere": free_pages,
                "frammentazione_pct": round(free_pages / page_count * 100, 1) if page_count else 0,
                "page_size": page_size,
                "esiste": True,
            }
        except Exception as e:
            return {"esiste": False, "errore": str(e)}


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
        "messaggi": {},
        "note_faldone": {},
        "notifiche": [],
        "email_casella": {},
        "fatturazione": {},
        "portale": {},
        "preventivi": {},
        "scadenze": {},          # scadenze.json — mancava dal bootstrap
        "soggetti": [],
        "soggetti_parti": {},
        "template_atti": {},
        "utenti": {},
        "validation_runs": {"runs": []},
        "redaction_assistant": [],
        "wizard_pro": [],
    }

    for nome, payload in simple_payloads.items():
        path = normalized.get(nome)
        if not path:
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
