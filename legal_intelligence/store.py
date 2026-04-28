"""Persistenza SQLite del motore giornaliero Legal Intelligence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .sources import LegalSource


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


class LegalIntelligenceStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS legal_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    official INTEGER NOT NULL DEFAULT 1,
                    apply_mode TEXT NOT NULL DEFAULT 'manual',
                    impact_areas_json TEXT NOT NULL DEFAULT '[]',
                    user_agent_note TEXT NOT NULL DEFAULT '',
                    etag TEXT NOT NULL DEFAULT '',
                    last_modified TEXT NOT NULL DEFAULT '',
                    last_checked_at TEXT NOT NULL DEFAULT '',
                    last_status TEXT NOT NULL DEFAULT 'never',
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS legal_source_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '',
                    status_code INTEGER NOT NULL DEFAULT 0,
                    etag TEXT NOT NULL DEFAULT '',
                    last_modified TEXT NOT NULL DEFAULT '',
                    content_sha256 TEXT NOT NULL,
                    normalized_text TEXT NOT NULL DEFAULT '',
                    raw_path TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_legal_source_snapshots_source
                    ON legal_source_snapshots(source_id, fetched_at DESC);
                CREATE TABLE IF NOT EXISTS legal_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    old_sha256 TEXT NOT NULL DEFAULT '',
                    new_sha256 TEXT NOT NULL DEFAULT '',
                    diff_text TEXT NOT NULL DEFAULT '',
                    impact_areas_json TEXT NOT NULL DEFAULT '[]',
                    apply_mode TEXT NOT NULL DEFAULT 'manual',
                    status TEXT NOT NULL DEFAULT 'pending_review',
                    applied_at TEXT NOT NULL DEFAULT '',
                    application_note TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL DEFAULT 'media',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_legal_updates_status
                    ON legal_updates(status, detected_at DESC);
                CREATE TABLE IF NOT EXISTS legal_intelligence_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'running',
                    sources_checked INTEGER NOT NULL DEFAULT 0,
                    updates_detected INTEGER NOT NULL DEFAULT 0,
                    updates_applied INTEGER NOT NULL DEFAULT 0,
                    pending_review INTEGER NOT NULL DEFAULT 0,
                    errors_count INTEGER NOT NULL DEFAULT 0,
                    log_json TEXT NOT NULL DEFAULT '[]'
                );
                """
            )

    def upsert_source(self, source: LegalSource) -> None:
        now = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO legal_sources
                (id, name, url, category, enabled, official, apply_mode, impact_areas_json,
                 user_agent_note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    url=excluded.url,
                    category=excluded.category,
                    enabled=excluded.enabled,
                    official=excluded.official,
                    apply_mode=excluded.apply_mode,
                    impact_areas_json=excluded.impact_areas_json,
                    user_agent_note=excluded.user_agent_note,
                    updated_at=excluded.updated_at
                """,
                (
                    source.id,
                    source.name,
                    source.url,
                    source.category,
                    int(source.enabled),
                    int(source.official),
                    source.apply_mode,
                    json.dumps(list(source.impact_areas), ensure_ascii=False),
                    source.user_agent_note,
                    now,
                    now,
                ),
            )

    def source_headers(self, source_id: str) -> dict[str, str]:
        with self.connect() as conn:
            row = conn.execute("SELECT etag, last_modified FROM legal_sources WHERE id=?", (source_id,)).fetchone()
        return dict(row) if row else {}

    def latest_snapshot(self, source_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM legal_source_snapshots WHERE source_id=? ORDER BY fetched_at DESC, id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
        return dict(row) if row else None

    def add_snapshot(self, source_id: str, *, result: Any, content_sha256: str, normalized_text: str) -> int:
        fetched_at = now_iso()
        etag = result.headers.get("etag", "") if getattr(result, "headers", None) else ""
        last_modified = result.headers.get("last-modified", "") if getattr(result, "headers", None) else ""
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO legal_source_snapshots
                (source_id, fetched_at, url, status_code, etag, last_modified, content_sha256, normalized_text, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    fetched_at,
                    getattr(result, "url", ""),
                    int(getattr(result, "status_code", 0) or 0),
                    etag,
                    last_modified,
                    content_sha256,
                    normalized_text,
                    json.dumps({"ok": bool(getattr(result, "ok", False))}, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                UPDATE legal_sources
                SET last_checked_at=?, last_status=?, last_error=?, etag=COALESCE(NULLIF(?, ''), etag),
                    last_modified=COALESCE(NULLIF(?, ''), last_modified), updated_at=?
                WHERE id=?
                """,
                (fetched_at, "ok", "", etag, last_modified, fetched_at, source_id),
            )
            return int(cur.lastrowid)

    def mark_source_error(self, source_id: str, error: str) -> None:
        now = now_iso()
        with self.connect() as conn:
            conn.execute(
                "UPDATE legal_sources SET last_checked_at=?, last_status='errore', last_error=?, updated_at=? WHERE id=?",
                (now, str(error or "")[:800], now, source_id),
            )

    def mark_source_not_modified(self, source_id: str) -> None:
        now = now_iso()
        with self.connect() as conn:
            conn.execute(
                "UPDATE legal_sources SET last_checked_at=?, last_status='invariata', last_error='', updated_at=? WHERE id=?",
                (now, now, source_id),
            )

    def create_update(self, payload: dict[str, Any]) -> int:
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM legal_updates WHERE source_id=? AND new_sha256=? LIMIT 1",
                (payload["source_id"], payload["new_sha256"]),
            ).fetchone()
            if existing:
                return int(existing["id"])
            cur = conn.execute(
                """
                INSERT INTO legal_updates
                (source_id, detected_at, title, summary, old_sha256, new_sha256, diff_text,
                 impact_areas_json, apply_mode, status, applied_at, application_note, severity, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["source_id"],
                    payload.get("detected_at") or now_iso(),
                    payload["title"],
                    payload.get("summary", ""),
                    payload.get("old_sha256", ""),
                    payload["new_sha256"],
                    payload.get("diff_text", ""),
                    json.dumps(payload.get("impact_areas", []), ensure_ascii=False),
                    payload.get("apply_mode", "manual"),
                    payload.get("status", "pending_review"),
                    payload.get("applied_at", ""),
                    payload.get("application_note", ""),
                    payload.get("severity", "media"),
                    json.dumps(payload.get("metadata", {}), ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def update_status(self, update_id: int, *, status: str, note: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE legal_updates SET status=?, applied_at=?, application_note=? WHERE id=?",
                (status, now_iso() if status == "applied" else "", note, int(update_id)),
            )

    def create_run(self) -> int:
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO legal_intelligence_runs (started_at) VALUES (?)", (now_iso(),))
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, summary: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE legal_intelligence_runs
                SET finished_at=?, status=?, sources_checked=?, updates_detected=?,
                    updates_applied=?, pending_review=?, errors_count=?, log_json=?
                WHERE id=?
                """,
                (
                    now_iso(),
                    summary.get("status", "completed"),
                    int(summary.get("sources_checked", 0)),
                    int(summary.get("updates_detected", 0)),
                    int(summary.get("updates_applied", 0)),
                    int(summary.get("pending_review", 0)),
                    int(summary.get("errors_count", 0)),
                    json.dumps(summary.get("log", []), ensure_ascii=False),
                    int(run_id),
                ),
            )

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as conn:
            last_run = conn.execute("SELECT * FROM legal_intelligence_runs ORDER BY id DESC LIMIT 1").fetchone()
            sources = [dict(row) for row in conn.execute("SELECT * FROM legal_sources ORDER BY category, name")]
            updates = [dict(row) for row in conn.execute("SELECT * FROM legal_updates ORDER BY detected_at DESC, id DESC LIMIT 20")]
            counts = conn.execute(
                """
                SELECT
                    COUNT(*) AS updates,
                    SUM(CASE WHEN status='pending_review' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status='applied' THEN 1 ELSE 0 END) AS applied
                FROM legal_updates
                """
            ).fetchone()
        counts_dict = dict(counts) if counts else {}
        decoded_sources = [self._decode_json_fields(row, ("impact_areas_json",)) for row in sources]
        decoded_updates = [self._decode_json_fields(row, ("impact_areas_json", "metadata_json")) for row in updates]
        pending = int(counts_dict.get("pending") or 0)
        applied = int(counts_dict.get("applied") or 0)
        errors = sum(1 for row in decoded_sources if row.get("last_status") == "errore")
        return {
            "last_run": dict(last_run) if last_run else None,
            "sources": decoded_sources,
            "updates": decoded_updates,
            "counts": {
                "sources": len(decoded_sources),
                "updates": int(counts_dict.get("updates") or 0),
                "pending": pending,
                "applied": applied,
                "errors": errors,
            },
        }

    def get_update(self, update_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM legal_updates WHERE id=?", (int(update_id),)).fetchone()
        if not row:
            return None
        return self._decode_json_fields(dict(row), ("impact_areas_json", "metadata_json"))

    @staticmethod
    def _decode_json_fields(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        for field in fields:
            value = row.get(field)
            target = field.removesuffix("_json")
            default = "[]" if field.endswith("areas_json") else "{}"
            try:
                row[target] = json.loads(value or default)
            except Exception:
                row[target] = [] if field.endswith("areas_json") else {}
        return row
