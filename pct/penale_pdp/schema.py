"""Tabelle del procedimento penale telematico, accanto al workflow PDP esistente.

Stanno nello stesso database di ``pct/pdp_penale_workflow.py`` e legano
ogni riga a ``criminal_cases``. Modellano ciò che il PDP chiede e restituisce
(manuale utente PDP; provvedimento DGSIA 11/07/2023 art. 6-7):

- i registri del procedimento negli uffici che attraversa (PM-U, GIP-U, DIB-U…);
- i soggetti rappresentati con il ruolo PDP (IND, OFF, CIV, RES, COB, TER);
- i depositi preparati, con composizione, controlli, identificativo e stato;
- le udienze lette dallo storico del PDP.
"""

from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS criminal_case_registers (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL REFERENCES criminal_cases(id) ON DELETE CASCADE,
    office_code TEXT NOT NULL,
    office_name TEXT NOT NULL DEFAULT '',
    register_type TEXT NOT NULL DEFAULT '',
    register_number TEXT NOT NULL DEFAULT '',
    register_year TEXT NOT NULL DEFAULT '',
    magistrate TEXT NOT NULL DEFAULT '',
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1)),
    source TEXT NOT NULL DEFAULT 'manuale',
    created_at TEXT NOT NULL,
    UNIQUE (criminal_case_id, office_code, register_number, register_year)
);
CREATE TABLE IF NOT EXISTS criminal_case_subjects (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL REFERENCES criminal_cases(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    role_code TEXT NOT NULL CHECK (role_code IN ('IND','OFF','CIV','RES','COB','TER')),
    tax_code TEXT NOT NULL DEFAULT '',
    subject_kind TEXT NOT NULL DEFAULT 'fisica' CHECK (subject_kind IN ('fisica','giuridica')),
    birth_date TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manuale',
    created_at TEXT NOT NULL,
    UNIQUE (criminal_case_id, full_name, role_code)
);
CREATE TABLE IF NOT EXISTS criminal_deposits (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL REFERENCES criminal_cases(id) ON DELETE CASCADE,
    act_name TEXT NOT NULL,
    is_main_act INTEGER NOT NULL DEFAULT 0 CHECK (is_main_act IN (0,1)),
    office_code TEXT NOT NULL DEFAULT '',
    office_name TEXT NOT NULL DEFAULT '',
    register_label TEXT NOT NULL DEFAULT '',
    subjects_json TEXT NOT NULL DEFAULT '[]',
    files_json TEXT NOT NULL DEFAULT '[]',
    data_json TEXT NOT NULL DEFAULT '{}',
    checks_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'BOZZA' CHECK (status IN (
        'BOZZA','PRONTO','INVIATO','IN_TRANSITO','IN_FASE_DI_VERIFICA','ACCOLTO','RIGETTATO','ERRORE_TECNICO')),
    sending_id TEXT NOT NULL DEFAULT '',
    sent_at TEXT NOT NULL DEFAULT '',
    arrived_at TEXT NOT NULL DEFAULT '',
    rejection_reason TEXT NOT NULL DEFAULT '',
    receipt_document_id TEXT NOT NULL DEFAULT '',
    outcome_document_id TEXT NOT NULL DEFAULT '',
    receipt_check_json TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT 'iusentra',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_criminal_deposits_case ON criminal_deposits(criminal_case_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_criminal_deposits_sending
    ON criminal_deposits(criminal_case_id, sending_id) WHERE sending_id <> '';
CREATE TABLE IF NOT EXISTS criminal_hearings (
    id TEXT PRIMARY KEY,
    criminal_case_id TEXT NOT NULL REFERENCES criminal_cases(id) ON DELETE CASCADE,
    starts_at TEXT NOT NULL,
    office_type TEXT NOT NULL DEFAULT '',
    room TEXT NOT NULL DEFAULT '',
    place TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    agenda_id TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'export_pdp',
    created_at TEXT NOT NULL,
    UNIQUE (criminal_case_id, starts_at, office_type)
);
"""

# Colonne aggiunte a criminal_cases (database già esistenti).
COLONNE_CASI: tuple[tuple[str, str], ...] = (
    ("pdp_office_code", "TEXT NOT NULL DEFAULT ''"),
    ("authorized", "INTEGER NOT NULL DEFAULT 0"),
    ("authorized_source", "TEXT NOT NULL DEFAULT ''"),
    ("authorized_at", "TEXT NOT NULL DEFAULT ''"),
    ("avocato_pg", "INTEGER NOT NULL DEFAULT 0"),
)


def assicura_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    presenti = {riga[1] for riga in conn.execute("PRAGMA table_info(criminal_cases)").fetchall()}
    for nome, definizione in COLONNE_CASI:
        if presenti and nome not in presenti:
            conn.execute(f"ALTER TABLE criminal_cases ADD COLUMN {nome} {definizione}")


__all__ = ["COLONNE_CASI", "SCHEMA_SQL", "assicura_schema"]
