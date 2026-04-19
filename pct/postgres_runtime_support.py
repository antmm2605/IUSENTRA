from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

try:
    import psycopg2
    import psycopg2.extras

    _HAS_PSYCOPG2 = True
except ImportError:  # pragma: no cover - dipendenza disponibile in produzione
    psycopg2 = None  # type: ignore[assignment]
    _HAS_PSYCOPG2 = False

try:  # pragma: no cover - opzionale fuori da Flask
    from flask import current_app, g, has_app_context, has_request_context
except Exception:  # pragma: no cover - moduli dominio usabili anche fuori da Flask
    current_app = None  # type: ignore[assignment]
    g = None  # type: ignore[assignment]

    def has_app_context() -> bool:
        return False

    def has_request_context() -> bool:
        return False

from pct.storage_postgres import build_postgres_dsn


def _mode_value(database: Any) -> str:
    if database is None:
        return ""
    normalized = getattr(database, "normalized_mode", None)
    if normalized:
        return str(normalized or "").strip().upper()
    return str(getattr(database, "mode", "") or "").strip().upper()


def database_config_to_dsn(database: Any) -> str:
    if database is None or _mode_value(database) != "POSTGRESQL":
        return ""
    host = str(getattr(database, "host", "") or "").strip()
    db_name = str(getattr(database, "db_name", "") or "").strip()
    user = str(getattr(database, "utente", "") or "").strip()
    password = str(getattr(database, "password", "") or "")
    port = int(getattr(database, "porta_effettiva", 0) or getattr(database, "porta", 0) or 5432)
    ssl = bool(getattr(database, "ssl", False))
    if not all((host, db_name, user)):
        return ""
    return build_postgres_dsn(
        host=host,
        port=port,
        db_name=db_name,
        user=user,
        password=password,
        ssl=ssl,
    )


def resolve_runtime_postgres_dsn(
    explicit_dsn: str = "",
    *,
    database: Any = None,
    config: Any = None,
    env_url_keys: tuple[str, ...] = (),
) -> str:
    if str(explicit_dsn or "").strip():
        return str(explicit_dsn).strip()

    cfg = dict(config or {})
    for key in env_url_keys:
        value = str(cfg.get(key) or os.getenv(key) or "").strip()
        if value:
            return value

    dsn = database_config_to_dsn(database)
    if dsn:
        return dsn

    request_tenant = None
    if has_request_context() and g is not None:
        request_tenant = getattr(g, "tenant", None)
    if request_tenant is not None:
        dsn = database_config_to_dsn(getattr(request_tenant, "database", None))
        if dsn:
            return dsn

    if not cfg and has_app_context() and current_app is not None:
        try:
            cfg = dict(current_app.config)
        except Exception:
            cfg = {}

    app_tenant = cfg.get("TENANT_DATABASE_CONFIG")
    dsn = database_config_to_dsn(app_tenant)
    if dsn:
        return dsn

    return ""


class CompatRow(dict):
    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None):
        self._rows = [CompatRow(row) for row in (rows or [])]

    def __iter__(self):
        return iter(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


def translate_sql(sql: str) -> str:
    return str(sql or "").replace("?", "%s")


class PostgresRepositoryConnection:
    def __init__(self, backend: "PostgresRepositoryBackend") -> None:
        self._backend = backend

    def __enter__(self) -> "PostgresRepositoryConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None):
        statement = str(sql or "").strip()
        upper = statement.upper()
        if upper in {"BEGIN", "BEGIN;"}:
            return CompatResult()
        if upper in {"COMMIT", "COMMIT;"}:
            self._backend.raw_conn.commit()
            return CompatResult()
        if upper in {"ROLLBACK", "ROLLBACK;"}:
            self._backend.raw_conn.rollback()
            return CompatResult()
        with self._backend.raw_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(translate_sql(statement), tuple(params or ()))
            rows = cur.fetchall() if cur.description else []
        return CompatResult(rows)

    def executemany(self, sql: str, seq_of_params: list[tuple[Any, ...]] | tuple[tuple[Any, ...], ...]):
        statement = str(sql or "").strip()
        translated = translate_sql(statement)
        with self._backend.raw_conn.cursor() as cur:
            cur.executemany(translated, list(seq_of_params or []))
        return CompatResult()

    def executescript(self, script: str) -> None:
        with self._backend.raw_conn.cursor() as cur:
            cur.execute(str(script or ""))

    def commit(self) -> None:
        self._backend.raw_conn.commit()

    def rollback(self) -> None:
        self._backend.raw_conn.rollback()

    def close(self) -> None:
        return None


class PostgresRepositoryBackend:
    def __init__(self, dsn: str, schema_path: str | Path) -> None:
        if not _HAS_PSYCOPG2:
            raise RuntimeError(
                "psycopg2 non disponibile: installa psycopg2-binary per usare i repository PostgreSQL."
            )
        self.dsn = str(dsn or "").strip()
        self.schema_path = Path(schema_path)
        self._local = threading.local()
        self._ensure_schema()

    @property
    def raw_conn(self):
        if not hasattr(self._local, "_conn") or self._local._conn is None:
            self._local._conn = psycopg2.connect(self.dsn)
        return self._local._conn

    def connection(self) -> PostgresRepositoryConnection:
        return PostgresRepositoryConnection(self)

    def _ensure_schema(self) -> None:
        schema_sql = self.schema_path.read_text(encoding="utf-8")
        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

    def close(self) -> None:
        if hasattr(self._local, "_conn") and self._local._conn is not None:
            try:
                self._local._conn.close()
            finally:
                self._local._conn = None
