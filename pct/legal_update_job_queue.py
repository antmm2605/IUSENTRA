"""Coda persistente per job di acquisizione fonti legali.

Serve per Cassazione e fonti pubbliche: ogni pagina, allegato o documento da
processare può essere accodato con chiave di deduplica, hash contenuto, timeout,
tentativi, stato leggibile e ripresa deterministica dopo crash.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping


LEGAL_UPDATE_JOB_QUEUE_SCHEMA = "iusentra.legal_source_job_queue.v1"
FINAL_STATUSES = {"completed", "skipped"}
ACTIVE_STATUSES = {"queued", "running"}
ERROR_STATUSES = {"failed", "timeout"}


@dataclass(frozen=True, slots=True)
class LegalUpdateQueueJob:
    job_id: str
    dedupe_key: str
    source_code: str
    source_name: str
    item_url: str
    item_title: str
    item_kind: str
    content_hash: str
    status: str
    attempts: int
    max_attempts: int
    timeout_seconds: int
    last_error: str = ""
    worker_id: str = ""
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    created_at: str = ""
    updated_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    deduplicated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "schema": LEGAL_UPDATE_JOB_QUEUE_SCHEMA,
                "job_id": self.job_id,
                "dedupe_key": self.dedupe_key,
                "source_code": self.source_code,
                "source_name": self.source_name,
                "item_url": self.item_url,
                "item_title": self.item_title,
                "item_kind": self.item_kind,
                "content_hash": self.content_hash,
                "status": self.status,
                "attempts": self.attempts,
                "max_attempts": self.max_attempts,
                "timeout_seconds": self.timeout_seconds,
                "last_error": self.last_error,
                "worker_id": self.worker_id,
                "payload": self.payload or {},
                "result": self.result or {},
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "deduplicated": self.deduplicated,
            }
        )


class LegalUpdateJobQueue:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def enqueue(
        self,
        *,
        source_code: str,
        source_name: str = "",
        item_url: str = "",
        item_title: str = "",
        item_kind: str = "documento",
        payload: Mapping[str, Any] | None = None,
        content: bytes | str = b"",
        content_hash: str = "",
        dedupe_key: str = "",
        timeout_seconds: int = 180,
        max_attempts: int = 3,
    ) -> LegalUpdateQueueJob:
        payload_dict = dict(payload or {})
        source = _clean(source_code)
        if not source:
            raise ValueError("Codice fonte obbligatorio per il job.")
        clean_hash = _content_hash(content=content, content_hash=content_hash, payload=payload_dict)
        key = dedupe_key or build_legal_update_dedupe_key(
            source_code=source,
            item_url=item_url,
            item_kind=item_kind,
            payload=payload_dict,
            content_hash=clean_hash,
        )
        job_id = _job_id(key)
        now = _now()
        with self.connect() as conn:
            existing = conn.execute("SELECT * FROM legal_update_jobs WHERE dedupe_key = ?", (key,)).fetchone()
            if existing:
                return _row_to_job(existing, deduplicated=True)
            conn.execute(
                """
                INSERT INTO legal_update_jobs (
                    job_id, dedupe_key, source_code, source_name, item_url, item_title,
                    item_kind, content_hash, status, attempts, max_attempts, timeout_seconds,
                    last_error, worker_id, payload_json, result_json, created_at, updated_at,
                    started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?, '', '', ?, '{}', ?, ?, '', '')
                """,
                (
                    job_id,
                    key,
                    source,
                    _clean(source_name),
                    _clean(item_url),
                    _clean(item_title),
                    _clean(item_kind) or "documento",
                    clean_hash,
                    max(1, int(max_attempts or 1)),
                    max(1, int(timeout_seconds or 1)),
                    _json_dump(payload_dict),
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM legal_update_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row)

    def enqueue_many(self, rows: Iterable[Mapping[str, Any]], *, source_code: str = "") -> list[LegalUpdateQueueJob]:
        jobs: list[LegalUpdateQueueJob] = []
        for row in rows:
            payload = dict(row or {})
            jobs.append(
                self.enqueue(
                    source_code=source_code or str(payload.get("source_code") or ""),
                    source_name=str(payload.get("source_name") or ""),
                    item_url=str(payload.get("item_url") or payload.get("official_url") or payload.get("url") or ""),
                    item_title=str(payload.get("item_title") or payload.get("title") or ""),
                    item_kind=str(payload.get("item_kind") or payload.get("type") or "documento"),
                    payload=payload,
                    content_hash=str(payload.get("sha256") or payload.get("content_hash") or ""),
                    timeout_seconds=_safe_int(payload.get("timeout_seconds"), 180),
                    max_attempts=_safe_int(payload.get("max_attempts"), 3),
                )
            )
        return jobs

    def claim_next(self, *, worker_id: str = "worker", recover_stale: bool = True) -> LegalUpdateQueueJob | None:
        if recover_stale:
            self.recover_stale_running()
        now = _now()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM legal_update_jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC, job_id ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            attempts = int(row["attempts"] or 0) + 1
            conn.execute(
                """
                UPDATE legal_update_jobs
                SET status='running', attempts=?, worker_id=?, started_at=?, updated_at=?,
                    last_error=''
                WHERE job_id=? AND status='queued'
                """,
                (attempts, _clean(worker_id), now, now, row["job_id"]),
            )
            claimed = conn.execute("SELECT * FROM legal_update_jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
        return _row_to_job(claimed)

    def complete(self, job_id: str, *, result: Mapping[str, Any] | None = None, content_hash: str = "") -> LegalUpdateQueueJob:
        now = _now()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM legal_update_jobs WHERE job_id = ?", (_clean(job_id),)).fetchone()
            if not row:
                raise KeyError(f"Job non trovato: {job_id}")
            final_hash = _clean(content_hash) or str(row["content_hash"] or "")
            conn.execute(
                """
                UPDATE legal_update_jobs
                SET status='completed', content_hash=?, result_json=?, finished_at=?, updated_at=?,
                    last_error='', worker_id=''
                WHERE job_id=?
                """,
                (final_hash, _json_dump(dict(result or {})), now, now, row["job_id"]),
            )
            updated = conn.execute("SELECT * FROM legal_update_jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
        return _row_to_job(updated)

    def fail(self, job_id: str, *, error: str, timed_out: bool = False) -> LegalUpdateQueueJob:
        now = _now()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM legal_update_jobs WHERE job_id = ?", (_clean(job_id),)).fetchone()
            if not row:
                raise KeyError(f"Job non trovato: {job_id}")
            attempts = int(row["attempts"] or 0)
            max_attempts = max(1, int(row["max_attempts"] or 1))
            final_status = "timeout" if timed_out else "failed"
            next_status = final_status if attempts >= max_attempts else "queued"
            clean_error = _readable_error(error, timed_out=timed_out, attempts=attempts, max_attempts=max_attempts)
            conn.execute(
                """
                UPDATE legal_update_jobs
                SET status=?, last_error=?, worker_id='', finished_at=?, updated_at=?
                WHERE job_id=?
                """,
                (next_status, clean_error, now if next_status in ERROR_STATUSES else "", now, row["job_id"]),
            )
            updated = conn.execute("SELECT * FROM legal_update_jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
        return _row_to_job(updated)

    def recover_stale_running(self, *, older_than_seconds: int | None = None) -> int:
        now_dt = datetime.now(tz=UTC)
        recovered = 0
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM legal_update_jobs WHERE status = 'running'").fetchall()
            for row in rows:
                started = _parse_iso(row["started_at"])
                timeout_seconds = max(1, int(row["timeout_seconds"] or 1))
                threshold = int(older_than_seconds) if older_than_seconds is not None else timeout_seconds * 2
                if started is None or now_dt - started < timedelta(seconds=max(0, threshold)):
                    continue
                attempts = int(row["attempts"] or 0)
                max_attempts = max(1, int(row["max_attempts"] or 1))
                status = "timeout" if attempts >= max_attempts else "queued"
                message = "Job recuperato dopo arresto o timeout del worker."
                conn.execute(
                    """
                    UPDATE legal_update_jobs
                    SET status=?, worker_id='', last_error=?, finished_at=?, updated_at=?
                    WHERE job_id=?
                    """,
                    (status, message, _now() if status == "timeout" else "", _now(), row["job_id"]),
                )
                recovered += 1
        return recovered

    def get(self, job_id: str) -> LegalUpdateQueueJob | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM legal_update_jobs WHERE job_id = ?", (_clean(job_id),)).fetchone()
        return _row_to_job(row) if row else None

    def list_jobs(self, *, status: str = "", limit: int = 100) -> list[LegalUpdateQueueJob]:
        with self.connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM legal_update_jobs WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (_clean(status), max(1, int(limit or 1))),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM legal_update_jobs ORDER BY updated_at DESC LIMIT ?",
                    (max(1, int(limit or 1)),),
                ).fetchall()
        return [_row_to_job(row) for row in rows]

    def summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM legal_update_jobs GROUP BY status"
            ).fetchall()
        counts = {str(row["status"]): int(row["count"] or 0) for row in rows}
        total = sum(counts.values())
        return {
            "schema": LEGAL_UPDATE_JOB_QUEUE_SCHEMA,
            "total": total,
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "timeout": counts.get("timeout", 0),
            "skipped": counts.get("skipped", 0),
            "ready": counts.get("queued", 0) + counts.get("running", 0),
        }

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS legal_update_jobs (
                    job_id TEXT PRIMARY KEY,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    source_code TEXT NOT NULL,
                    source_name TEXT NOT NULL DEFAULT '',
                    item_url TEXT NOT NULL DEFAULT '',
                    item_title TEXT NOT NULL DEFAULT '',
                    item_kind TEXT NOT NULL DEFAULT 'documento',
                    content_hash TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    timeout_seconds INTEGER NOT NULL DEFAULT 180,
                    last_error TEXT NOT NULL DEFAULT '',
                    worker_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_legal_update_jobs_status ON legal_update_jobs(status, updated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_legal_update_jobs_source ON legal_update_jobs(source_code, status)")


def build_legal_update_dedupe_key(
    *,
    source_code: str,
    item_url: str = "",
    item_kind: str = "",
    payload: Mapping[str, Any] | None = None,
    content_hash: str = "",
) -> str:
    payload_dict = dict(payload or {})
    stable_payload = {
        key: payload_dict.get(key)
        for key in sorted(payload_dict)
        if key not in {"fetched_at", "created_at", "updated_at", "last_checked_at", "error"}
    }
    raw = {
        "source_code": _clean(source_code).lower(),
        "item_url": _clean(item_url).lower(),
        "item_kind": _clean(item_kind).lower(),
        "content_hash": _clean(content_hash),
        "payload": stable_payload,
    }
    return "legal-job:" + _sha256(_json_dump(raw))[:40]


def _row_to_job(row: sqlite3.Row | None, *, deduplicated: bool = False) -> LegalUpdateQueueJob:
    if row is None:
        raise ValueError("Riga job mancante.")
    return LegalUpdateQueueJob(
        job_id=str(row["job_id"] or ""),
        dedupe_key=str(row["dedupe_key"] or ""),
        source_code=str(row["source_code"] or ""),
        source_name=str(row["source_name"] or ""),
        item_url=str(row["item_url"] or ""),
        item_title=str(row["item_title"] or ""),
        item_kind=str(row["item_kind"] or ""),
        content_hash=str(row["content_hash"] or ""),
        status=str(row["status"] or ""),
        attempts=int(row["attempts"] or 0),
        max_attempts=int(row["max_attempts"] or 0),
        timeout_seconds=int(row["timeout_seconds"] or 0),
        last_error=str(row["last_error"] or ""),
        worker_id=str(row["worker_id"] or ""),
        payload=_json_load(row["payload_json"], {}),
        result=_json_load(row["result_json"], {}),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
        started_at=str(row["started_at"] or ""),
        finished_at=str(row["finished_at"] or ""),
        deduplicated=deduplicated,
    )


def _content_hash(*, content: bytes | str, content_hash: str, payload: Mapping[str, Any]) -> str:
    clean_hash = _clean(content_hash)
    if clean_hash:
        return clean_hash
    if content:
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    return hashlib.sha256(_json_dump(dict(payload or {})).encode("utf-8")).hexdigest()


def _readable_error(error: str, *, timed_out: bool, attempts: int, max_attempts: int) -> str:
    base = _clean(error) or "Errore non specificato."
    prefix = "Timeout" if timed_out else "Errore"
    retry = "ritento" if attempts < max_attempts else "tentativi esauriti"
    return f"{prefix}: {base} ({attempts}/{max_attempts}, {retry})."[:1200]


def _parse_iso(value: Any) -> datetime | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_load(value: Any, default: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _job_id(dedupe_key: str) -> str:
    return "legal-job-" + _sha256(dedupe_key)[:24]


def _sha256(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [], {}, ())}
