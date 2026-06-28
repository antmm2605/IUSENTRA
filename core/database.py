"""Connessioni database leggere per SQLite/PostgreSQL e FTS governato."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse


def is_sqlite_url(database_url: str) -> bool:
    return not database_url or database_url.startswith("sqlite:")


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url:
        return Path("data/iusentra.sqlite")
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise ValueError("DATABASE_URL non SQLite")
    raw = parsed.path or ""
    if raw.startswith("/") and len(raw) > 3 and raw[2] == ":":
        raw = raw[1:]
    return Path(raw or "data/iusentra.sqlite")


@contextmanager
def sqlite_connection(database_url: str) -> Iterator[sqlite3.Connection]:
    path = sqlite_path_from_url(database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_core_sqlite_schema(database_url: str) -> None:
    with sqlite_connection(database_url) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS json_documents (
                id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                record_key TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_json_documents_source ON json_documents(source_path);
            CREATE INDEX IF NOT EXISTS idx_json_documents_record_key ON json_documents(record_key);
            CREATE VIRTUAL TABLE IF NOT EXISTS json_documents_fts
            USING fts5(id UNINDEXED, title, body, source_path UNINDEXED);

            CREATE TABLE IF NOT EXISTS hardening_audit_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT '',
                user_id TEXT NOT NULL DEFAULT '',
                ip TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}',
                previous_hash TEXT NOT NULL DEFAULT '',
                signature TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_hardening_audit_action ON hardening_audit_log(action);
            CREATE INDEX IF NOT EXISTS idx_hardening_audit_tenant ON hardening_audit_log(tenant_id);
            """
        )


def ping_database(database_url: str) -> tuple[bool, str]:
    try:
        if is_sqlite_url(database_url):
            with sqlite_connection(database_url) as conn:
                conn.execute("SELECT 1").fetchone()
            return True, "sqlite ok"
        try:
            from sqlalchemy import create_engine, text
        except Exception:  # pragma: no cover - dipendenza runtime
            return False, "sqlalchemy non disponibile"
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "postgres ok"
    except Exception:
        return False, "database non raggiungibile"
