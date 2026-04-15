"""Coda OCR persistente con backend SQLite."""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def default_ocr_queue_db(search_index_path: str) -> str:
    search_path = Path(search_index_path)
    return str((search_path.parent / "ocr_jobs.db").resolve())


@dataclass(frozen=True)
class OCRJob:
    id: int
    percorso: str
    hash_sha256: str
    id_fasc: str
    id_doc: str
    nome_doc: str
    tipo_doc: str
    index_path: str
    attempts: int = 0


class OCRJobStore:
    """Storage SQLite per job OCR accodati dall'app e processati da worker dedicati."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._ensure_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError as exc:
                logger.warning(
                    "SQLite WAL non disponibile per la coda OCR %s, fallback a DELETE: %s",
                    self.db_path,
                    exc,
                )
                conn.execute("PRAGMA journal_mode = DELETE")
            conn.execute("PRAGMA synchronous = NORMAL")
            self._local.conn = conn
        return conn

    def enqueue(
        self,
        *,
        percorso: str,
        hash_sha256: str,
        id_fasc: str,
        id_doc: str,
        nome_doc: str,
        tipo_doc: str,
        index_path: str,
    ) -> int:
        conn = self.conn
        now = datetime.now().isoformat()
        row = conn.execute(
            """
            SELECT id
            FROM ocr_jobs
            WHERE hash_sha256 = ?
              AND id_fasc = ?
              AND id_doc = ?
              AND status IN ('pending', 'processing')
            ORDER BY id DESC
            LIMIT 1
            """,
            (hash_sha256, id_fasc, id_doc),
        ).fetchone()
        if row:
            return int(row["id"])

        cursor = conn.execute(
            """
            INSERT INTO ocr_jobs (
                status,
                percorso,
                hash_sha256,
                id_fasc,
                id_doc,
                nome_doc,
                tipo_doc,
                index_path,
                attempts,
                created_at,
                updated_at,
                last_error
            ) VALUES ('pending', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, '')
            """,
            (percorso, hash_sha256, id_fasc, id_doc, nome_doc, tipo_doc, index_path, now, now),
        )
        conn.commit()
        return int(cursor.lastrowid)

    def claim_next(self, *, worker_id: str, stale_after_seconds: int = 600) -> OCRJob | None:
        conn = self.conn
        stale_before = (datetime.now() - timedelta(seconds=max(60, int(stale_after_seconds)))).isoformat()
        now = datetime.now().isoformat()
        conn.execute(
            """
            UPDATE ocr_jobs
               SET status = 'pending',
                   worker_id = '',
                   updated_at = ?
             WHERE status = 'processing'
               AND updated_at < ?
            """,
            (now, stale_before),
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM ocr_jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None

        updated = conn.execute(
            """
            UPDATE ocr_jobs
               SET status = 'processing',
                   worker_id = ?,
                   attempts = attempts + 1,
                   updated_at = ?
             WHERE id = ?
               AND status = 'pending'
            """,
            (worker_id, now, int(row["id"])),
        )
        conn.commit()
        if updated.rowcount != 1:
            return None

        claimed = conn.execute("SELECT * FROM ocr_jobs WHERE id = ?", (int(row["id"]),)).fetchone()
        if claimed is None:
            return None
        return OCRJob(
            id=int(claimed["id"]),
            percorso=str(claimed["percorso"] or ""),
            hash_sha256=str(claimed["hash_sha256"] or ""),
            id_fasc=str(claimed["id_fasc"] or ""),
            id_doc=str(claimed["id_doc"] or ""),
            nome_doc=str(claimed["nome_doc"] or ""),
            tipo_doc=str(claimed["tipo_doc"] or ""),
            index_path=str(claimed["index_path"] or ""),
            attempts=int(claimed["attempts"] or 0),
        )

    def complete(self, job_id: int) -> None:
        now = datetime.now().isoformat()
        self.conn.execute(
            """
            UPDATE ocr_jobs
               SET status = 'completed',
                   updated_at = ?,
                   last_error = ''
             WHERE id = ?
            """,
            (now, int(job_id)),
        )
        self.conn.commit()

    def fail(self, job_id: int, error: str) -> None:
        now = datetime.now().isoformat()
        self.conn.execute(
            """
            UPDATE ocr_jobs
               SET status = 'failed',
                   updated_at = ?,
                   last_error = ?
             WHERE id = ?
            """,
            (now, str(error or "").strip()[:1000], int(job_id)),
        )
        self.conn.commit()

    def retry_failed(self, *, max_items: int = 25) -> int:
        now = datetime.now().isoformat()
        rows = self.conn.execute(
            """
            SELECT id
            FROM ocr_jobs
            WHERE status = 'failed'
            ORDER BY updated_at ASC, id ASC
            LIMIT ?
            """,
            (max(1, int(max_items)),),
        ).fetchall()
        if not rows:
            return 0
        ids = [(int(row["id"]),) for row in rows]
        self.conn.executemany(
            """
            UPDATE ocr_jobs
               SET status = 'pending',
                   worker_id = '',
                   updated_at = ?,
                   last_error = ''
             WHERE id = ?
            """,
            [(now, job_id) for (job_id,) in ids],
        )
        self.conn.commit()
        return len(ids)

    def pending_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM ocr_jobs WHERE status = 'pending'"
        ).fetchone()
        return int(row["total"] if row else 0)

    def status_snapshot(self) -> dict[str, Any]:
        rows = self.conn.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM ocr_jobs
            GROUP BY status
            """
        ).fetchall()
        counts = {str(row["status"]): int(row["total"]) for row in rows}
        throughput_row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM ocr_jobs
            WHERE status = 'completed'
              AND updated_at >= ?
            """,
            ((datetime.now() - timedelta(hours=1)).isoformat(),),
        ).fetchone()
        return {
            "enabled": True,
            "totale": sum(counts.values()),
            "completati": counts.get("completed", 0),
            "errori": counts.get("failed", 0),
            "in_coda": counts.get("pending", 0),
            "in_lavorazione": counts.get("processing", 0),
            "throughput_ultima_ora": int(throughput_row["total"] if throughput_row else 0),
            "queue_db_path": str(self.db_path),
        }

    def _ensure_schema(self) -> None:
        conn = self.conn
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ocr_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                percorso TEXT NOT NULL,
                hash_sha256 TEXT NOT NULL,
                id_fasc TEXT NOT NULL,
                id_doc TEXT NOT NULL,
                nome_doc TEXT NOT NULL,
                tipo_doc TEXT NOT NULL,
                index_path TEXT NOT NULL,
                worker_id TEXT NOT NULL DEFAULT '',
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_ocr_jobs_status_created
                ON ocr_jobs(status, created_at, id);
            CREATE INDEX IF NOT EXISTS idx_ocr_jobs_hash_doc
                ON ocr_jobs(hash_sha256, id_fasc, id_doc);
            """
        )
        conn.commit()
