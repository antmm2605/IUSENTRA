"""Database index for audit evidence.

The database is deliberately an index/cache. WORM objects remain the source of
truth and every row can be rebuilt from immutable evidence objects.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

from .exceptions import AuditIndexError
from .schemas import AuditEventIndexRecord, AuditSnapshotIndexRecord


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events_index (
  event_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  fascicolo_id TEXT NOT NULL,
  actor_id TEXT,
  kind TEXT NOT NULL,
  event_ts_utc TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  prev_event_hash TEXT,
  payload_hash TEXT NOT NULL,
  files_hashes_jsonb TEXT NOT NULL DEFAULT '{}',
  signature_alg TEXT NOT NULL,
  signer_kid TEXT NOT NULL,
  signer_cert_fingerprint TEXT,
  worm_bucket TEXT NOT NULL,
  worm_key TEXT NOT NULL,
  worm_version_id TEXT NOT NULL,
  worm_retention_until TEXT NOT NULL,
  snapshot_id TEXT,
  idempotency_key TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_events_idempotency
  ON audit_events_index(tenant_id, fascicolo_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_audit_events_chain
  ON audit_events_index(tenant_id, fascicolo_id, event_ts_utc, event_id);

CREATE INDEX IF NOT EXISTS idx_audit_events_snapshot
  ON audit_events_index(tenant_id, snapshot_id);

CREATE TABLE IF NOT EXISTS audit_snapshots_index (
  snapshot_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  period_start_utc TEXT NOT NULL,
  period_end_utc TEXT NOT NULL,
  merkle_root TEXT NOT NULL,
  events_count INTEGER NOT NULL,
  snapshot_hash TEXT NOT NULL,
  signature_alg TEXT NOT NULL,
  signer_kid TEXT NOT NULL,
  tsa_token_worm_key TEXT,
  worm_bucket TEXT NOT NULL,
  worm_key TEXT NOT NULL,
  worm_version_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_snapshots_period
  ON audit_snapshots_index(tenant_id, period_start_utc, period_end_utc);

CREATE TABLE IF NOT EXISTS audit_emit_failures (
  failure_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  fascicolo_id TEXT,
  attempted_kind TEXT,
  idempotency_key TEXT,
  failure_stage TEXT NOT NULL,
  error_code TEXT NOT NULL,
  error_message_sanitized TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_reconciliation_runs (
  run_id TEXT PRIMARY KEY,
  tenant_id TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  objects_seen INTEGER NOT NULL DEFAULT 0,
  missing_index_rows_created INTEGER NOT NULL DEFAULT 0,
  conflicts_found INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or "{}"))
    except Exception:
        return {}


class AuditRepository:
    def __init__(self, sqlite_path: str | Path | None = None, *, postgres_dsn: str = "", connection: Any | None = None) -> None:
        self.sqlite_path = Path(sqlite_path) if sqlite_path else None
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self._connection = connection
        if isinstance(self._connection, sqlite3.Connection):
            self._connection.row_factory = sqlite3.Row
        self._local = threading.local()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._ensure_schema()

    @classmethod
    def in_memory(cls) -> "AuditRepository":
        return cls(connection=sqlite3.connect(":memory:", check_same_thread=False))

    @property
    def is_postgres(self) -> bool:
        return bool(self.postgres_dsn)

    def _connect(self):
        if self._connection is not None:
            return self._connection
        if self.is_postgres:
            try:
                import psycopg2
                import psycopg2.extras
            except Exception as exc:  # pragma: no cover
                raise AuditIndexError("psycopg2 non disponibile per indice audit Postgres.") from exc
            if not hasattr(self._local, "conn") or self._local.conn is None:
                self._local.conn = psycopg2.connect(self.postgres_dsn)
            return self._local.conn
        if self.sqlite_path is None:
            raise AuditIndexError("Percorso SQLite indice audit mancante.")
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self._local.conn = sqlite3.connect(str(self.sqlite_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        if self.is_postgres:
            schema_path = Path(__file__).resolve().parents[1] / "pct" / "sql" / "20260513_legal_audit_worm_postgres.sql"
            if schema_path.exists():
                with conn.cursor() as cur:
                    cur.execute(schema_path.read_text(encoding="utf-8"))
                conn.commit()
            return
        conn.executescript(SQLITE_SCHEMA)
        conn.commit()

    def _execute(self, conn: Any, sql: str, params: tuple[Any, ...] = ()):
        if self.is_postgres:
            with conn.cursor() as cur:
                cur.execute(sql.replace("?", "%s"), params)
                if cur.description:
                    columns = [item[0] for item in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                return []
        cur = conn.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
        return [dict(row) for row in rows]

    @contextmanager
    def transaction(self, *, chain_key: str = "") -> Iterator[Any]:
        conn = self._connect()
        lock = None
        if chain_key and not self.is_postgres:
            with self._locks_guard:
                lock = self._locks.setdefault(chain_key, threading.Lock())
            lock.acquire()
        try:
            if self.is_postgres:
                self._execute(conn, "BEGIN")
                if chain_key:
                    self._execute(conn, "SELECT pg_advisory_xact_lock(hashtext(?))", (chain_key,))
            else:
                self._execute(conn, "BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if lock is not None:
                lock.release()

    def chain_key(self, tenant_id: str, fascicolo_id: str) -> str:
        return f"{tenant_id}:{fascicolo_id}"

    def find_by_idempotency(self, tenant_id: str, fascicolo_id: str, idempotency_key: str, *, conn: Any | None = None) -> dict[str, Any] | None:
        rows = self._execute(
            conn or self._connect(),
            """
            SELECT * FROM audit_events_index
            WHERE tenant_id = ? AND fascicolo_id = ? AND idempotency_key = ?
            LIMIT 1
            """,
            (tenant_id, fascicolo_id, idempotency_key),
        )
        return self._decode_event_row(rows[0]) if rows else None

    def last_event_hash(self, tenant_id: str, fascicolo_id: str, *, conn: Any | None = None) -> str:
        rows = self._execute(
            conn or self._connect(),
            """
            SELECT event_hash FROM audit_events_index
            WHERE tenant_id = ? AND fascicolo_id = ?
            ORDER BY event_ts_utc DESC, event_id DESC
            LIMIT 1
            """,
            (tenant_id, fascicolo_id),
        )
        return str(rows[0].get("event_hash") or "") if rows else ""

    def insert_event(self, record: AuditEventIndexRecord, *, conn: Any | None = None) -> None:
        payload = asdict(record)
        payload["files_hashes_jsonb"] = _json(payload.get("files_hashes_jsonb"))
        columns = list(payload.keys())
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT INTO audit_events_index ({','.join(columns)}) VALUES ({placeholders})"
        self._execute(conn or self._connect(), sql, tuple(payload[column] for column in columns))

    def upsert_event_from_rebuild(self, record: AuditEventIndexRecord, *, conn: Any | None = None) -> bool:
        if self.get_event(record.event_id, tenant_id=record.tenant_id, conn=conn):
            return False
        self.insert_event(record, conn=conn)
        return True

    def get_event(self, event_id: str, *, tenant_id: str = "", conn: Any | None = None) -> dict[str, Any] | None:
        if tenant_id:
            rows = self._execute(
                conn or self._connect(),
                "SELECT * FROM audit_events_index WHERE event_id = ? AND tenant_id = ? LIMIT 1",
                (event_id, tenant_id),
            )
        else:
            rows = self._execute(conn or self._connect(), "SELECT * FROM audit_events_index WHERE event_id = ? LIMIT 1", (event_id,))
        return self._decode_event_row(rows[0]) if rows else None

    def list_events(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str = "",
        kind: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 200,
        include_snapshotted: bool = True,
    ) -> list[dict[str, Any]]:
        where = ["tenant_id = ?"]
        params: list[Any] = [tenant_id]
        if fascicolo_id:
            where.append("fascicolo_id = ?")
            params.append(fascicolo_id)
        if kind:
            where.append("kind = ?")
            params.append(kind)
        if date_from:
            where.append("event_ts_utc >= ?")
            params.append(date_from)
        if date_to:
            where.append("event_ts_utc <= ?")
            params.append(date_to)
        if not include_snapshotted:
            where.append("(snapshot_id IS NULL OR snapshot_id = '')")
        params.append(int(limit))
        sql = f"""
            SELECT * FROM audit_events_index
            WHERE {' AND '.join(where)}
            ORDER BY event_ts_utc ASC, event_id ASC
            LIMIT ?
        """
        return [self._decode_event_row(row) for row in self._execute(self._connect(), sql, tuple(params))]

    def tenants_with_open_events(self, *, date_from: str = "", date_to: str = "") -> list[str]:
        where = ["(snapshot_id IS NULL OR snapshot_id = '')"]
        params: list[Any] = []
        if date_from:
            where.append("event_ts_utc >= ?")
            params.append(date_from)
        if date_to:
            where.append("event_ts_utc <= ?")
            params.append(date_to)
        sql = f"""
            SELECT DISTINCT tenant_id
            FROM audit_events_index
            WHERE {' AND '.join(where)}
            ORDER BY tenant_id ASC
        """
        return [str(row.get("tenant_id") or "") for row in self._execute(self._connect(), sql, tuple(params)) if row.get("tenant_id")]

    def insert_snapshot(self, record: AuditSnapshotIndexRecord, *, conn: Any | None = None) -> None:
        payload = asdict(record)
        columns = list(payload.keys())
        sql = f"INSERT INTO audit_snapshots_index ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
        self._execute(conn or self._connect(), sql, tuple(payload[column] for column in columns))

    def mark_events_snapshot(self, event_ids: list[str], snapshot_id: str, *, conn: Any | None = None) -> None:
        if not event_ids:
            return
        active = conn or self._connect()
        for event_id in event_ids:
            self._execute(active, "UPDATE audit_events_index SET snapshot_id = ? WHERE event_id = ?", (snapshot_id, event_id))

    def get_snapshot(self, snapshot_id: str, *, tenant_id: str = "", conn: Any | None = None) -> dict[str, Any] | None:
        if tenant_id:
            rows = self._execute(
                conn or self._connect(),
                "SELECT * FROM audit_snapshots_index WHERE snapshot_id = ? AND tenant_id = ? LIMIT 1",
                (snapshot_id, tenant_id),
            )
        else:
            rows = self._execute(conn or self._connect(), "SELECT * FROM audit_snapshots_index WHERE snapshot_id = ? LIMIT 1", (snapshot_id,))
        return rows[0] if rows else None

    def record_failure(
        self,
        *,
        failure_id: str,
        tenant_id: str = "",
        fascicolo_id: str = "",
        attempted_kind: str = "",
        idempotency_key: str = "",
        failure_stage: str,
        error_code: str,
        error_message_sanitized: str,
    ) -> None:
        conn = self._connect()
        self._execute(
            conn,
            """
            INSERT INTO audit_emit_failures (
              failure_id, tenant_id, fascicolo_id, attempted_kind, idempotency_key,
              failure_stage, error_code, error_message_sanitized, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                failure_id,
                tenant_id,
                fascicolo_id,
                attempted_kind,
                idempotency_key,
                failure_stage,
                error_code,
                error_message_sanitized[:800],
                _now(),
            ),
        )
        conn.commit()

    def start_reconciliation(self, run_id: str, tenant_id: str = "") -> None:
        conn = self._connect()
        self._execute(
            conn,
            """
            INSERT INTO audit_reconciliation_runs (
              run_id, tenant_id, started_at, objects_seen, missing_index_rows_created,
              conflicts_found, status
            ) VALUES (?, ?, ?, 0, 0, 0, ?)
            """,
            (run_id, tenant_id, _now(), "RUNNING"),
        )
        conn.commit()

    def complete_reconciliation(
        self,
        run_id: str,
        *,
        objects_seen: int,
        missing_index_rows_created: int,
        conflicts_found: int,
        status: str,
    ) -> None:
        conn = self._connect()
        self._execute(
            conn,
            """
            UPDATE audit_reconciliation_runs
            SET completed_at = ?, objects_seen = ?, missing_index_rows_created = ?,
                conflicts_found = ?, status = ?
            WHERE run_id = ?
            """,
            (_now(), objects_seen, missing_index_rows_created, conflicts_found, status, run_id),
        )
        conn.commit()

    def _decode_event_row(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["files_hashes_jsonb"] = _load_json(result.get("files_hashes_jsonb"))
        return result
