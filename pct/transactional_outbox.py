"""Outbox transazionale tenant-aware per gli eventi applicativi.

Il modulo non invia PEC, firme, depositi o pagamenti: registra soltanto
eventi interni nella stessa transazione della mutazione business. Il
dispatcher resta separato affinché una scrittura SQL non inneschi mai
un'azione legale o esterna non autorizzata.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

OUTBOX_TABLE = "transactional_outbox"

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactional_outbox (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    actor_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    causation_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_transactional_outbox_pending
    ON transactional_outbox(status, available_at);
CREATE INDEX IF NOT EXISTS idx_transactional_outbox_tenant_aggregate
    ON transactional_outbox(tenant_id, aggregate_type, aggregate_id);
"""

# Il DDL usa soltanto tipi e vincoli condivisi da SQLite e PostgreSQL.
POSTGRES_SCHEMA = SQLITE_SCHEMA


@dataclass(frozen=True)
class OutboxEvent:
    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    event_type: str
    idempotency_key: str
    payload: dict[str, Any]
    actor_id: str
    correlation_id: str = ""
    causation_id: str = ""


def _required(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} obbligatorio per l'outbox transazionale.")
    return normalized


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_outbox_schema(conn: Any) -> None:
    """Crea schema e indici; il chiamante mantiene la propria transazione."""

    if hasattr(conn, "executescript"):
        conn.executescript(SQLITE_SCHEMA)
        return
    for statement in POSTGRES_SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)


def enqueue(conn: Any, event: OutboxEvent) -> str:
    """Accoda un evento una sola volta nella transazione gia' aperta.

    L'idempotency key e' il vincolo contro le duplicazioni. La funzione non
    esegue ``commit``: rollback e commit restano atomici con il dato business.
    """

    tenant_id = _required(event.tenant_id, "Tenant")
    aggregate_type = _required(event.aggregate_type, "Tipo aggregate")
    aggregate_id = _required(event.aggregate_id, "ID aggregate")
    event_type = _required(event.event_type, "Tipo evento")
    idempotency_key = _required(event.idempotency_key, "Idempotency key")
    actor_id = _required(event.actor_id, "Attore")
    if event.aggregate_version < 1:
        raise ValueError("La versione aggregate dell'outbox deve essere positiva.")
    now = _now()
    event_id = str(uuid.uuid4())
    correlation_id = str(event.correlation_id or idempotency_key).strip()
    payload_json = json.dumps(event.payload or {}, ensure_ascii=False, sort_keys=True)
    values = (
        event_id, tenant_id, aggregate_type, aggregate_id, int(event.aggregate_version),
        event_type, idempotency_key, actor_id, correlation_id, str(event.causation_id or ""),
        payload_json, now, now,
    )
    sqlite = hasattr(conn, "executescript")
    placeholders = ", ".join("?" if sqlite else "%s" for _ in values)
    sql = f"""INSERT INTO {OUTBOX_TABLE} (
        id, tenant_id, aggregate_type, aggregate_id, aggregate_version, event_type,
        idempotency_key, actor_id, correlation_id, causation_id, payload_json, available_at, created_at
    ) VALUES ({placeholders})"""
    try:
        conn.execute(sql, values)
    except Exception as exc:
        message = str(exc).lower()
        if "unique" in message or "duplicate" in message:
            return idempotency_key
        raise
    return event_id
