"""Repository SQL/PostgreSQL per crash test operativo, repair ticket e backup blindato."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from pct.postgres_runtime_support import PostgresRepositoryBackend


_SQLITE_SCHEMA_PATH = Path(__file__).resolve().parent / "sql" / "20260420_operational_resilience.sql"
_POSTGRES_SCHEMA_PATH = (
    Path(__file__).resolve().parent / "sql" / "20260420_operational_resilience_postgres.sql"
)


def _decode_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    return dict(row)


class OperationalResilienceRepository:
    """Persistenza governata dei report operativi su SQLite o PostgreSQL."""

    def __init__(self, *, sqlite_path: str = "", postgres_dsn: str = "") -> None:
        self.sqlite_path = Path(str(sqlite_path or "").strip()) if str(sqlite_path or "").strip() else None
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self._postgres_backend: PostgresRepositoryBackend | None = None
        self.ensure_schema()

    def ensure_schema(self) -> None:
        if self.backend_kind == "postgresql":
            if self._postgres_backend is None:
                self._postgres_backend = PostgresRepositoryBackend(
                    self.postgres_dsn,
                    _POSTGRES_SCHEMA_PATH,
                )
            return
        if self.sqlite_path is None:
            raise ValueError("Percorso SQLite operativo non configurato.")
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.sqlite_path)) as conn:
            conn.executescript(_SQLITE_SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.commit()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.backend_kind == "postgresql":
            if self._postgres_backend is None:
                self.ensure_schema()
            assert self._postgres_backend is not None
            with self._postgres_backend.connection() as conn:
                yield conn
            return
        if self.sqlite_path is None:
            raise ValueError("Percorso SQLite operativo non configurato.")
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ping(self) -> bool:
        try:
            with self.connect() as conn:
                row = self._fetch_one(conn, "SELECT 1 AS ok")
        except Exception:
            return False
        return bool(int((row or {}).get("ok") or 0) == 1)

    def _fetch_one(self, conn: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
        if self.backend_kind == "postgresql":
            row = conn.execute(sql, params).fetchone()
            return _row_to_dict(row)
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return _row_to_dict(row)

    def _fetch_all(self, conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if self.backend_kind == "postgresql":
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in rows]
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return [_row_to_dict(row) for row in rows]

    def _insert_returning_id(self, conn: Any, sql: str, params: tuple[Any, ...]) -> int:
        statement = str(sql or "").strip()
        if self.backend_kind == "postgresql":
            row = conn.execute(f"{statement} RETURNING id", params).fetchone()
            return int(_row_to_dict(row).get("id") or 0)
        cur = conn.execute(f"{statement} RETURNING id", params)
        row = cur.fetchone()
        return int(_row_to_dict(row).get("id") or 0)

    def record_crash_run(self, payload: dict[str, Any]) -> int:
        with self.connect() as conn:
            return self._insert_returning_id(
                conn,
                """
                INSERT INTO operational_crash_test_runs (
                    tenant_slug,
                    trigger_source,
                    schedule_code,
                    started_at,
                    completed_at,
                    status,
                    overall_ok,
                    attempt_count,
                    total_phases,
                    passed_phases,
                    report_path,
                    report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(payload.get("tenant_slug") or ""),
                    str(payload.get("trigger_source") or "manual"),
                    str(payload.get("schedule_code") or ""),
                    str(payload.get("started_at") or ""),
                    str(payload.get("completed_at") or ""),
                    str(payload.get("status") or "failed"),
                    1 if bool(payload.get("overall_ok")) else 0,
                    int(payload.get("attempt_count") or 1),
                    int(payload.get("total_phases") or 0),
                    int(payload.get("passed_phases") or 0),
                    str(payload.get("report_path") or ""),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def list_crash_runs(self, *, tenant_slug: str = "", limit: int = 12) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if str(tenant_slug or "").strip():
            where = "WHERE tenant_slug = ?"
            params.append(str(tenant_slug).strip().lower())
        params.append(int(limit))
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                f"""
                SELECT id, tenant_slug, trigger_source, schedule_code, started_at, completed_at,
                       status, overall_ok, attempt_count, total_phases, passed_phases,
                       report_path, report_json
                FROM operational_crash_test_runs
                {where}
                ORDER BY completed_at DESC, id DESC
                LIMIT ?
                """,
                tuple(params),
            )
        for row in rows:
            row["overall_ok"] = bool(row.get("overall_ok"))
            row["report_json"] = _decode_json(row.get("report_json"), {})
        return rows

    def latest_crash_run(self, *, tenant_slug: str = "") -> dict[str, Any] | None:
        rows = self.list_crash_runs(tenant_slug=tenant_slug, limit=1)
        return rows[0] if rows else None

    def record_repair_ticket(self, crash_run_id: int, tenant_slug: str, payload: dict[str, Any]) -> int:
        with self.connect() as conn:
            return self._insert_returning_id(
                conn,
                """
                INSERT INTO operational_repair_tickets (
                    crash_run_id,
                    tenant_slug,
                    action_code,
                    severity,
                    status,
                    title,
                    remediation,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(crash_run_id or 0),
                    str(tenant_slug or ""),
                    str(payload.get("action_code") or ""),
                    str(payload.get("severity") or "warning"),
                    str(payload.get("status") or "open"),
                    str(payload.get("title") or ""),
                    str(payload.get("remediation") or ""),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def list_repair_tickets(self, *, tenant_slug: str = "", limit: int = 20) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if str(tenant_slug or "").strip():
            where = "WHERE tenant_slug = ?"
            params.append(str(tenant_slug).strip().lower())
        params.append(int(limit))
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                f"""
                SELECT id, crash_run_id, tenant_slug, action_code, severity, status,
                       title, remediation, payload_json, created_at
                FROM operational_repair_tickets
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                tuple(params),
            )
        for row in rows:
            row["payload_json"] = _decode_json(row.get("payload_json"), {})
        return rows

    def record_backup_run(self, tenant_slug: str, payload: dict[str, Any]) -> int:
        with self.connect() as conn:
            return self._insert_returning_id(
                conn,
                """
                INSERT INTO operational_backup_runs (
                    tenant_slug,
                    executed_at,
                    backup_scope,
                    backup_type,
                    status,
                    primary_record_id,
                    primary_path,
                    local_copy_path,
                    secondary_copy_path,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(tenant_slug or ""),
                    str(payload.get("executed_at") or ""),
                    str(payload.get("backup_scope") or "nightly"),
                    str(payload.get("backup_type") or "COMPLETO"),
                    str(payload.get("status") or "OK"),
                    str(payload.get("primary_record_id") or ""),
                    str(payload.get("primary_path") or ""),
                    str(payload.get("local_copy_path") or ""),
                    str(payload.get("secondary_copy_path") or ""),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def list_backup_runs(self, *, tenant_slug: str = "", limit: int = 20) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if str(tenant_slug or "").strip():
            where = "WHERE tenant_slug = ?"
            params.append(str(tenant_slug).strip().lower())
        params.append(int(limit))
        with self.connect() as conn:
            rows = self._fetch_all(
                conn,
                f"""
                SELECT id, tenant_slug, executed_at, backup_scope, backup_type, status,
                       primary_record_id, primary_path, local_copy_path,
                       secondary_copy_path, payload_json
                FROM operational_backup_runs
                {where}
                ORDER BY executed_at DESC, id DESC
                LIMIT ?
                """,
                tuple(params),
            )
        for row in rows:
            row["payload_json"] = _decode_json(row.get("payload_json"), {})
        return rows

    def latest_backup_run(self, *, tenant_slug: str = "") -> dict[str, Any] | None:
        rows = self.list_backup_runs(tenant_slug=tenant_slug, limit=1)
        return rows[0] if rows else None
