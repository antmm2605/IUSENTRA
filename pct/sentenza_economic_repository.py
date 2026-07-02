"""Persistenza tenant-aware per Sentenza Economic Control V1.

Due livelli, complementari:
- stato interrogabile: SQLite/PostgreSQL (audit sentenza, controllo contributo
  unificato, eventi economici del fascicolo), con whitelist di tabelle/colonne
  come il Portale Cliente (nessuna interpolazione di identificatori);
- registro probatorio: catena di hash append-only (`ComplianceDecisionLog`),
  così ogni decisione economica è immutabile e verificabile.

Il modulo NON dipende dal motore (`sentenza_economic_audit`): accetta solo dati
primitivi/dict, così può essere testato e riusato senza import circolari.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pct.compliance.decisions import ComplianceDecisionLog
from pct.postgres_runtime_support import PostgresRepositoryBackend


SCHEMA_SENTENZA_ECONOMIC_SQLITE = Path(__file__).with_name("sql") / "20260702_sentenza_economic.sql"
SCHEMA_SENTENZA_ECONOMIC_POSTGRES = Path(__file__).with_name("sql") / "20260702_sentenza_economic_postgres.sql"

SENTENZA_ECONOMIC_TABLES = (
    "sentenza_economic_audits",
    "contributo_unificato_audits",
    "fascicolo_economic_events",
    "sentenza_economic_audit_events",
)
SENTENZA_ECONOMIC_TABLE_SQL = {table: f'"{table}"' for table in SENTENZA_ECONOMIC_TABLES}
SENTENZA_ECONOMIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "sentenza_economic_audits": (
        "id", "tenant_id", "fascicolo_id", "documento_id", "message_id",
        "document_hash_sha256", "fonte", "rg_numero_rilevato", "rg_anno_rilevato",
        "cliente_rilevato", "tribunale_rilevato", "match_score", "safe_to_attach",
        "human_review_required", "status", "audit_json", "created_at", "updated_at",
    ),
    "contributo_unificato_audits": (
        "id", "tenant_id", "fascicolo_id", "sentenza_audit_id", "documento_id",
        "status", "importo_pagato", "importo_atteso", "differenza", "iuv",
        "ricevuta_id", "data_pagamento", "fonte_prova", "evidence_hash_sha256",
        "human_review_required", "audit_json", "created_at",
    ),
    "fascicolo_economic_events": (
        "id", "tenant_id", "fascicolo_id", "source_type", "source_id", "event_type",
        "beneficiary_type", "amount", "currency", "status", "priority",
        "evidence_json", "created_at", "reviewed_at", "reviewed_by",
    ),
    "sentenza_economic_audit_events": (
        "id", "tenant_id", "actor_type", "actor_id", "action", "resource_type",
        "resource_id", "created_at", "details_json",
    ),
}
SENTENZA_ECONOMIC_COLUMN_SQL = {
    column: f'"{column}"'
    for columns in SENTENZA_ECONOMIC_COLUMNS.values()
    for column in columns
}
SENTENZA_ECONOMIC_WHERE_SQL = {
    "": "",
    "tenant_id = ?": '"tenant_id" = ?',
    "id = ? AND tenant_id = ?": '"id" = ? AND "tenant_id" = ?',
    "tenant_id = ? AND id = ?": '"tenant_id" = ? AND "id" = ?',
    "tenant_id = ? AND fascicolo_id = ?": '"tenant_id" = ? AND "fascicolo_id" = ?',
    "tenant_id = ? AND status = ?": '"tenant_id" = ? AND "status" = ?',
}
SENTENZA_ECONOMIC_ORDER_SQL = {
    "created_at DESC": '"created_at" DESC',
    "created_at ASC": '"created_at" ASC',
    "updated_at DESC": '"updated_at" DESC',
}


class SentenzaEconomicError(ValueError):
    """Errore controllato del controllo economico sentenze."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: Any, fallback: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        return fallback


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


def _sql_table(table: str) -> str:
    sql = SENTENZA_ECONOMIC_TABLE_SQL.get(str(table or ""))
    if not sql:
        raise SentenzaEconomicError("Tabella dati non valida.")
    return sql


def _sql_columns(table: str, values: dict[str, Any]) -> tuple[str, ...]:
    allowed = SENTENZA_ECONOMIC_COLUMNS.get(str(table or ""))
    if not allowed:
        raise SentenzaEconomicError("Tabella dati non valida.")
    if any(column not in allowed for column in values):
        raise SentenzaEconomicError("Colonna dati non valida.")
    return tuple(column for column in allowed if column in values)


def _sql_where_clause(where: str) -> str:
    sql = SENTENZA_ECONOMIC_WHERE_SQL.get(str(where or "").strip())
    if sql is None:
        raise SentenzaEconomicError("Filtro dati non valido.")
    return sql


def _sql_order_clause(order: str) -> str:
    sql = SENTENZA_ECONOMIC_ORDER_SQL.get(str(order or "created_at DESC").strip())
    if sql is None:
        raise SentenzaEconomicError("Ordinamento dati non valido.")
    return sql


class SentenzaEconomicRepository:
    """Repository del controllo economico sentenze (SQLite o PostgreSQL) + registro firmato."""

    def __init__(self, db_path: str | Path = "", *, postgres_dsn: str = "", decisions_path: str | Path = "") -> None:
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.backend_kind = "postgres" if self.postgres_dsn else "sqlite"
        self.db_path = Path(db_path or "./data/economico/sentenza_economic.db")
        self._pg_backend: PostgresRepositoryBackend | None = None
        if self.postgres_dsn:
            self._pg_backend = PostgresRepositoryBackend(self.postgres_dsn, SCHEMA_SENTENZA_ECONOMIC_POSTGRES)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_sqlite_schema()
        decisions = Path(decisions_path) if decisions_path else self._default_decisions_path()
        self._decisions = ComplianceDecisionLog(decisions)

    def _default_decisions_path(self) -> Path:
        anchor = self.db_path if self.backend_kind == "sqlite" else Path("./data/economico/sentenza_economic.db")
        return anchor.with_name("sentenza_economic_decisions.jsonl")

    def _ensure_sqlite_schema(self) -> None:
        schema = SCHEMA_SENTENZA_ECONOMIC_SQLITE.read_text(encoding="utf-8")
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(schema)

    def connection(self):
        if self._pg_backend is not None:
            return self._pg_backend.connection()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        if self._pg_backend is not None:
            self._pg_backend.close()

    # ---- primitive SQL (whitelist) -----------------------------------------

    def _fetchone(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return _row_dict(row)

    def _fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_dict(row) for row in rows]

    def _insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        safe_table = _sql_table(table)
        columns = _sql_columns(table, values)
        placeholders = ", ".join("?" for _ in columns)
        names = ", ".join(SENTENZA_ECONOMIC_COLUMN_SQL[column] for column in columns)
        with self.connection() as conn:
            conn.execute(
                f"INSERT INTO {safe_table} ({names}) VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
        return dict(values)

    def _update(self, table: str, values: dict[str, Any], where: str, params: Iterable[Any]) -> None:
        if not values:
            return
        safe_table = _sql_table(table)
        columns = _sql_columns(table, values)
        assignments = ", ".join(f"{SENTENZA_ECONOMIC_COLUMN_SQL[column]} = ?" for column in columns)
        safe_where = _sql_where_clause(where)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE {safe_table} SET {assignments} WHERE {safe_where}",
                (*(values[column] for column in columns), *tuple(params)),
            )

    def schema_table_names(self) -> set[str]:
        if self.backend_kind == "postgres":
            return set(SENTENZA_ECONOMIC_TABLES)
        rows = self._fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND (name LIKE 'sentenza_economic_%' OR name LIKE 'contributo_unificato_%' OR name LIKE 'fascicolo_economic_%')"
        )
        return {str(row.get("name") or "") for row in rows}

    # ---- audit log mutabile (timeline) -------------------------------------

    def record_audit(self, tenant_id: str, actor_type: str, actor_id: str, action: str, resource_type: str, resource_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        row = {
            "id": new_id("sea"),
            "tenant_id": str(tenant_id),
            "actor_type": str(actor_type or ""),
            "actor_id": str(actor_id or ""),
            "action": str(action or ""),
            "resource_type": str(resource_type or ""),
            "resource_id": str(resource_id or ""),
            "created_at": utc_now(),
            "details_json": json_dumps(details or {}),
        }
        return self._insert("sentenza_economic_audit_events", row)

    # ---- registro probatorio firmato ---------------------------------------

    def record_decision(self, *, tenant_id: str, actor_id: str, kind: str, subject_ref: str, decision: str, rationale: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._decisions.record_decision(
            tenant_id=tenant_id, actor_id=actor_id, kind=kind,
            subject_ref=subject_ref, decision=decision, rationale=rationale, evidence=evidence,
        )

    def list_decisions(self, *, tenant_id: str | None = None) -> list[dict[str, Any]]:
        return self._decisions.list_decisions(tenant_id=tenant_id)

    def verify_decisions(self) -> bool:
        return self._decisions.verify_chain()

    # ---- audit sentenza -----------------------------------------------------

    def save_sentenza_audit(
        self,
        tenant_id: str,
        *,
        fascicolo_id: str,
        documento_id: str = "",
        message_id: str = "",
        document_hash_sha256: str = "",
        fonte: str = "",
        rg_numero_rilevato: str = "",
        rg_anno_rilevato: str = "",
        cliente_rilevato: str = "",
        tribunale_rilevato: str = "",
        match_score: float = 0.0,
        safe_to_attach: bool = False,
        human_review_required: bool = True,
        status: str = "to_review",
        audit: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": new_id("sea_audit"),
            "tenant_id": str(tenant_id),
            "fascicolo_id": str(fascicolo_id),
            "documento_id": str(documento_id or ""),
            "message_id": str(message_id or ""),
            "document_hash_sha256": str(document_hash_sha256 or ""),
            "fonte": str(fonte or ""),
            "rg_numero_rilevato": str(rg_numero_rilevato or ""),
            "rg_anno_rilevato": str(rg_anno_rilevato or ""),
            "cliente_rilevato": str(cliente_rilevato or ""),
            "tribunale_rilevato": str(tribunale_rilevato or ""),
            "match_score": float(match_score or 0.0),
            "safe_to_attach": 1 if safe_to_attach else 0,
            "human_review_required": 1 if human_review_required else 0,
            "status": str(status or "to_review"),
            "audit_json": json_dumps(audit or {}),
            "created_at": now,
            "updated_at": now,
        }
        self._insert("sentenza_economic_audits", row)
        return self._decode_audit_row(row)

    def get_sentenza_audit(self, tenant_id: str, audit_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            "SELECT * FROM sentenza_economic_audits WHERE id = ? AND tenant_id = ?",
            (audit_id, tenant_id),
        )
        return self._decode_audit_row(row) if row else None

    def list_sentenza_audits(self, tenant_id: str, *, fascicolo_id: str = "") -> list[dict[str, Any]]:
        if fascicolo_id:
            rows = self._fetchall(
                "SELECT * FROM sentenza_economic_audits WHERE tenant_id = ? AND fascicolo_id = ? ORDER BY created_at DESC",
                (tenant_id, fascicolo_id),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM sentenza_economic_audits WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            )
        return [self._decode_audit_row(row) for row in rows]

    def update_sentenza_audit_status(self, tenant_id: str, audit_id: str, *, status: str) -> None:
        self._update(
            "sentenza_economic_audits",
            {"status": str(status), "updated_at": utc_now()},
            "tenant_id = ? AND id = ?",
            (tenant_id, audit_id),
        )

    @staticmethod
    def _decode_audit_row(row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["safe_to_attach"] = bool(data.get("safe_to_attach"))
        data["human_review_required"] = bool(data.get("human_review_required"))
        data["audit"] = json_loads(data.pop("audit_json", ""), {})
        return data

    # ---- contributo unificato ----------------------------------------------

    def save_contributo_unificato(
        self,
        tenant_id: str,
        *,
        fascicolo_id: str,
        sentenza_audit_id: str = "",
        documento_id: str = "",
        status: str = "incerto",
        importo_pagato: float | None = None,
        importo_atteso: float | None = None,
        differenza: float | None = None,
        iuv: str = "",
        ricevuta_id: str = "",
        data_pagamento: str = "",
        fonte_prova: str = "",
        evidence_hash_sha256: str = "",
        human_review_required: bool = True,
        audit: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": new_id("cu_audit"),
            "tenant_id": str(tenant_id),
            "fascicolo_id": str(fascicolo_id),
            "sentenza_audit_id": str(sentenza_audit_id or ""),
            "documento_id": str(documento_id or ""),
            "status": str(status or "incerto"),
            "importo_pagato": importo_pagato,
            "importo_atteso": importo_atteso,
            "differenza": differenza,
            "iuv": str(iuv or ""),
            "ricevuta_id": str(ricevuta_id or ""),
            "data_pagamento": str(data_pagamento or ""),
            "fonte_prova": str(fonte_prova or ""),
            "evidence_hash_sha256": str(evidence_hash_sha256 or ""),
            "human_review_required": 1 if human_review_required else 0,
            "audit_json": json_dumps(audit or {}),
            "created_at": utc_now(),
        }
        self._insert("contributo_unificato_audits", row)
        return dict(row)

    def list_contributo_unificato(self, tenant_id: str, *, fascicolo_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM contributo_unificato_audits WHERE tenant_id = ? AND fascicolo_id = ? ORDER BY created_at DESC",
            (tenant_id, fascicolo_id),
        )

    # ---- eventi economici del fascicolo ------------------------------------

    def add_economic_event(
        self,
        tenant_id: str,
        *,
        fascicolo_id: str,
        event_type: str,
        source_type: str = "sentenza_economic_audit",
        source_id: str = "",
        beneficiary_type: str = "",
        amount: float | None = None,
        currency: str = "EUR",
        status: str = "to_review",
        priority: str = "P2",
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": new_id("fee"),
            "tenant_id": str(tenant_id),
            "fascicolo_id": str(fascicolo_id),
            "source_type": str(source_type or ""),
            "source_id": str(source_id or ""),
            "event_type": str(event_type),
            "beneficiary_type": str(beneficiary_type or ""),
            "amount": amount,
            "currency": str(currency or "EUR"),
            "status": str(status or "to_review"),
            "priority": str(priority or "P2"),
            "evidence_json": json_dumps(evidence or []),
            "created_at": utc_now(),
            "reviewed_at": "",
            "reviewed_by": "",
        }
        self._insert("fascicolo_economic_events", row)
        return self._decode_event_row(row)

    def list_economic_events(self, tenant_id: str, *, fascicolo_id: str = "", status: str = "") -> list[dict[str, Any]]:
        if fascicolo_id:
            rows = self._fetchall(
                "SELECT * FROM fascicolo_economic_events WHERE tenant_id = ? AND fascicolo_id = ? ORDER BY created_at DESC",
                (tenant_id, fascicolo_id),
            )
        elif status:
            rows = self._fetchall(
                "SELECT * FROM fascicolo_economic_events WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC",
                (tenant_id, status),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM fascicolo_economic_events WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            )
        return [self._decode_event_row(row) for row in rows]

    def update_event_status(self, tenant_id: str, event_id: str, *, status: str, reviewed_by: str = "") -> None:
        self._update(
            "fascicolo_economic_events",
            {"status": str(status), "reviewed_at": utc_now(), "reviewed_by": str(reviewed_by or "")},
            "tenant_id = ? AND id = ?",
            (tenant_id, event_id),
        )

    @staticmethod
    def _decode_event_row(row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["evidence"] = json_loads(data.pop("evidence_json", ""), [])
        return data


__all__ = [
    "SentenzaEconomicRepository",
    "SentenzaEconomicError",
    "SENTENZA_ECONOMIC_TABLES",
    "SCHEMA_SENTENZA_ECONOMIC_SQLITE",
    "SCHEMA_SENTENZA_ECONOMIC_POSTGRES",
]
