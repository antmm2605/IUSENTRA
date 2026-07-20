from __future__ import annotations

import uuid
from typing import Any, Iterable, Mapping

from .models import canonical_json, json_load, required_text, utc_now_iso
from .repository import NotificationPresidioRepository
from .work_queue_lifecycle import NotificationPresidioWorkQueueLifecycleMixin


class NotificationPresidioWorkQueue(NotificationPresidioWorkQueueLifecycleMixin):
    def __init__(self, repository: NotificationPresidioRepository) -> None:
        self.repository = repository
        self.tenant_id = repository.tenant_id

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        result = dict(row) if row is not None else {}
        if "payload_json" in result:
            result["payload"] = json_load(result.pop("payload_json"), default={})
        return result

    def enqueue(
        self,
        job_type: str,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        priority: int = 0,
        available_at: str = "",
        max_attempts: int = 5,
    ) -> tuple[dict[str, Any], bool]:
        key = required_text(idempotency_key, "idempotency_key")
        now = utc_now_iso()
        job_id = str(uuid.uuid4())
        with self.repository.connection() as conn:
            conn.execute(
                """
                INSERT INTO pec_legal_notification_jobs
                (id, tenant_id, job_type, status, priority, payload_json,
                 idempotency_key, attempts, max_attempts, available_at,
                 worker_id, locked_at, heartbeat_at, started_at, completed_at,
                 last_error, created_at, updated_at)
                VALUES (?,?,?,'queued',?,?,?,0,?,?, '', NULL, NULL, NULL, NULL, '', ?, ?)
                ON CONFLICT(tenant_id, idempotency_key) DO NOTHING
                """,
                (
                    job_id,
                    self.tenant_id,
                    required_text(job_type, "job_type"),
                    int(priority),
                    canonical_json(dict(payload)),
                    key,
                    max(1, int(max_attempts)),
                    str(available_at or now),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM pec_legal_notification_jobs WHERE tenant_id=? AND idempotency_key=?",
                (self.tenant_id, key),
            ).fetchone()
        result = self._row(row)
        return result, str(result.get("id") or "") == job_id

    @staticmethod
    def _job_type_clause(job_types: Iterable[str]) -> tuple[str, list[str]]:
        normalized = sorted({str(item or "").strip() for item in job_types if str(item or "").strip()})
        if not normalized:
            return "", []
        return f" AND job_type IN ({','.join('?' for _ in normalized)})", normalized

    def claim_next_job(self, worker_id: str, *, job_types: Iterable[str] = ()) -> dict[str, Any] | None:
        worker = required_text(worker_id, "worker_id")
        now = utc_now_iso()
        clause, type_params = self._job_type_clause(job_types)
        with self.repository.connection() as conn:
            if self.repository.backend_kind == "postgresql":
                sql = f"""
                    WITH candidate AS (
                        SELECT id FROM pec_legal_notification_jobs
                        WHERE tenant_id=? AND status='queued' AND available_at<=?
                        {clause}
                        ORDER BY priority DESC, available_at, id
                        FOR UPDATE SKIP LOCKED LIMIT 1
                    )
                    UPDATE pec_legal_notification_jobs AS job
                    SET status='running', worker_id=?, locked_at=?, heartbeat_at=?,
                        started_at=?, attempts=job.attempts+1, updated_at=?
                    FROM candidate
                    WHERE job.tenant_id=? AND job.id=candidate.id AND job.status='queued'
                    RETURNING job.*
                """
                params: list[Any] = [self.tenant_id, now, *type_params]
                params.extend((worker, now, now, now, now, self.tenant_id))
                row = conn.execute(sql, tuple(params)).fetchone()
            else:
                conn.execute("BEGIN IMMEDIATE")
                sql = f"""
                    SELECT id FROM pec_legal_notification_jobs
                    WHERE tenant_id=? AND status='queued' AND available_at<=?
                    {clause}
                    ORDER BY priority DESC, available_at, id LIMIT 1
                """
                candidate = conn.execute(sql, (self.tenant_id, now, *type_params)).fetchone()
                if candidate is None:
                    return None
                row = conn.execute(
                    """
                    UPDATE pec_legal_notification_jobs
                    SET status='running', worker_id=?, locked_at=?, heartbeat_at=?,
                        started_at=?, attempts=attempts+1, updated_at=?
                    WHERE tenant_id=? AND id=? AND status='queued'
                    RETURNING *
                    """,
                    (
                        worker,
                        now,
                        now,
                        now,
                        now,
                        self.tenant_id,
                        candidate["id"],
                    ),
                ).fetchone()
        return self._row(row) if row is not None else None

    def heartbeat(self, job_id: str, *, worker_id: str) -> bool:
        now = utc_now_iso()
        with self.repository.connection() as conn:
            row = conn.execute(
                """
                UPDATE pec_legal_notification_jobs SET heartbeat_at=?, updated_at=?
                WHERE tenant_id=? AND id=? AND status='running' AND worker_id=?
                RETURNING id
                """,
                (now, now, self.tenant_id, job_id, worker_id),
            ).fetchone()
        return row is not None
