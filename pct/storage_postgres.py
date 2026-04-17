"""Backend PostgreSQL compatibile con i repository core tenant-aware.

Questo modulo chiude il percorso R/W reale per i domini core che oggi
parlano con l'astrazione ``studio_db``:

- utenti
- audit
- clienti
- fascicoli
- agenda
- scadenziario
- timesheet

L'obiettivo non e' introdurre un ORM nuovo, ma fornire un backend piccolo e
governabile che esponga le stesse primitive usate dai repository legacy:

- ``conn.execute(...)``
- ``carica_tabella(table)``
- ``salva_tabella(table, rows, inserter)``
- ``ha_dati(table)``
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import psycopg2
import psycopg2.extras


CORE_POSTGRES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS _meta (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);

CREATE TABLE IF NOT EXISTS clienti (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL DEFAULT 'PERSONA_FISICA',
    stato TEXT NOT NULL DEFAULT 'ATTIVO',
    cognome TEXT,
    nome TEXT,
    ragione_sociale TEXT,
    codice_fiscale TEXT,
    partita_iva TEXT,
    email TEXT,
    telefono TEXT,
    note TEXT,
    creato_il TEXT,
    modificato_il TEXT,
    dati_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS fascicoli (
    id TEXT PRIMARY KEY,
    numero TEXT UNIQUE,
    titolo TEXT,
    tipo TEXT NOT NULL DEFAULT 'CIVILE',
    stato TEXT NOT NULL DEFAULT 'APERTO',
    id_cliente TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    nome_cliente TEXT,
    tribunale TEXT,
    sezione TEXT,
    giudice TEXT,
    numero_rg TEXT,
    anno_rg TEXT,
    controparte TEXT,
    avvocato_referente TEXT,
    avvocato_dominus TEXT,
    data_apertura TEXT,
    data_chiusura TEXT,
    oggetto TEXT,
    note TEXT,
    creato_il TEXT,
    modificato_il TEXT,
    attivita_json TEXT DEFAULT '[]',
    documenti_json TEXT DEFAULT '[]',
    scadenze_json TEXT DEFAULT '[]',
    dati_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS appuntamenti (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL DEFAULT 'CONSULTAZIONE',
    stato TEXT NOT NULL DEFAULT 'PROGRAMMATO',
    titolo TEXT NOT NULL,
    data_ora TEXT NOT NULL,
    durata_minuti INTEGER DEFAULT 60,
    luogo TEXT,
    descrizione TEXT,
    cliente TEXT,
    cf_cliente TEXT,
    procedimento TEXT,
    tribunale TEXT,
    note TEXT,
    creato_il TEXT,
    modificato_il TEXT,
    dati_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS scadenze (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    stato TEXT NOT NULL DEFAULT 'APERTO',
    titolo TEXT NOT NULL,
    data_scadenza TEXT NOT NULL,
    priorita TEXT DEFAULT 'MEDIA',
    perentorio INTEGER DEFAULT 0,
    note TEXT,
    id_fascicolo TEXT REFERENCES fascicoli(id) ON DELETE CASCADE,
    id_appuntamento TEXT REFERENCES appuntamenti(id) ON DELETE SET NULL,
    id_utente TEXT,
    giorni_preavviso TEXT DEFAULT '[]',
    avvisi_inviati TEXT DEFAULT '[]',
    completata_il TEXT,
    creato_il TEXT,
    dati_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS utenti (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT,
    nome_completo TEXT,
    ruolo TEXT NOT NULL DEFAULT 'SEGRETERIA',
    password_hash TEXT NOT NULL,
    attivo INTEGER DEFAULT 1,
    must_change_password INTEGER DEFAULT 0,
    permessi_extra TEXT DEFAULT '[]',
    permessi_negati TEXT DEFAULT '[]',
    creato_il TEXT,
    ultimo_accesso TEXT,
    dati_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    id_utente TEXT,
    username TEXT,
    azione TEXT NOT NULL,
    risorsa_tipo TEXT,
    risorsa_id TEXT,
    dettagli TEXT,
    ip TEXT,
    esito TEXT DEFAULT 'OK',
    dati_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS timesheet_entries (
    id TEXT PRIMARY KEY,
    id_fascicolo TEXT REFERENCES fascicoli(id) ON DELETE SET NULL,
    id_cliente TEXT REFERENCES clienti(id) ON DELETE SET NULL,
    id_utente TEXT,
    username TEXT,
    data_attivita TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    minuti INTEGER NOT NULL DEFAULT 0,
    valore_unitario REAL NOT NULL DEFAULT 0,
    fatturabile INTEGER DEFAULT 1,
    stato TEXT NOT NULL DEFAULT 'APERTO',
    origine TEXT DEFAULT '',
    creato_il TEXT,
    modificato_il TEXT,
    dati_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_clienti_cf ON clienti(codice_fiscale);
CREATE INDEX IF NOT EXISTS idx_fascicoli_cliente ON fascicoli(id_cliente);
CREATE INDEX IF NOT EXISTS idx_fascicoli_stato ON fascicoli(stato);
CREATE INDEX IF NOT EXISTS idx_appuntamenti_data ON appuntamenti(data_ora);
CREATE INDEX IF NOT EXISTS idx_scadenze_data ON scadenze(data_scadenza);
CREATE INDEX IF NOT EXISTS idx_scadenze_fascicolo ON scadenze(id_fascicolo);
CREATE INDEX IF NOT EXISTS idx_utenti_ruolo ON utenti(ruolo);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_timesheet_fascicolo ON timesheet_entries(id_fascicolo);
CREATE INDEX IF NOT EXISTS idx_timesheet_utente ON timesheet_entries(id_utente);
CREATE INDEX IF NOT EXISTS idx_timesheet_data ON timesheet_entries(data_attivita);
"""


CORE_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "clienti": (
        "id",
        "tipo",
        "stato",
        "cognome",
        "nome",
        "ragione_sociale",
        "codice_fiscale",
        "partita_iva",
        "email",
        "telefono",
        "note",
        "creato_il",
        "modificato_il",
        "dati_json",
    ),
    "fascicoli": (
        "id",
        "numero",
        "titolo",
        "tipo",
        "stato",
        "id_cliente",
        "nome_cliente",
        "tribunale",
        "sezione",
        "giudice",
        "numero_rg",
        "anno_rg",
        "controparte",
        "avvocato_referente",
        "avvocato_dominus",
        "data_apertura",
        "data_chiusura",
        "oggetto",
        "note",
        "creato_il",
        "modificato_il",
        "attivita_json",
        "documenti_json",
        "scadenze_json",
        "dati_json",
    ),
    "appuntamenti": (
        "id",
        "tipo",
        "stato",
        "titolo",
        "data_ora",
        "durata_minuti",
        "luogo",
        "descrizione",
        "cliente",
        "cf_cliente",
        "procedimento",
        "tribunale",
        "note",
        "creato_il",
        "modificato_il",
        "dati_json",
    ),
    "scadenze": (
        "id",
        "tipo",
        "stato",
        "titolo",
        "data_scadenza",
        "priorita",
        "perentorio",
        "note",
        "id_fascicolo",
        "id_appuntamento",
        "id_utente",
        "giorni_preavviso",
        "avvisi_inviati",
        "completata_il",
        "creato_il",
        "dati_json",
    ),
    "utenti": (
        "id",
        "username",
        "email",
        "nome_completo",
        "ruolo",
        "password_hash",
        "attivo",
        "must_change_password",
        "permessi_extra",
        "permessi_negati",
        "creato_il",
        "ultimo_accesso",
        "dati_json",
    ),
    "audit_log": (
        "id",
        "timestamp",
        "id_utente",
        "username",
        "azione",
        "risorsa_tipo",
        "risorsa_id",
        "dettagli",
        "ip",
        "esito",
        "dati_json",
    ),
    "timesheet_entries": (
        "id",
        "id_fascicolo",
        "id_cliente",
        "id_utente",
        "username",
        "data_attivita",
        "descrizione",
        "minuti",
        "valore_unitario",
        "fatturabile",
        "stato",
        "origine",
        "creato_il",
        "modificato_il",
        "dati_json",
    ),
}


def build_postgres_dsn(
    *,
    host: str,
    port: int,
    db_name: str,
    user: str,
    password: str,
    ssl: bool = False,
) -> str:
    ssl_suffix = "?sslmode=require" if ssl else ""
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(db_name)}{ssl_suffix}"
    )


class CompatRow(dict):
    """Row mapping che resta accessibile sia per chiave sia per indice."""

    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None):
        self._rows = [CompatRow(row) for row in (rows or [])]

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


def _translate_sql(sql: str) -> str:
    statement = sql.replace("?", "%s")
    return statement


class PostgresCompatConnection:
    """Compat layer minima per i repository che usano ``studio_db.conn``."""

    def __init__(self, backend: "PostgresStudioDB") -> None:
        self._backend = backend

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None):
        statement = str(sql or "").strip()
        upper = statement.upper()
        if upper.startswith("PRAGMA "):
            return self._handle_pragma(statement)
        if upper in {"BEGIN", "BEGIN;"}:
            return CompatResult()
        if upper in {"COMMIT", "COMMIT;"}:
            self._backend.raw_conn.commit()
            return CompatResult()
        if upper in {"ROLLBACK", "ROLLBACK;"}:
            self._backend.raw_conn.rollback()
            return CompatResult()

        with self._backend.raw_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_translate_sql(statement), tuple(params or ()))
            rows = cur.fetchall() if cur.description else []
        return CompatResult(rows)

    def _handle_pragma(self, statement: str) -> CompatResult:
        match = re.match(r"PRAGMA\s+table_info\((?P<table>[^)]+)\)", statement, re.I)
        if match:
            table = str(match.group("table") or "").strip().strip("'\"")
            rows = []
            for idx, column in enumerate(self._backend.table_columns(table)):
                rows.append(
                    {
                        "cid": idx,
                        "name": column,
                        "type": "TEXT",
                        "notnull": 0,
                        "dflt_value": None,
                        "pk": 1 if idx == 0 else 0,
                    }
                )
            return CompatResult(rows)
        return CompatResult()


_instances: dict[str, "PostgresStudioDB"] = {}
_instances_lock = threading.Lock()


class PostgresStudioDB:
    """Backend PostgreSQL con API compatibile con ``StudioDB`` per i moduli core."""

    backend_kind = "postgresql"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.db_path = Path("postgresql")
        self._local = threading.local()
        self._ensure_schema()

    @classmethod
    def get(cls, dsn: str) -> "PostgresStudioDB":
        key = str(dsn or "").strip()
        if key not in _instances:
            with _instances_lock:
                if key not in _instances:
                    _instances[key] = cls(key)
        return _instances[key]

    @property
    def raw_conn(self):
        if not hasattr(self._local, "_conn") or self._local._conn is None:
            self._local._conn = psycopg2.connect(self.dsn)
        return self._local._conn

    @property
    def conn(self) -> PostgresCompatConnection:
        return PostgresCompatConnection(self)

    def _ensure_schema(self) -> None:
        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(CORE_POSTGRES_SCHEMA_SQL)
                cur.execute(
                    """
                    INSERT INTO _meta (chiave, valore)
                    VALUES (%s, %s)
                    ON CONFLICT (chiave) DO NOTHING
                    """,
                    ("backend", "postgresql"),
                )
            conn.commit()

    def table_columns(self, table: str) -> list[str]:
        with self.raw_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            rows = cur.fetchall() or []
        return [str(row["column_name"]) for row in rows]

    def carica_tabella(self, table: str) -> list[Any]:
        try:
            rows = self.conn.execute(f"SELECT dati_json FROM {table}").fetchall()
        except Exception:
            return []
        result = []
        for row in rows:
            try:
                result.append(json.loads(row["dati_json"]))
            except Exception:
                result.append(dict(row))
        return result

    def ha_dati(self, table: str) -> bool:
        try:
            row = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        except Exception:
            return False
        return bool(row and int(row.get("n", 0) or 0) > 0)

    def salva_tabella(self, table: str, rows: list[Any], inserter, delete_all: bool = True) -> None:
        compat_conn = self.conn
        raw_conn = self.raw_conn
        try:
            with raw_conn.cursor() as cur:
                if delete_all:
                    cur.execute(f"DELETE FROM {table}")
            for row in rows:
                inserter(compat_conn, row)
            raw_conn.commit()
        except Exception:
            raw_conn.rollback()
            raise

    def chiudi(self) -> None:
        if hasattr(self._local, "_conn") and self._local._conn is not None:
            self._local._conn.close()
            self._local._conn = None
