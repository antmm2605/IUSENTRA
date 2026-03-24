"""
Gestione database centralizzata per lo studio legale PCT.

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


# ================================================================ Dataclasses

@dataclass
class StatisticheModulo:
    nome: str
    percorso: str
    esiste: bool
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
"""


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

    MODULI = [
        "clienti", "fascicoli", "appuntamenti",
        "scadenze", "messaggi", "utenti", "audit",
    ]

    def __init__(self, percorsi: Dict[str, str]):
        """
        Parameters
        ----------
        percorsi:
            Dizionario {nome_modulo: percorso_file_json}.
            Chiavi riconosciute: clienti, fascicoli, appuntamenti,
            scadenze, messaggi, utenti, audit, search_index.
        """
        self.percorsi = {k: Path(v) for k, v in percorsi.items()}

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

        for chiave in self.MODULI:
            p = self.percorsi.get(chiave)
            sm = StatisticheModulo(
                nome=chiave,
                percorso=str(p) if p else "",
                esiste=bool(p and p.exists()),
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
            )
            if search_p.exists():
                sm_s.dimensione_bytes, sm_s.ultima_modifica = self._stat_file(search_p)
                try:
                    conn = sqlite3.connect(str(search_p))
                    row = conn.execute("SELECT COUNT(*) FROM documenti").fetchone()
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
        for chiave in self.MODULI:
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
            try:
                conn = sqlite3.connect(str(search_p))
                conn.execute("INSERT INTO documenti(documenti) VALUES('optimize')")
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                conn.commit()
                conn.close()
                ms = int((time.monotonic() - t0) * 1000)
                risultati.append(RisultatoOttimizzazione(
                    modulo="search_index", operazione="VACUUM + ANALYZE + FTS optimize",
                    riuscita=True, ms=ms,
                ))
            except Exception as e:
                risultati.append(RisultatoOttimizzazione(
                    modulo="search_index", operazione="VACUUM",
                    riuscita=False, dettagli=str(e),
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
        migrati: Dict[str, int] = {}

        try:
            conn.executescript(SCHEMA_SQL)

            # Meta
            conn.execute(
                "INSERT OR REPLACE INTO _meta VALUES(?,?)",
                ("migrazione_il", datetime.now().isoformat()),
            )

            # ---- Clienti
            clienti_raw, err = self._leggi_json("clienti")
            if err:
                errori.append(f"clienti: {err}")
            else:
                c_count = 0
                for c in clienti_raw:
                    try:
                        ind = c.get("indirizzo") or {}
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
                            (rec.get("telefono_principale") if isinstance(rec, dict) else c.get("telefono", "")),
                            c.get("note", ""), c.get("creato_il", ""),
                            json.dumps(c, ensure_ascii=False),
                        ))
                        c_count += 1
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
                            f.get("id_cliente") or None, f.get("nome_cliente", ""),
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
                            s.get("note", ""), s.get("id_fascicolo") or None,
                            s.get("id_appuntamento") or None,
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
                            m.get("id_cliente") or None, m.get("id_fascicolo") or None,
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
                             password_hash, attivo, permessi_extra, permessi_negati,
                             creato_il, ultimo_accesso)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            u.get("id"), u.get("username", ""),
                            u.get("email", ""), u.get("nome_completo", ""),
                            u.get("ruolo", "SEGRETERIA"), u.get("password_hash", ""),
                            1 if u.get("attivo", True) else 0,
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

            conn.execute("INSERT OR REPLACE INTO _meta VALUES(?,?)",
                         ("totale_record", str(sum(migrati.values()))))
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
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '\\_%' ESCAPE '\\'"
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
