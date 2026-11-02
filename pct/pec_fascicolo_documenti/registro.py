"""Registro SQL del flusso PEC → documenti del fascicolo, nel database del presidio PEC (SQLite).

Sta nella stessa base di ``pec_messages`` e ``pec_fascicolo_links`` (``pec_audit.sqlite``, perimetro solo
SQLite dichiarato in docs/PEC_AUDIT_PIPELINE.md): il collegamento e il suo esito si leggono insieme.

* ``pec_fascicolo_documenti``: un esito per oggetto (allegato o .eml) con impronta SHA-256, nome originale,
  documento creato, mittente e data di consegna in ora italiana. È la chiave di idempotenza.
* ``pec_fascicolo_documenti_messaggi``: lo stato del messaggio (completato, in attesa di conferma, errore)
  e i tentativi; il recupero storico riprende da qui.
* ``pec_fascicolo_documenti_giri``: ogni giro con i conteggi, per la console e per la verifica sul server.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS pec_fascicolo_documenti (
    tenant_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    ruolo TEXT NOT NULL,
    nome_originale TEXT NOT NULL,
    sha256 TEXT NOT NULL DEFAULT '',
    esito TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT '',
    documento_id TEXT NOT NULL DEFAULT '',
    message_id_header TEXT NOT NULL DEFAULT '',
    mittente TEXT NOT NULL DEFAULT '',
    consegnata_il TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, message_id, fascicolo_id, ruolo, nome_originale, sha256)
);
CREATE INDEX IF NOT EXISTS idx_pec_fascicolo_documenti_fascicolo
    ON pec_fascicolo_documenti (tenant_id, fascicolo_id, sha256);
CREATE TABLE IF NOT EXISTS pec_fascicolo_documenti_messaggi (
    tenant_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL,
    motivo TEXT NOT NULL DEFAULT '',
    tentativi INTEGER NOT NULL DEFAULT 0,
    salvati INTEGER NOT NULL DEFAULT 0,
    eml_salvati INTEGER NOT NULL DEFAULT 0,
    scartati INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_pec_fascicolo_documenti_messaggi_stato
    ON pec_fascicolo_documenti_messaggi (tenant_id, stato);
CREATE TABLE IF NOT EXISTS pec_fascicolo_documenti_giri (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    origine TEXT NOT NULL,
    iniziato_il TEXT NOT NULL,
    finito_il TEXT NOT NULL,
    esito_json TEXT NOT NULL DEFAULT '{}'
);
"""

MASSIMO_TENTATIVI = 3


def adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def prepara(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def esito_oggetto(conn: sqlite3.Connection, tenant_id: str, message_id: str, fascicolo_id: str, sha256: str) -> dict[str, Any]:
    """L'esito già registrato per lo stesso file della stessa PEC nello stesso fascicolo (salvato o presente)."""
    riga = conn.execute(
        "SELECT esito, documento_id FROM pec_fascicolo_documenti WHERE tenant_id=? AND message_id=? AND fascicolo_id=? "
        "AND sha256=? AND esito IN ('salvato', 'gia_presente') LIMIT 1",
        (tenant_id, message_id, fascicolo_id, sha256),
    ).fetchone()
    return dict(riga) if riga else {}


def registra_oggetti(conn: sqlite3.Connection, righe: Iterable[dict[str, Any]]) -> None:
    for riga in righe:
        conn.execute(
            "INSERT INTO pec_fascicolo_documenti (tenant_id, message_id, fascicolo_id, ruolo, nome_originale, sha256, esito, motivo, "
            "documento_id, message_id_header, mittente, consegnata_il, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(tenant_id, message_id, fascicolo_id, ruolo, nome_originale, sha256) DO UPDATE SET "
            "esito=excluded.esito, motivo=excluded.motivo, documento_id=CASE WHEN excluded.documento_id<>'' "
            "THEN excluded.documento_id ELSE pec_fascicolo_documenti.documento_id END",
            (
                riga["tenant_id"], riga["message_id"], riga.get("fascicolo_id", ""), riga["ruolo"], riga["nome_originale"],
                riga.get("sha256", ""), riga["esito"], riga.get("motivo", ""), riga.get("documento_id", ""),
                riga.get("message_id_header", ""), riga.get("mittente", ""), riga.get("consegnata_il", ""), adesso(),
            ),
        )


def stato_messaggio(conn: sqlite3.Connection, tenant_id: str, message_id: str) -> dict[str, Any]:
    riga = conn.execute(
        "SELECT * FROM pec_fascicolo_documenti_messaggi WHERE tenant_id=? AND message_id=?", (tenant_id, message_id),
    ).fetchone()
    return dict(riga) if riga else {}


def registra_messaggio(conn: sqlite3.Connection, tenant_id: str, message_id: str, *, fascicolo_id: str, stato: str,
                       motivo: str = "", salvati: int = 0, eml_salvati: int = 0, scartati: int = 0) -> None:
    precedente = stato_messaggio(conn, tenant_id, message_id)
    tentativi = int(precedente.get("tentativi") or 0) + 1 if stato == "errore" else 0
    conn.execute(
        "INSERT INTO pec_fascicolo_documenti_messaggi (tenant_id, message_id, fascicolo_id, stato, motivo, tentativi, salvati, "
        "eml_salvati, scartati, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id, message_id) DO UPDATE SET "
        "fascicolo_id=excluded.fascicolo_id, stato=excluded.stato, motivo=excluded.motivo, tentativi=excluded.tentativi, "
        "salvati=excluded.salvati, eml_salvati=excluded.eml_salvati, scartati=excluded.scartati, updated_at=excluded.updated_at",
        (tenant_id, message_id, fascicolo_id, stato, motivo[:300], tentativi, salvati, eml_salvati, scartati, adesso()),
    )


def registra_giro(conn: sqlite3.Connection, tenant_id: str, origine: str, iniziato_il: str, esito: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO pec_fascicolo_documenti_giri (tenant_id, origine, iniziato_il, finito_il, esito_json) VALUES (?,?,?,?,?)",
        (tenant_id, origine, iniziato_il, adesso(), json.dumps(esito, ensure_ascii=False, sort_keys=True)),
    )
    # Si conservano gli ultimi 200 giri per studio: bastano per la verifica, senza crescere senza fine.
    conn.execute(
        "DELETE FROM pec_fascicolo_documenti_giri WHERE tenant_id=? AND id NOT IN "
        "(SELECT id FROM pec_fascicolo_documenti_giri WHERE tenant_id=? ORDER BY id DESC LIMIT 200)",
        (tenant_id, tenant_id),
    )


def ultimo_giro(conn: sqlite3.Connection, tenant_id: str) -> dict[str, Any]:
    riga = conn.execute(
        "SELECT origine, iniziato_il, finito_il, esito_json FROM pec_fascicolo_documenti_giri WHERE tenant_id=? ORDER BY id DESC LIMIT 1",
        (tenant_id,),
    ).fetchone()
    if not riga:
        return {}
    return {"origine": riga["origine"], "iniziato_il": riga["iniziato_il"], "finito_il": riga["finito_il"],
            "esito": json.loads(riga["esito_json"] or "{}")}


__all__ = [
    "MASSIMO_TENTATIVI", "SCHEMA", "adesso", "esito_oggetto", "prepara", "registra_giro", "registra_messaggio",
    "registra_oggetti", "stato_messaggio", "ultimo_giro",
]
