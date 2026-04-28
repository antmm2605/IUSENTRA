"""Migrazione idempotente JSON -> tabella documentale SQLite."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.database import ensure_core_sqlite_schema, is_sqlite_url, sqlite_connection
from core.storage.json_discovery import discover_json_files


def migrate_json_directory_to_sqlite(root: str | Path, database_url: str, *, limit: int = 0) -> dict[str, Any]:
    if not is_sqlite_url(database_url):
        return migrate_json_directory_to_sql(root, database_url, limit=limit)
    ensure_core_sqlite_schema(database_url)
    files = discover_json_files(root)
    if limit:
        files = files[:limit]
    report = {"ok": True, "files": len(files), "records": 0, "errors": []}
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with sqlite_connection(database_url) as conn:
        for item in files:
            try:
                payload = json.loads(item.path.read_text(encoding="utf-8") or "null")
                records = _iter_records(payload)
                for record_key, record in records:
                    title, body = _record_text(record)
                    raw = json.dumps(record, ensure_ascii=False, sort_keys=True)
                    digest = hashlib.sha256(raw.encode()).hexdigest()
                    doc_id = hashlib.sha256(f"{item.relative_path}:{record_key}".encode()).hexdigest()
                    conn.execute(
                        """
                        INSERT INTO json_documents(id, source_path, record_key, title, body, payload_json, sha256, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            title=excluded.title,
                            body=excluded.body,
                            payload_json=excluded.payload_json,
                            sha256=excluded.sha256,
                            updated_at=excluded.updated_at
                        """,
                        (doc_id, item.relative_path, record_key, title, body, raw, digest, now, now),
                    )
                    conn.execute("DELETE FROM json_documents_fts WHERE id = ?", (doc_id,))
                    conn.execute(
                        "INSERT INTO json_documents_fts(id, title, body, source_path) VALUES (?, ?, ?, ?)",
                        (doc_id, title, body, item.relative_path),
                    )
                    report["records"] += 1
            except Exception as exc:
                report["ok"] = False
                report["errors"].append({"file": item.relative_path, "errore": str(exc)})
    return report


def migrate_json_directory_to_sql(root: str | Path, database_url: str, *, limit: int = 0) -> dict[str, Any]:
    try:
        from sqlalchemy import create_engine, text
    except Exception as exc:
        return {"ok": False, "files": 0, "records": 0, "errors": [{"errore": f"SQLAlchemy non disponibile: {exc}"}]}
    files = discover_json_files(root)
    if limit:
        files = files[:limit]
    report = {"ok": True, "files": len(files), "records": 0, "errors": []}
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS json_documents (
                    id VARCHAR(64) PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    record_key TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    sha256 VARCHAR(64) NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        for item in files:
            try:
                payload = json.loads(item.path.read_text(encoding="utf-8") or "null")
                for record_key, record in _iter_records(payload):
                    title, body = _record_text(record)
                    raw = json.dumps(record, ensure_ascii=False, sort_keys=True)
                    digest = hashlib.sha256(raw.encode()).hexdigest()
                    doc_id = hashlib.sha256(f"{item.relative_path}:{record_key}".encode()).hexdigest()
                    conn.execute(
                        text(
                            """
                            INSERT INTO json_documents
                            (id, source_path, record_key, title, body, payload_json, sha256, created_at, updated_at)
                            VALUES
                            (:id, :source_path, :record_key, :title, :body, :payload_json, :sha256, :created_at, :updated_at)
                            ON CONFLICT (id) DO UPDATE SET
                                title = EXCLUDED.title,
                                body = EXCLUDED.body,
                                payload_json = EXCLUDED.payload_json,
                                sha256 = EXCLUDED.sha256,
                                updated_at = EXCLUDED.updated_at
                            """
                        ),
                        {
                            "id": doc_id,
                            "source_path": item.relative_path,
                            "record_key": record_key,
                            "title": title,
                            "body": body,
                            "payload_json": raw,
                            "sha256": digest,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    report["records"] += 1
            except Exception as exc:
                report["ok"] = False
                report["errors"].append({"file": item.relative_path, "errore": str(exc)})
    return report


def _iter_records(payload: Any) -> list[tuple[str, Any]]:
    if isinstance(payload, list):
        return [(str(index), value) for index, value in enumerate(payload)]
    if isinstance(payload, dict):
        return [(str(key), value) for key, value in payload.items()]
    return [("value", payload)]


def _record_text(record: Any) -> tuple[str, str]:
    if isinstance(record, dict):
        title = str(record.get("titolo") or record.get("title") or record.get("nome") or record.get("id") or "")[:240]
        body = " ".join(str(value) for value in record.values() if isinstance(value, (str, int, float)))
        return title, body[:8000]
    return str(record)[:240], str(record)[:8000]
